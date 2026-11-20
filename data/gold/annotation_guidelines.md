# Gold Dataset Annotation Guidelines — Maryland State Court Orders

## Corpus Source
Real Maryland state appellate court decisions retrieved from the **Harvard Caselaw Access Project (CAP)** static archive (`static.case.law/md-app/`, volumes 201–207, Court of Special Appeals of Maryland). Each document input presented to extraction models is a standardized raw-text excerpt combining:
1. The full caption and counsel block (`head_matter`)
2. The opening procedural summary (first ~1,800 characters of the opinion)
3. The closing holding and decretal order (last ~2,200 characters of the opinion)

Extraction models receive **only** this raw text excerpt—never structured CAP metadata.

---

## Extraction Fields & Labeling Rules

| Field | Type / Allowed Values | Labeling Rule & `UNKNOWN` Policy |
| :--- | :--- | :--- |
| `case_number` | `string` or `"UNKNOWN"` | Primary docket number printed in the caption (e.g., `No. 1332`, `No. 0456`, `No. 2411`). Normalize extra whitespace; omit term/year suffixes (`Sept. Term, 2009`). Return `"UNKNOWN"` if no docket number appears in the text. |
| `monetary_judgment_amount` | `float` or `"UNKNOWN"` | Primary dollar amount explicitly awarded, ordered, or disputed as a judgment/damages/fee figure in the excerpt (numeric USD value, e.g., `25000.0`). Return `"UNKNOWN"` for non-monetary orders or when no concrete dollar figure appears. |
| `case_category` | `criminal`, `family`, `housing_property`, `civil_contract_tort`, `administrative_other`, `"UNKNOWN"` | Primary legal subject of the case: `criminal` (State prosecutions, convictions, sentencing, post-conviction), `family` (divorce, custody, child support, alimony, guardianship/CINA), `housing_property` (landlord-tenant, foreclosure, real property, zoning, easements), `civil_contract_tort` (negligence, malpractice, contracts, debt, insurance), `administrative_other` (agency appeals, workers' comp, licensing, tax). |
| `disposition_outcome` | `affirmed`, `reversed_or_vacated`, `remanded`, `dismissed`, `affirmed_in_part_reversed_in_part`, `"UNKNOWN"` | Formal ruling in the decretal order. Use `affirmed_in_part_reversed_in_part` when the court explicitly affirms part and reverses/vacates part; use `reversed_or_vacated` for full reversals or vacaturs (even if also remanded); use `remanded` only for pure remands without affirmance/reversal; use `dismissed` when the appeal or petition is dismissed. |
| `self_represented_flag` | `"true"`, `"false"`, `"UNKNOWN"` | `"true"` if any party is explicitly noted as appearing *pro se*, *in proper person*, or without counsel; `"false"` if all appearing parties are represented by named attorneys/firms/public counsel; `"UNKNOWN"` if counsel information is absent or illegible. |
| `remand_or_procedural_stay_flag` | `"true"`, `"false"`, `"UNKNOWN"` | `"true"` if the order remands for further proceedings, grants a stay, or orders a continuance/new trial; `"false"` if the ruling terminates proceedings without remand/stay; `"UNKNOWN"` if the decretal disposition is missing or ambiguous. |

---

## Text Quality Tag (`clean` vs. `noisy_ocr`)

Each document in `gold_court_orders.jsonl` is tagged with `text_quality`:
- **`noisy_ocr`**: Documents exhibiting measurable optical character recognition (OCR) artifacts common in scanned court reporters (e.g., repeated stray punctuation such as `,,` or `..`, broken word hyphens, stray non-ASCII/digit substitutions inside words, or malformed whitespace/ligature errors).
- **`clean`**: Documents with low/zero measurable OCR noise in the excerpt.

---

## Splits & Evaluation Protocol

- **`dev` split (20 documents):** Used for crafting regex patterns, fitting classical NLP models, and tuning LLM prompts.
- **`test` split (60 documents):** Strictly held out until final benchmark evaluation (`05_evaluate_benchmark.py`).
- **Evidence verification (LLM):** Every non-`UNKNOWN` prediction must include a verbatim `evidence_span` quote from the document text. Quotes not present in normalized source text are counted as unsupported/hallucinated claims.
