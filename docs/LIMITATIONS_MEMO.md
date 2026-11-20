# Methodological Limitations & Causal Guardrails Memo

This memo documents the data-generating limitations, statistical caveats, cross-jurisdiction reporting inconsistencies, and NLP/OCR failure boundaries observed across the **Open Court Analytics** pipeline. Every finding in this repository is **descriptive and operational** and must not be interpreted as causal proof of judicial, clerk, or landlord behavior.

---

## 1. Administrative Court Data Limitations (Maryland Eviction Warrant Cohort)

### A. Cross-Jurisdiction Reporting Heterogeneity (Critical Finding)
Even within a single state publishing through a unified open-data feed (`mvqb-b4hf`), local clerk and sheriff offices do not log non-eviction return-of-service events uniformly:
* **Baltimore County** logs all four lifecycle outcomes (`Cancelled`: 6,717; `Expired`: 2,281; `Evicted`: 1,119; `Pending`: 5,189).
* **Montgomery County** similarly logs `Cancelled` (1,884), `Expired` (165), `Evicted` (235), and `Pending` (1,100).
* **Prince George's County** logs `Cancelled` (3,654) and `Evicted` (696), but **0 `Expired`** returns.
* **Baltimore City** logs `Evicted` (1,197) and only **61 `Cancelled`** and **0 `Expired`** returns—leaving **13,487 petitions (91.5%)** coded as `Pending`.

**Implication:** Apparent differences in county clearance rates and right-censored survival curves—especially in Baltimore City and in `Public Housing FTPR` (heavily concentrated in Baltimore City)—partly reflect **local case-management logging practices**, not solely physical court backlogs. County fixed effects and county-stratified Cox models absorb jurisdiction-level baseline differences, but raw cross-county clearance comparisons must always be read alongside this caveat.

### B. Left-Truncation and Right-Censoring
* **Left-Truncation (19,716 cases excluded):** Petitions filed prior to the extract window (`2026-04-22`) appear only when their warrant return occurred during Apr–Sep 2026. Because their start date is unobserved, they are audited in `qa_audit_summary` and excluded from `v_analyst_cases` rather than assigned imputed filing dates.
* **Right-Censoring (27,542 open cases; 53.0% of cohort):** Ignoring open petitions creates severe **survivorship bias**—naive closed-case averages report a **46.0-day** median versus the Kaplan–Meier censor-adjusted median of **65.0 days** (+19 days).
* **Mature-Cohort Sensitivity Check:** Re-estimating our clustered logistic regression strictly on petitions filed at least 60 days prior to extract cutoff (`n = 31,451`) confirms the direction and magnitude of all core predictors (e.g., `batch_efiler` OR = 0.599 vs. 0.579 in full cohort; `Wrongful Detainer` OR = 6.51 vs. 6.01).

### C. Impossible Dates & Clerk Data Hygiene
* **9 cases** exhibited `disposition_date < filing_date` (typically reopened warrants or back-dated clerk entries) and were excluded from `v_analyst_cases`.
* **7 raw rows** required whitespace normalization on `casenumber` (e.g., `22- 313632` → `22-313632`).

### D. Missing Covariates & Causal Guardrails
* **Tenant Representation Not Reported:** The public Maryland eviction extract does not report whether tenants had legal counsel. Our `batch_efiler_flag` (derived from institutional e-filing vendor prefixes such as `EWRIT::`, `HENWEB::`, `KANE::` in `eventcomment`) identifies high-volume corporate/institutional plaintiff filers, **not** individual tenant legal representation.
* **Unobserved Confounders:** Administrative dockets omit rent arrears amounts, landlord redemption policies, informal out-of-court payment plans, emergency rental assistance timing, and local sheriff scheduling capacity. Consequently, our regression odds ratios (e.g., institutional batch e-filers showing lower executed-eviction odds, OR = 0.58) reflect **observational filing-to-execution patterns** (such as high-volume serial filings later redeemed/cancelled), not causal effects of e-filing software.

---

## 2. Privacy & Re-Identification Controls
* Downstream analytics query **only** `v_analyst_cases` (salted SHA-256 `case_id_hash`, raw city/5-digit ZIP removed, coarsened to 3-digit `tenant_zip3`).
* Public county and monthly exports enforce **small-cell suppression (`< 10` cases)**, automatically suppressing 38 county-category cells and Garrett County's closed-case median (`n_closed = 7`).
* In production deployments with non-public court records, **sealed, expunged, juvenile, and domestic-violence dockets** must be stripped upstream prior to warehouse ingestion and never transmitted to external commercial LLM APIs.

---

## 3. Unstructured Document Extraction & OCR Limitations (Maryland CAP Benchmark)
* **Domain Generalization:** The Phase 2 extraction benchmark evaluates **80 published Maryland appellate opinions** (`static.case.law/md-app/`). Published appellate decisions are cleaner, longer, and far more likely to involve represented counsel (only 1 of 80 sampled appellate orders was *pro se*) than high-volume trial-court filings, handwritten small-claims orders, or scanned sheriff returns.
* **OCR Noise Sensitivity:** 55 of the 80 sampled documents exhibited measurable legacy scan/OCR artifacts (stray punctuation, broken hyphens, character substitutions). Accuracy on clean digital PDFs overstates performance on low-resolution court scans; pre-deployment pipelines require an upstream OCR quality gate.
* **Context Truncation:** Excerpts capture the caption, opening 1,800 characters, and closing decretal window around the formal judgment order (avoiding CAP's trailing endnotes). Multi-issue opinions with monetary awards buried mid-opinion can be missed without full-document chunking.
* **Hallucination & Abstention Risk:** Even at `temperature = 0` with strict JSON schemas, LLMs can confuse *requested damages* with *awarded judgments* or paraphrase quotes. Requiring verbatim `evidence_span` verification and explicit `UNKNOWN` abstention mitigates silent fabrication, but does not replace human clerk review for binding court records.
