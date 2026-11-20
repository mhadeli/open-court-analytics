"""Phase 2 Evaluation: Score Rules vs. Classical NLP vs. LLM on held-out test set.

Computes per-field Precision, Recall, Macro-F1, Abstention Rate (% UNKNOWN),
Unsupported Claim / Hallucination Rate (verbatim evidence_span verification),
Clean vs. Noisy-OCR F1 drop, Median Latency, and Cost per 1,000 docs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = PROJECT_ROOT / "data" / "gold" / "gold_court_orders.jsonl"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

FIELDS = [
    "case_number",
    "monetary_judgment_amount",
    "case_category",
    "disposition_outcome",
    "self_represented_flag",
    "remand_or_procedural_stay_flag",
]

METHOD_FILES = {
    "rules": OUTPUTS_DIR / "preds_rules.jsonl",
    "classical_nlp": OUTPUTS_DIR / "preds_classical_nlp.jsonl",
    "llm_gemini": OUTPUTS_DIR / "preds_llm.jsonl",
}


def norm_str(val: Any) -> str:
    return re.sub(r"\s+", " ", str(val)).strip().lower()


def norm_docket(val: Any) -> str:
    s = norm_str(val)
    if s == "unknown":
        return "unknown"
    # Normalize minor punctuation ('no. 1332' == 'no 1332')
    return re.sub(r"[^a-z0-9]", "", s.replace("nos", "no"))


def is_field_match(field: str, gold_val: Any, pred_val: Any) -> bool:
    if field == "case_number":
        return norm_docket(gold_val) == norm_docket(pred_val)
    if field == "monetary_judgment_amount":
        g_unk = norm_str(gold_val) == "unknown"
        p_unk = norm_str(pred_val) == "unknown"
        if g_unk and p_unk:
            return True
        if g_unk or p_unk:
            return False
        try:
            g_f, p_f = float(gold_val), float(pred_val)
            return abs(g_f - p_f) <= max(1.0, 0.01 * abs(g_f))
        except (ValueError, TypeError):
            return False
    return norm_str(gold_val) == norm_str(pred_val)


def evidence_supported(source_text: str, span: str) -> bool:
    if not span or not span.strip():
        return False
    norm_src = re.sub(r"\s+", " ", source_text).lower()
    norm_sp = re.sub(r"\s+", " ", span).strip().strip('"').strip("'").lower()
    if len(norm_sp) < 3:
        return False
    if norm_sp in norm_src:
        return True
    # Allow minor punctuation normalization (smart quotes / OCR dashes)
    src_alnum = re.sub(r"[^a-z0-9 ]", "", norm_src)
    sp_alnum = re.sub(r"[^a-z0-9 ]", "", norm_sp)
    return bool(sp_alnum) and sp_alnum in src_alnum


def compute_field_metrics(field: str, test_rows: list[dict], pred_map: dict[str, dict]) -> dict[str, Any]:
    golds = [r["gold"][field] for r in test_rows]
    preds = [pred_map[r["doc_id"]]["pred"][field] for r in test_rows]

    abstention_rate = sum(norm_str(p) == "unknown" for p in preds) / len(preds)

    if field in ("case_number", "monetary_judgment_amount"):
        # Entity extraction precision / recall / F1 (TP = non-UNKNOWN match)
        tp = fp = fn = 0
        for g, p in zip(golds, preds):
            g_unk = norm_str(g) == "unknown"
            p_unk = norm_str(p) == "unknown"
            if not g_unk and not p_unk and is_field_match(field, g, p):
                tp += 1
            elif not p_unk and (g_unk or not is_field_match(field, g, p)):
                fp += 1
                if not g_unk:
                    fn += 1
            elif not g_unk and p_unk:
                fn += 1
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    else:
        y_true = [norm_str(g) for g in golds]
        y_pred = [norm_str(p) for p in preds]
        labels = sorted(set(y_true))
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=labels, average="macro", zero_division=0
        )

    exact_acc = sum(is_field_match(field, g, p) for g, p in zip(golds, preds)) / len(golds)

    # Clean vs. Noisy-OCR exact accuracy breakdown
    clean_matches = [
        is_field_match(field, r["gold"][field], pred_map[r["doc_id"]]["pred"][field])
        for r in test_rows
        if r["text_quality"] == "clean"
    ]
    noisy_matches = [
        is_field_match(field, r["gold"][field], pred_map[r["doc_id"]]["pred"][field])
        for r in test_rows
        if r["text_quality"] == "noisy_ocr"
    ]
    clean_acc = float(np.mean(clean_matches)) if clean_matches else np.nan
    noisy_acc = float(np.mean(noisy_matches)) if noisy_matches else np.nan

    # Hallucination / unsupported claim audit (for LLM predictions with evidence_spans)
    non_unk_checked = 0
    unsupported = 0
    for r in test_rows:
        pred_rec = pred_map[r["doc_id"]]
        if "evidence_spans" not in pred_rec:
            continue
        p_val = pred_rec["pred"][field]
        if norm_str(p_val) != "unknown":
            non_unk_checked += 1
            span = pred_rec["evidence_spans"].get(field, "")
            if not evidence_supported(r["text"], span):
                unsupported += 1
    halluc_rate = (unsupported / non_unk_checked) if non_unk_checked > 0 else np.nan

    return {
        "field": field,
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "macro_f1": round(float(f1), 4),
        "exact_accuracy": round(float(exact_acc), 4),
        "abstention_rate": round(float(abstention_rate), 4),
        "unsupported_claim_rate": round(float(halluc_rate), 4) if not np.isnan(halluc_rate) else np.nan,
        "clean_accuracy": round(clean_acc, 4) if not np.isnan(clean_acc) else np.nan,
        "noisy_ocr_accuracy": round(noisy_acc, 4) if not np.isnan(noisy_acc) else np.nan,
        "ocr_accuracy_drop": round(clean_acc - noisy_acc, 4)
        if not (np.isnan(clean_acc) or np.isnan(noisy_acc))
        else np.nan,
    }


def build_error_taxonomy(
    test_rows: list[dict], all_preds: dict[str, dict[str, dict]], metrics_df: pd.DataFrame
) -> str:
    lines = [
        "# Extraction Error Taxonomy (Held-Out Test Set, n = 60 Maryland Court Orders)",
        "",
        "Concrete error patterns observed across all three extraction methods on the identical 60-document held-out test set.",
        "",
        "## Headline Performance Comparison (Averaged Across 6 Fields)",
        "",
    ]
    summary = (
        metrics_df.groupby("method", as_index=False)
        .agg(
            mean_precision=("precision", "mean"),
            mean_recall=("recall", "mean"),
            mean_macro_f1=("macro_f1", "mean"),
            mean_exact_acc=("exact_accuracy", "mean"),
            median_latency_ms=("median_latency_ms", "first"),
            cost_per_1k_usd=("cost_per_1k_usd", "first"),
        )
        .round(4)
    )
    cols = list(summary.columns)
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in summary.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    lines.append("")

    for method, pred_map in all_preds.items():
        lines.append(f"## Method: `{method}` — Sample Failure Cases")
        lines.append("")
        shown = 0
        for field in FIELDS:
            mismatches = []
            for r in test_rows:
                g = r["gold"][field]
                p = pred_map[r["doc_id"]]["pred"][field]
                if not is_field_match(field, g, p):
                    mismatches.append((r, g, p, pred_map[r["doc_id"]].get("evidence_spans", {}).get(field, "")))
            if not mismatches:
                lines.append(f"- **`{field}`**: 0 errors on the held-out test set.")
                continue
            lines.append(f"- **`{field}`** ({len(mismatches)}/{len(test_rows)} mismatches):")
            for r, g, p, span in mismatches[:2]:
                extra = f" | evidence_span: `{span[:80]}`" if span else ""
                lines.append(
                    f"  - `{r['doc_id']}` ({r['text_quality']}): gold=`{g}`, pred=`{p}`{extra}"
                )
                shown += 1
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    test_rows = [r for r in rows if r["split"] == "test"]
    print(f"Evaluating on {len(test_rows)} held-out test court orders...")

    all_preds: dict[str, dict[str, dict]] = {}
    metric_rows: list[dict[str, Any]] = []

    for method, path in METHOD_FILES.items():
        if not path.exists():
            print(f"[warn] Missing predictions file for {method}: {path}")
            continue
        recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        pred_map = {rec["doc_id"]: rec for rec in recs}
        all_preds[method] = pred_map

        latencies = [rec["latency_ms"] for rec in recs]
        costs = [rec.get("cost_usd", 0.0) for rec in recs]
        med_lat = round(float(np.median(latencies)), 2)
        cost_1k = round(float(np.mean(costs)) * 1000.0, 4)

        for field in FIELDS:
            row = compute_field_metrics(field, test_rows, pred_map)
            row["method"] = method
            row["median_latency_ms"] = med_lat
            row["cost_per_1k_usd"] = cost_1k
            metric_rows.append(row)

    metrics_df = pd.DataFrame(metric_rows)[
        [
            "method",
            "field",
            "precision",
            "recall",
            "macro_f1",
            "exact_accuracy",
            "abstention_rate",
            "unsupported_claim_rate",
            "clean_accuracy",
            "noisy_ocr_accuracy",
            "ocr_accuracy_drop",
            "median_latency_ms",
            "cost_per_1k_usd",
        ]
    ]
    metrics_df.to_csv(OUTPUTS_DIR / "benchmark_metrics.csv", index=False)

    taxonomy_md = build_error_taxonomy(test_rows, all_preds, metrics_df)
    (OUTPUTS_DIR / "error_taxonomy.md").write_text(taxonomy_md, encoding="utf-8")

    print("\n=== Phase 2 Per-Field Extraction Benchmark ===")
    print(metrics_df.to_string(index=False))
    print(f"\n[ok] Wrote {OUTPUTS_DIR / 'benchmark_metrics.csv'} and {OUTPUTS_DIR / 'error_taxonomy.md'}")


if __name__ == "__main__":
    main()
