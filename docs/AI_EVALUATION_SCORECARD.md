# Pre-Deployment AI Readiness Scorecard (Non-Technical Decision Guide)

**Evaluated Corpus:** 60 held-out Maryland state court orders (`static.case.law/md-app/`, 16 clean digital / 44 legacy OCR scans)  
**Methods Benchmarked:** Deterministic Rules (`regex`) vs. Classical NLP (`spaCy` + `TF-IDF`) vs. Structured LLM (`gemini-3.8-flash`, `temperature = 0`, mandatory `UNKNOWN` abstention + verbatim source quote verification)

---

## Executive Takeaway for Court Administrators

**Do not deploy an LLM everywhere—use a hybrid pipeline.**  
Across six judicial extraction fields, deterministic rules delivered **near-identical average F1 (0.871 vs. 0.862)** at **0.15 ms/document and \$0.00 cost**, compared to **6,968 ms/document and \$0.39 per 1,000 documents** for the LLM. The LLM earned its cost **only on nuanced, non-boilerplate legal semantics** (e.g., detecting remands/procedural stays: **+24.5 Macro-F1 points** over rules, with minimal OCR degradation).

---

## Traffic-Light Deployment Matrix by Field

| Status | Extraction Field | Recommended Engine | Held-Out Performance | Operational Guidance |
| :---: | :--- | :--- | :--- | :--- |
| **GREEN** | `case_number` (Docket ID) | **Deterministic Regex** (fallback LLM on multi-docket captions) | Rules: **0.950 F1** (0.15 ms, \$0)<br>LLM: **0.983 F1** (6.97 s, \$0.39/1k) | Safe for automated intake indexing. Add a simple multi-docket rule (`Nos. A, B`) to close the 3% gap without paying LLM latency. |
| **GREEN** | `disposition_outcome` (Standard Appellate Decretals) | **Deterministic Rules** + LLM exception routing | Rules: **1.000 F1**<br>LLM: **0.964 F1** | Safe to automate when court orders use standardized closing disposition headers. Route non-standard or trial-court prose orders to Yellow. |
| **YELLOW** | `remand_or_procedural_stay_flag` | **LLM (`UNKNOWN` + Quote Check)** + Clerk Spot-Audit | LLM: **0.983 F1** (2.3% OCR drop)<br>Rules: **0.738 F1** (12.5% OCR drop) | Strong candidate for **human-in-the-loop triage**. Require verbatim quote highlighting so clerks verify remands in seconds. |
| **YELLOW** | `case_category` (Subject Taxonomy) | **LLM (`UNKNOWN` + Quote Check)** + Human Review on Disputes | LLM: **0.744 F1** (76.7% acc)<br>Rules: **0.647 F1**<br>Classical NLP: **0.101 F1** | Suitable for draft routing/tagging only. Real cases frequently straddle categories (e.g., real-estate line-of-credit breach); publish explicit tie-break rules. |
| **YELLOW** | `self_represented_flag` (*Pro Se* Indicator) | **Structured Counsel Parser** + Clerk Verification | Rules: **1.000 F1**<br>LLM: **0.737 F1** (95.0% acc) | High false-positive risk when LLMs read solo practitioners lacking a firm name as *pro se*. Always cross-check against bar-number/CMS attorney tables. |
| **RED** | `monetary_judgment_amount` (Financial Awards) | **Do Not Automate Binding Entry** (Assistive Highlight Only) | `spaCy`: **0.909 F1** (1.00 prec)<br>Rules: **0.889 F1** (missed "million")<br>LLM: **0.759 F1** (81.7% abstention) | **Never auto-post dollar judgments to dockets.** Rules dropped unit multipliers (`$147 million` → `$147`); LLM abstained on 39% of real amounts. Use only to surface candidate dollar spans for clerk entry. |

---

## Reliability, Cost & Risk Summary

| Metric | Rules (`regex`) | Classical NLP (`spaCy` + `TF-IDF`) | Structured LLM (`gemini-3.8-flash`) |
| :--- | :---: | :---: | :---: |
| **Mean Macro-F1 (6 Fields)** | **0.871** | 0.499 | 0.862 |
| **Mean Exact Accuracy** | 89.7% | 68.9% | **92.2%** |
| **Median Latency / Doc** | **0.15 ms** | 80.9 ms | 6,968 ms |
| **Estimated Cost / 1,000 Docs** | **\$0.00** | **\$0.00** | \$0.39 |
| **Unsupported Quote Rate (Hallucination)** | N/A | N/A | **0.0%** *(all quotes verified verbatim)* |
| **Worst OCR Accuracy Drop** | 12.5% (`remand`) | 20.5% (`remand`) | **7.4%** (`monetary`) |

---

## Pre-Deployment Operational Safeguards Checklist

Before moving any document-extraction workflow into a live court environment, require sign-off on all five controls:

1. **Privacy & Data Residency Gate:** Block sealed, expunged, juvenile, and domestic-violence filings upstream. Never send restricted PII or non-public filings to consumer APIs without a zero-data-retention government/enterprise agreement or on-premise model.
2. **Mandatory Abstention & Citation Verification:** Require models to output `UNKNOWN` when evidence is ambiguous and return a verbatim `evidence_span` verified programmatically against source text before surfacing any prediction to staff.
3. **Upstream OCR Quality Gate:** Flag low-confidence scans automatically; route documents below an OCR character-confidence threshold directly to manual clerk review instead of automated extraction.
4. **Periodic Drift & Calibration Audits:** Re-score a stratified random sample of 50–100 new filings every quarter (and after any model version update or court form redesign).
5. **Language-Access & Trial-Court Validation:** This benchmark reflects English-language published appellate opinions. Before serving self-represented litigants or non-English notices (e.g., Spanish), run dedicated bilingual accuracy and plain-language safety benchmarks.
