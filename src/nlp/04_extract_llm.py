"""Phase 2 Baseline 3: Schema-Validated LLM Extraction (Gemini via google-genai).

Enforces:
- Strict Pydantic JSON output schema
- temperature = 0.0 for deterministic extraction
- Explicit UNKNOWN abstention policy
- Mandatory verbatim `evidence_span` quote per non-UNKNOWN field for hallucination auditing
- Incremental disk caching & retry backoff
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import threading
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = PROJECT_ROOT / "data" / "gold" / "gold_court_orders.jsonl"
OUT_PATH = PROJECT_ROOT / "outputs" / "preds_llm.jsonl"

# Reference published pricing (USD per 1M tokens) for Gemini 2.5 Flash
INPUT_COST_PER_M = 0.15
OUTPUT_COST_PER_M = 0.60


class ExtractedFieldStr(BaseModel):
    value: str = Field(..., description="Extracted value or 'UNKNOWN' if not clearly supported.")
    evidence_span: str = Field(
        ...,
        description="Exact verbatim substring copied from the court order supporting `value`, or empty string if UNKNOWN.",
    )


class ExtractedMoney(BaseModel):
    value: str = Field(
        ...,
        description="Numeric USD value as plain float string (e.g. '25000.0') for primary dollar figure >= 50, or 'UNKNOWN'.",
    )
    evidence_span: str = Field(
        ...,
        description="Exact verbatim substring containing the dollar figure, or empty string if UNKNOWN.",
    )


class ExtractedCategory(BaseModel):
    value: Literal[
        "criminal",
        "family",
        "housing_property",
        "civil_contract_tort",
        "administrative_other",
        "UNKNOWN",
    ]
    evidence_span: str


class ExtractedDisposition(BaseModel):
    value: Literal[
        "affirmed",
        "reversed_or_vacated",
        "remanded",
        "dismissed",
        "affirmed_in_part_reversed_in_part",
        "UNKNOWN",
    ]
    evidence_span: str


class ExtractedBoolFlag(BaseModel):
    value: Literal["true", "false", "UNKNOWN"]
    evidence_span: str


class CourtOrderExtraction(BaseModel):
    case_number: ExtractedFieldStr
    monetary_judgment_amount: ExtractedMoney
    case_category: ExtractedCategory
    disposition_outcome: ExtractedDisposition
    self_represented_flag: ExtractedBoolFlag
    remand_or_procedural_stay_flag: ExtractedBoolFlag


SYSTEM_PROMPT = """You are a careful judicial data analyst extracting structured fields from Maryland state court opinions.

Rules:
1. Extract ONLY information explicitly supported by the provided text. If a field is missing or ambiguous, return "UNKNOWN" and set evidence_span to "".
2. For every non-UNKNOWN field, copy a SHORT EXACT VERBATIM substring (5 to 120 characters) directly from the document text into `evidence_span` without paraphrasing or fixing typos.
3. Field definitions:
   - case_number: Primary docket number in the caption (e.g., "No. 1332"). Omit term/year suffixes.
   - monetary_judgment_amount: First primary dollar figure >= $50 explicitly stated as an amount awarded, ordered, or disputed (plain numeric string like "25000.0"), else "UNKNOWN".
   - case_category: One of criminal, family, housing_property, civil_contract_tort, administrative_other, UNKNOWN.
   - disposition_outcome: Formal appellate ruling in the closing decretal order:
     * affirmed_in_part_reversed_in_part (both affirmed in part AND reversed/vacated in part)
     * reversed_or_vacated (reversed or vacated, even if also remanded)
     * dismissed (appeal dismissed)
     * affirmed (judgment affirmed)
     * remanded (pure remand without affirmance/reversal)
     * UNKNOWN (unclear)
   - self_represented_flag: "true" if any party appears pro se / in proper person / without counsel; "false" if parties are represented by named counsel/firms/public defender/attorney general; "UNKNOWN" if counsel is omitted.
   - remand_or_procedural_stay_flag: "true" if the court remands for further proceedings, orders a new trial, or stays/continues proceedings; "false" if the ruling ends proceedings without remand/stay; "UNKNOWN" if unclear.
"""


def parse_money_str(raw: str) -> float | str:
    if not raw or raw.upper() == "UNKNOWN":
        return "UNKNOWN"
    try:
        cleaned = raw.replace("$", "").replace(",", "").strip()
        val = float(cleaned)
        return val if val >= 50.0 else "UNKNOWN"
    except ValueError:
        return "UNKNOWN"


def call_gemini_with_retry(
    client: genai.Client, model: str, doc_text: str, max_retries: int = 4
) -> tuple[CourtOrderExtraction, int, int, float]:
    for attempt in range(max_retries):
        t0 = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=model,
                contents=f"Extract structured fields from this Maryland court order:\n\n{doc_text}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=CourtOrderExtraction,
                ),
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            parsed = CourtOrderExtraction.model_validate_json(response.text)
            usage = response.usage_metadata
            in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
            out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
            return parsed, in_tok, out_tok, latency_ms
        except Exception as exc:
            wait_s = 2.5 * (2**attempt)
            if attempt == max_retries - 1:
                raise
            print(f"[warn] Gemini call failed ({exc}); retrying in {wait_s:.1f}s...")
            time.sleep(wait_s)
    raise RuntimeError("Unreachable")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not found. Add it to .env before running.")

    parser = argparse.ArgumentParser(description="Run Gemini structured extraction benchmark.")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
    parser.add_argument("--workers", type=int, default=6, help="Concurrent API workers")
    parser.add_argument("--force", action="store_true", help="Re-run even if cached predictions exist")
    args = parser.parse_args()

    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    test_rows = [r for r in rows if r["split"] == "test"]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, dict] = {}
    if OUT_PATH.exists() and not args.force:
        for line in OUT_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                existing[rec["doc_id"]] = rec
        print(f"[resume] Loaded {len(existing)} cached LLM predictions from {OUT_PATH}")

    client = genai.Client(api_key=api_key)
    lock = threading.Lock()
    results_map: dict[str, dict] = dict(existing)
    todo = [r for r in test_rows if r["doc_id"] not in existing]
    done_count = len(existing)

    def process_one(r: dict) -> dict:
        parsed, in_tok, out_tok, latency_ms = call_gemini_with_retry(client, args.model, r["text"])
        cost_usd = (in_tok / 1_000_000) * INPUT_COST_PER_M + (out_tok / 1_000_000) * OUTPUT_COST_PER_M
        return {
            "doc_id": r["doc_id"],
            "method": "llm_gemini",
            "model": args.model,
            "pred": {
                "case_number": parsed.case_number.value.strip().rstrip(",."),
                "monetary_judgment_amount": parse_money_str(parsed.monetary_judgment_amount.value),
                "case_category": parsed.case_category.value,
                "disposition_outcome": parsed.disposition_outcome.value,
                "self_represented_flag": parsed.self_represented_flag.value,
                "remand_or_procedural_stay_flag": parsed.remand_or_procedural_stay_flag.value,
            },
            "evidence_spans": {
                "case_number": parsed.case_number.evidence_span,
                "monetary_judgment_amount": parsed.monetary_judgment_amount.evidence_span,
                "case_category": parsed.case_category.evidence_span,
                "disposition_outcome": parsed.disposition_outcome.evidence_span,
                "self_represented_flag": parsed.self_represented_flag.evidence_span,
                "remand_or_procedural_stay_flag": parsed.remand_or_procedural_stay_flag.evidence_span,
            },
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "latency_ms": round(latency_ms, 2),
            "cost_usd": round(cost_usd, 6),
        }

    if todo:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(process_one, r) for r in todo]
            for fut in as_completed(futs):
                rec = fut.result()
                with lock:
                    results_map[rec["doc_id"]] = rec
                    done_count += 1
                    with OUT_PATH.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    if done_count % 10 == 0 or done_count == len(test_rows):
                        print(f"[progress] LLM extracted {done_count}/{len(test_rows)} test docs (last latency={rec['latency_ms']:.0f}ms)")

    ordered_results = [results_map[r["doc_id"]] for r in test_rows]
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for rec in ordered_results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[ok] LLM extraction completed on {len(ordered_results)} test docs -> {OUT_PATH}")


if __name__ == "__main__":
    main()
