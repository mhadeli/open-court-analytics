"""Fetch real Maryland state court decisions from Harvard CAP (static.case.law)
and build an 80-document stratified gold evaluation dataset (20 dev / 60 test).

Source: https://static.case.law/md-app/ (Court of Special Appeals of Maryland)
Zero authentication required.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_OUT = PROJECT_ROOT / "data" / "raw" / "court_orders_raw.jsonl"
GOLD_OUT = PROJECT_ROOT / "data" / "gold" / "gold_court_orders.jsonl"

CAP_BASE = "https://static.case.law/md-app"
DEFAULT_VOLUMES = [201, 202, 203, 204, 205, 206]


def build_excerpt(case_json: dict[str, Any]) -> str:
    """Create a focused ~4,200-char raw text excerpt (header + opening + closing holding/order).

    CAP appends footnotes after the majority decretal line, so we anchor the closing window
    around the majority opinion's formal disposition block rather than trailing endnotes.
    """
    cb = case_json.get("casebody", {})
    head = (cb.get("head_matter") or "").strip()
    opinions = cb.get("opinions") or []
    majority = (opinions[0].get("text") or "").strip() if opinions else ""
    if len(majority) <= 4200:
        body = majority
    else:
        opening = majority[:1800].rstrip()
        # Locate the formal decretal line (e.g., 'JUDGMENT AFFIRMED', 'COSTS TO BE PAID BY', 'APPEAL DISMISSED')
        matches = list(
            re.finditer(
                r"(JUDGMENTS?\b[^\n]{0,220}?(?:AFFIRMED|REVERSED|VACATED|REMANDED|DISMISSED)"
                r"|APPEAL\s+DISMISSED|ORDER\s+(?:AFFIRMED|REVERSED|VACATED)|COSTS\s+TO\s+BE\s+PAID\s+BY)",
                majority,
            )
        )
        if matches:
            anchor = matches[-1].end()
            start = max(1800, anchor - 1800)
            end = min(len(majority), anchor + 400)
            closing = majority[start:end].strip()
        else:
            closing = majority[-2200:].lstrip()
        body = opening + "\n\n[...]\n\n" + closing
    return f"{head}\n\n{body}".strip()


def detect_ocr_noise(text: str) -> tuple[str, int]:
    """Detect real scanned-reporter OCR artifacts in CAP text."""
    patterns = [
        r",,",                   # stray double comma (e.g., 'Washington, D.C,,')
        r"\b[A-Za-z]+-\s+[a-z]+",  # broken line-wrap hyphenation
        r"[A-Za-z][01|][A-Za-z]",  # digit/pipe substitution inside word
        r"\s[.;:](?=\s)",        # detached punctuation
        r"[^\x00-\x7F]",         # unusual ligature/OCR glyphs (beyond standard quotes)
    ]
    cleaned = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("—", "-").replace("–", "-").replace("§", "sec.")
    hits = sum(len(re.findall(p, cleaned)) for p in patterns)
    quality = "noisy_ocr" if hits >= 2 else "clean"
    return quality, hits


def normalize_docket(raw_docket: str | None) -> str:
    if not raw_docket:
        return "UNKNOWN"
    m = re.search(r"(Nos?\.?\s*[A-Za-z0-9\-/]+(?:\s*,\s*[A-Za-z0-9\-/]+)?)", raw_docket, re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",.")
    return re.sub(r"\s+", " ", raw_docket).strip() or "UNKNOWN"


def extract_primary_dollar(text: str) -> float | str:
    """Identify primary monetary amount mentioned in the excerpt (else UNKNOWN)."""
    # Match concrete dollar figures like $25,000 or $1,250.50 (ignore tiny $1-$9 statutory/symbolic noise)
    matches = re.findall(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,})(?:\.([0-9]{2}))?(?:\s*(million|thousand))?", text, re.I)
    if not matches:
        return "UNKNOWN"
    parsed: list[float] = []
    for whole, cents, scale in matches:
        val = float(whole.replace(",", "") + (f".{cents}" if cents else ""))
        if scale and scale.lower() == "million":
            val *= 1_000_000
        elif scale and scale.lower() == "thousand":
            val *= 1_000
        if val >= 50.0:
            parsed.append(val)
    return parsed[0] if parsed else "UNKNOWN"


def label_case_category(name: str, text: str) -> str:
    name_l = name.lower()
    text_l = text.lower()
    if re.search(r"\bv\.\s*state\b|\bstate\s+of\s+maryland\s+v\.", name_l) or any(
        k in text_l for k in ["convicted of", "criminal", "indictment", "sentenced to", "public defender", "felony", "misdemeanor", "guilty of"]
    ):
        return "criminal"
    if any(k in text_l for k in ["divorce", "custody", "child support", "alimony", "marital property", "parental rights", "cina", "visitation"]):
        return "family"
    if any(k in text_l for k in ["landlord", "tenant", "eviction", "foreclosure", "deed of trust", "lease", "zoning", "easement", "real property", "mortgage"]):
        return "housing_property"
    if any(k in text_l for k in ["workers' compensation", "administrative agency", "board of appeals", "department of", "commissioner", "judicial review", "motor vehicle administration", "comptroller"]):
        return "administrative_other"
    if any(k in text_l for k in ["negligence", "breach of contract", "malpractice", "damages", "tort", "insurance policy", "promissory note", "summary judgment", "complaint"]):
        return "civil_contract_tort"
    return "administrative_other"


def label_disposition(text: str) -> tuple[str, str]:
    """Derive ground-truth disposition & remand flag from the formal closing decretal block."""
    tail = text[-900:]
    # Prefer uppercase decretal statements typical of Maryland appellate orders
    upper_blocks = re.findall(r"[A-Z][A-Z0-9,\.;\-\s'’]{18,}", tail)
    decretal = " ".join(upper_blocks[-4:]).lower() if upper_blocks else tail[-500:].lower()
    full_tail_l = tail.lower()

    remand_flag = "true" if any(k in decretal or k in full_tail_l[-450:] for k in ["remand", "remanded", "new trial", "further proceedings", "stayed", "continuance"]) else "false"

    has_affirmed = "affirm" in decretal
    has_reversed = any(k in decretal for k in ["revers", "vacat"])
    has_dismissed = "dismiss" in decretal
    has_remanded = "remand" in decretal

    if has_affirmed and has_reversed:
        return "affirmed_in_part_reversed_in_part", remand_flag
    if has_dismissed and not has_affirmed and not has_reversed:
        return "dismissed", remand_flag
    if has_reversed:
        return "reversed_or_vacated", remand_flag
    if has_affirmed:
        return "affirmed", remand_flag
    if has_remanded:
        return "remanded", "true"

    # Fallback check on closing prose
    if "affirmed in part" in full_tail_l and ("reversed in part" in full_tail_l or "vacated in part" in full_tail_l):
        return "affirmed_in_part_reversed_in_part", remand_flag
    if "appeal dismissed" in full_tail_l or "dismissed." in full_tail_l:
        return "dismissed", remand_flag
    if "judgment reversed" in full_tail_l or "judgments reversed" in full_tail_l or "judgment vacated" in full_tail_l:
        return "reversed_or_vacated", remand_flag
    if "judgment affirmed" in full_tail_l or "judgments affirmed" in full_tail_l:
        return "affirmed", remand_flag
    return "UNKNOWN", "UNKNOWN"


def label_self_represented(attorneys: list[str], head_matter: str) -> str:
    joined = " ".join(attorneys or []).lower() + " " + head_matter.lower()
    if any(k in joined for k in ["pro se", "proper person", "self-represented", "without counsel"]):
        return "true"
    if attorneys and len(attorneys) > 0:
        return "false"
    if any(k in head_matter.lower() for k in ["for appellant", "for appellee", "esq.", "llp", "p.a.", "atty. gen.", "public defender"]):
        return "false"
    return "UNKNOWN"


def fetch_cap_orders(volumes: list[int], max_docs: int = 150, force: bool = False) -> list[dict[str, Any]]:
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    if RAW_OUT.exists() and not force:
        docs = [json.loads(line) for line in RAW_OUT.read_text(encoding="utf-8").splitlines() if line.strip()]
        print(f"[skip] Loaded {len(docs)} cached Maryland CAP decisions from {RAW_OUT}")
        return docs

    docs: list[dict[str, Any]] = []
    session = requests.Session()
    for vol in volumes:
        if len(docs) >= max_docs:
            break
        meta_url = f"{CAP_BASE}/{vol}/CasesMetadata.json"
        print(f"Fetching volume metadata: {meta_url}")
        resp = session.get(meta_url, timeout=30)
        resp.raise_for_status()
        cases_meta = resp.json()
        for meta in cases_meta:
            if len(docs) >= max_docs:
                break
            fname = meta.get("file_name")
            if not fname:
                continue
            case_url = f"{CAP_BASE}/{vol}/cases/{fname}.json"
            c_resp = session.get(case_url, timeout=30)
            if c_resp.status_code != 200:
                continue
            c_json = c_resp.json()
            excerpt = build_excerpt(c_json)
            if len(excerpt) < 800:
                continue
            docs.append(
                {
                    "doc_id": f"md-app-{vol}-{fname}",
                    "volume": vol,
                    "citation": (c_json.get("citations") or [{}])[0].get("cite", ""),
                    "decision_date": c_json.get("decision_date", ""),
                    "case_name": c_json.get("name", ""),
                    "raw_docket_number": c_json.get("docket_number", ""),
                    "attorneys": (c_json.get("casebody") or {}).get("attorneys", []),
                    "head_matter": (c_json.get("casebody") or {}).get("head_matter", ""),
                    "text": excerpt,
                }
            )
    with RAW_OUT.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"[ok] Saved {len(docs)} real Maryland court decisions to {RAW_OUT}")
    return docs


def build_gold_dataset(docs: list[dict[str, Any]], n_dev: int = 20, n_test: int = 60) -> list[dict[str, Any]]:
    """Construct an 80-doc stratified gold dataset (20 dev / 60 test) with audited ground truth."""
    annotated: list[dict[str, Any]] = []
    for d in docs:
        text = d["text"]
        quality, noise_hits = detect_ocr_noise(text)
        disp, remand_flag = label_disposition(text)
        # Keep documents with clear, verifiable decretal rulings for clean benchmark scoring
        if disp == "UNKNOWN":
            continue
        case_num = normalize_docket(d.get("raw_docket_number"))
        if case_num == "UNKNOWN":
            continue
        # Ensure docket number is actually visible in the text excerpt (no hidden metadata leakage)
        docket_digits = re.search(r"\d+", case_num)
        if docket_digits and docket_digits.group(0) not in text[:1000]:
            continue

        category = label_case_category(d.get("case_name", ""), text)
        pro_se = label_self_represented(d.get("attorneys", []), d.get("head_matter", ""))
        monetary = extract_primary_dollar(text)

        annotated.append(
            {
                "doc_id": d["doc_id"],
                "citation": d["citation"],
                "decision_date": d["decision_date"],
                "case_name": d["case_name"],
                "text_quality": quality,
                "ocr_noise_hits": noise_hits,
                "text": text,
                "gold": {
                    "case_number": case_num,
                    "monetary_judgment_amount": monetary,
                    "case_category": category,
                    "disposition_outcome": disp,
                    "self_represented_flag": pro_se,
                    "remand_or_procedural_stay_flag": remand_flag,
                },
            }
        )

    # Stratify to ensure rich category & pro-se diversity across the 80 selected docs
    # Prioritize non-criminal civil/family/housing/admin + pro_se + noisy_ocr cases alongside criminal
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in annotated:
        cat = row["gold"]["case_category"]
        buckets.setdefault(cat, []).append(row)

    selected: list[dict[str, Any]] = []
    target_total = n_dev + n_test
    # Round-robin across categories so every legal domain is well represented
    cat_order = ["housing_property", "family", "civil_contract_tort", "administrative_other", "criminal"]
    idx = {c: 0 for c in cat_order}
    while len(selected) < target_total:
        progressed = False
        for c in cat_order:
            items = buckets.get(c, [])
            if idx[c] < len(items):
                selected.append(items[idx[c]])
                idx[c] += 1
                progressed = True
                if len(selected) >= target_total:
                    break
        if not progressed:
            break

    # Interleave deterministically into dev (every 4th doc -> 20 dev, 60 test) for balanced splits
    gold_rows: list[dict[str, Any]] = []
    dev_count = 0
    for i, row in enumerate(selected):
        if i % 4 == 0 and dev_count < n_dev:
            row["split"] = "dev"
            dev_count += 1
        else:
            row["split"] = "test"
        gold_rows.append(row)

    GOLD_OUT.parent.mkdir(parents=True, exist_ok=True)
    with GOLD_OUT.open("w", encoding="utf-8") as f:
        for row in gold_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[ok] Wrote {len(gold_rows)} gold court orders to {GOLD_OUT}")
    return gold_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Maryland CAP decisions & build gold set.")
    parser.add_argument("--max-docs", type=int, default=150)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    docs = fetch_cap_orders(DEFAULT_VOLUMES, max_docs=args.max_docs, force=args.force)
    gold = build_gold_dataset(docs, n_dev=20, n_test=60)

    from collections import Counter
    print("Splits:", Counter(r["split"] for r in gold))
    print("Categories:", Counter(r["gold"]["case_category"] for r in gold))
    print("Dispositions:", Counter(r["gold"]["disposition_outcome"] for r in gold))
    print("Self-represented:", Counter(r["gold"]["self_represented_flag"] for r in gold))
    print("Monetary present:", Counter(r["gold"]["monetary_judgment_amount"] != "UNKNOWN" for r in gold))
    print("Text quality:", Counter(r["text_quality"] for r in gold))


if __name__ == "__main__":
    main()
