"""Phase 2 Baseline 2: Classical NLP (spaCy NER/Matcher + TF-IDF Logistic Regression).

Trained strictly on the 20-document `dev` split and evaluated on the 60-document held-out `test` split.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import spacy
from spacy.matcher import Matcher
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = PROJECT_ROOT / "data" / "gold" / "gold_court_orders.jsonl"
OUT_PATH = PROJECT_ROOT / "outputs" / "preds_classical_nlp.jsonl"


def build_spacy_pipeline() -> tuple[spacy.Language, Matcher]:
    nlp = spacy.load("en_core_web_sm")
    matcher = Matcher(nlp.vocab)
    # Match docket identifiers such as 'No. 1332' or 'Nos. 1332'
    matcher.add(
        "DOCKET_NUM",
        [
            [{"TEXT": {"REGEX": r"^Nos?\.?$"}}, {"TEXT": {"REGEX": r"^[0-9]{1,5}(?:[-/][0-9A-Za-z]+)?$"}}],
            [{"TEXT": {"REGEX": r"^Nos?$"}}, {"TEXT": "."}, {"TEXT": {"REGEX": r"^[0-9]{1,5}$"}}],
        ],
    )
    return nlp, matcher


def parse_money_entity(text: str) -> float | None:
    cleaned = text.replace("$", "").replace(",", "").strip().lower()
    mult = 1.0
    if "million" in cleaned:
        mult = 1_000_000.0
        cleaned = cleaned.replace("million", "").strip()
    elif "thousand" in cleaned:
        mult = 1_000.0
        cleaned = cleaned.replace("thousand", "").strip()
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)$", cleaned)
    if not m:
        return None
    val = float(m.group(1)) * mult
    return val if val >= 50.0 else None


def fit_text_classifier(texts: list[str], labels: list[str]) -> Pipeline | str:
    unique = sorted(set(labels))
    if len(unique) < 2:
        return unique[0]
    pipe = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=3000, sublinear_tf=True, stop_words="english")),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", C=2.0, random_state=42)),
        ]
    )
    pipe.fit(texts, labels)
    return pipe


def predict_with_model(model: Pipeline | str, text: str) -> str:
    if isinstance(model, str):
        return model
    return str(model.predict([text])[0])


def main() -> None:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    dev_rows = [r for r in rows if r["split"] == "dev"]
    test_rows = [r for r in rows if r["split"] == "test"]

    nlp, matcher = build_spacy_pipeline()

    # Train separate TF-IDF + Logistic Regression classifiers strictly on dev split
    cat_model = fit_text_classifier([r["text"] for r in dev_rows], [r["gold"]["case_category"] for r in dev_rows])
    disp_model = fit_text_classifier(
        [r["text"][-900:] for r in dev_rows], [r["gold"]["disposition_outcome"] for r in dev_rows]
    )
    prose_model = fit_text_classifier(
        [r["text"][:1000] for r in dev_rows], [r["gold"]["self_represented_flag"] for r in dev_rows]
    )
    remand_model = fit_text_classifier(
        [r["text"][-700:] for r in dev_rows], [r["gold"]["remand_or_procedural_stay_flag"] for r in dev_rows]
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []

    for r in test_rows:
        t0 = time.perf_counter()
        text = r["text"]
        doc = nlp(text)

        # 1. case_number via spaCy token Matcher on header tokens
        header_doc = nlp(text[:800])
        matches = matcher(header_doc)
        if matches:
            _, start, end = matches[0]
            case_number = re.sub(r"\s+", " ", header_doc[start:end].text).strip().rstrip(",.")
            case_number = case_number.replace("No .", "No.").replace("Nos .", "Nos.")
        else:
            case_number = "UNKNOWN"

        # 2. monetary_judgment_amount via spaCy MONEY NER
        monetary: float | str = "UNKNOWN"
        for ent in doc.ents:
            if ent.label_ == "MONEY":
                val = parse_money_entity(ent.text)
                if val is not None:
                    monetary = val
                    break

        # 3-6. Supervised TF-IDF linear classifiers trained on dev split
        pred = {
            "case_number": case_number,
            "monetary_judgment_amount": monetary,
            "case_category": predict_with_model(cat_model, text),
            "disposition_outcome": predict_with_model(disp_model, text[-900:]),
            "self_represented_flag": predict_with_model(prose_model, text[:1000]),
            "remand_or_procedural_stay_flag": predict_with_model(remand_model, text[-700:]),
        }
        latency_ms = (time.perf_counter() - t0) * 1000.0
        outputs.append(
            {
                "doc_id": r["doc_id"],
                "method": "classical_nlp",
                "pred": pred,
                "latency_ms": round(latency_ms, 3),
                "cost_usd": 0.0,
            }
        )

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in outputs:
            f.write(json.dumps(row) + "\n")
    print(f"[ok] Classical NLP baseline completed on {len(outputs)} test docs -> {OUT_PATH}")


if __name__ == "__main__":
    main()
