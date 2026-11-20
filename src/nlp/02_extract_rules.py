"""Phase 2 Baseline 1: Deterministic Regex & Keyword Extractor.

Operates strictly on raw document text (never structured metadata).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = PROJECT_ROOT / "data" / "gold" / "gold_court_orders.jsonl"
OUT_PATH = PROJECT_ROOT / "outputs" / "preds_rules.jsonl"

CATEGORY_KEYWORDS = {
    "criminal": [
        "state of maryland", "convicted", "sentenced", "indictment", "public defender",
        "felony", "misdemeanor", "trial court", "guilty", "jury", "miranda", "suppression",
    ],
    "family": [
        "divorce", "custody", "child support", "alimony", "marital property",
        "parental rights", "cina", "visitation", "best interest of the child",
    ],
    "housing_property": [
        "landlord", "tenant", "eviction", "foreclosure", "deed of trust", "lease",
        "zoning", "easement", "real property", "mortgage", "rent",
    ],
    "civil_contract_tort": [
        "negligence", "breach of contract", "malpractice", "damages", "tort",
        "insurance", "promissory note", "summary judgment", "plaintiff",
    ],
    "administrative_other": [
        "workers' compensation", "administrative", "board of appeals",
        "judicial review", "commissioner", "agency", "comptroller", "motor vehicle",
    ],
}


def extract_rules(text: str) -> dict[str, Any]:
    header = text[:900]
    tail = text[-700:]
    text_l = text.lower()
    tail_l = tail.lower()

    # 1. case_number (structured caption identifier)
    m_num = re.search(r"\b(Nos?\.?\s*[0-9]{1,5}(?:[-/][0-9A-Za-z]+)?)", header)
    case_number = re.sub(r"\s+", " ", m_num.group(1)).strip().rstrip(",.") if m_num else "UNKNOWN"

    # 2. monetary_judgment_amount (simple first dollar figure >= $50)
    m_amt = re.findall(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{2,})(?:\.([0-9]{2}))?", text)
    monetary: float | str = "UNKNOWN"
    for whole, cents in m_amt:
        val = float(whole.replace(",", "") + (f".{cents}" if cents else ""))
        if val >= 50.0:
            monetary = val
            break

    # 3. case_category (highest keyword match count)
    scores = {
        cat: sum(text_l.count(kw) for kw in kws)
        for cat, kws in CATEGORY_KEYWORDS.items()
    }
    best_cat, best_score = max(scores.items(), key=lambda kv: kv[1])
    case_category = best_cat if best_score > 0 else "UNKNOWN"

    # 4. disposition_outcome (simple closing-line keyword scan)
    has_aff = "affirmed" in tail_l
    has_rev = "reversed" in tail_l or "vacated" in tail_l
    has_dis = "dismissed" in tail_l
    has_rem = "remanded" in tail_l
    if has_aff and has_rev:
        disposition = "affirmed_in_part_reversed_in_part"
    elif has_dis and not has_aff and not has_rev:
        disposition = "dismissed"
    elif has_rev:
        disposition = "reversed_or_vacated"
    elif has_aff:
        disposition = "affirmed"
    elif has_rem:
        disposition = "remanded"
    else:
        disposition = "UNKNOWN"

    # 5. self_represented_flag
    header_l = header.lower()
    if any(k in header_l for k in ["pro se", "proper person", "self-represented"]):
        pro_se = "true"
    elif any(k in header_l for k in ["for appellant", "for appellee", "llp", "esq.", "atty. gen."]):
        pro_se = "false"
    else:
        pro_se = "UNKNOWN"

    # 6. remand_or_procedural_stay_flag
    if any(k in tail_l[-450:] for k in ["remand", "new trial", "further proceedings", "stayed"]):
        remand_flag = "true"
    elif disposition != "UNKNOWN":
        remand_flag = "false"
    else:
        remand_flag = "UNKNOWN"

    return {
        "case_number": case_number,
        "monetary_judgment_amount": monetary,
        "case_category": case_category,
        "disposition_outcome": disposition,
        "self_represented_flag": pro_se,
        "remand_or_procedural_stay_flag": remand_flag,
    }


def main() -> None:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    test_rows = [r for r in rows if r["split"] == "test"]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    outputs = []
    for r in test_rows:
        t0 = time.perf_counter()
        pred = extract_rules(r["text"])
        latency_ms = (time.perf_counter() - t0) * 1000.0
        outputs.append(
            {
                "doc_id": r["doc_id"],
                "method": "rules",
                "pred": pred,
                "latency_ms": round(latency_ms, 3),
                "cost_usd": 0.0,
            }
        )

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in outputs:
            f.write(json.dumps(row) + "\n")
    print(f"[ok] Rule-based baseline completed on {len(outputs)} test docs -> {OUT_PATH}")


if __name__ == "__main__":
    main()
