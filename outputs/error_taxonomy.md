# Extraction Error Taxonomy (Held-Out Test Set, n = 60 Maryland Court Orders)

Concrete error patterns observed across all three extraction methods on the identical 60-document held-out test set.

## Headline Performance Comparison (Averaged Across 6 Fields)

| method | mean_precision | mean_recall | mean_macro_f1 | mean_exact_acc | median_latency_ms | cost_per_1k_usd |
| --- | --- | --- | --- | --- | --- | --- |
| classical_nlp | 0.5145 | 0.5444 | 0.499 | 0.6889 | 80.87 | 0.0 |
| llm_gemini | 0.8909 | 0.8788 | 0.8617 | 0.9222 | 6967.53 | 0.3901 |
| rules | 0.9063 | 0.8648 | 0.8706 | 0.8972 | 0.15 | 0.0 |

## Method: `rules` — Sample Failure Cases

- **`case_number`** (3/60 mismatches):
  - `md-app-202-0650-01` (noisy_ocr): gold=`Nos. 291, 1310`, pred=`Nos. 291`
  - `md-app-203-0225-01` (noisy_ocr): gold=`Nos. 1668, 1669`, pred=`Nos. 1668`
- **`monetary_judgment_amount`** (2/60 mismatches):
  - `md-app-203-0321-01` (noisy_ocr): gold=`8605000000.0`, pred=`8605.0`
  - `md-app-204-0001-01` (clean): gold=`147000000.0`, pred=`147.0`
- **`case_category`** (19/60 mismatches):
  - `md-app-201-0054-01` (noisy_ocr): gold=`civil_contract_tort`, pred=`criminal`
  - `md-app-201-0315-01` (noisy_ocr): gold=`administrative_other`, pred=`UNKNOWN`
- **`disposition_outcome`**: 0 errors on the held-out test set.
- **`self_represented_flag`**: 0 errors on the held-out test set.
- **`remand_or_procedural_stay_flag`** (13/60 mismatches):
  - `md-app-201-0315-01` (noisy_ocr): gold=`true`, pred=`false`
  - `md-app-203-0225-01` (noisy_ocr): gold=`true`, pred=`false`

## Method: `classical_nlp` — Sample Failure Cases

- **`case_number`** (3/60 mismatches):
  - `md-app-202-0650-01` (noisy_ocr): gold=`Nos. 291, 1310`, pred=`Nos. 291`
  - `md-app-203-0225-01` (noisy_ocr): gold=`Nos. 1668, 1669`, pred=`Nos. 1668`
- **`monetary_judgment_amount`** (3/60 mismatches):
  - `md-app-203-0321-01` (noisy_ocr): gold=`8605000000.0`, pred=`UNKNOWN`
  - `md-app-202-0487-01` (noisy_ocr): gold=`1000.0`, pred=`UNKNOWN`
- **`case_category`** (50/60 mismatches):
  - `md-app-202-0401-01` (clean): gold=`family`, pred=`housing_property`
  - `md-app-201-0054-01` (noisy_ocr): gold=`civil_contract_tort`, pred=`housing_property`
- **`disposition_outcome`** (31/60 mismatches):
  - `md-app-201-0315-01` (noisy_ocr): gold=`affirmed_in_part_reversed_in_part`, pred=`affirmed`
  - `md-app-201-0079-01` (clean): gold=`reversed_or_vacated`, pred=`affirmed`
- **`self_represented_flag`** (1/60 mismatches):
  - `md-app-201-0390-01` (noisy_ocr): gold=`true`, pred=`false`
- **`remand_or_procedural_stay_flag`** (24/60 mismatches):
  - `md-app-201-0315-01` (noisy_ocr): gold=`true`, pred=`false`
  - `md-app-201-0023-01` (noisy_ocr): gold=`true`, pred=`false`

## Method: `llm_gemini` — Sample Failure Cases

- **`case_number`** (1/60 mismatches):
  - `md-app-203-0225-01` (noisy_ocr): gold=`Nos. 1668, 1669`, pred=`Nos. 1668, 1669, 1670` | evidence_span: `Nos. 1668, 1669, 1670,`
- **`monetary_judgment_amount`** (7/60 mismatches):
  - `md-app-201-0054-01` (noisy_ocr): gold=`530228.4`, pred=`UNKNOWN`
  - `md-app-201-0390-01` (noisy_ocr): gold=`890000.0`, pred=`UNKNOWN`
- **`case_category`** (14/60 mismatches):
  - `md-app-201-0390-01` (noisy_ocr): gold=`housing_property`, pred=`civil_contract_tort` | evidence_span: `a suit for breach of a line of credit agreement`
  - `md-app-201-0476-01` (clean): gold=`housing_property`, pred=`civil_contract_tort` | evidence_span: `failed to present any evidence to sustain a negligence claim`
- **`disposition_outcome`** (2/60 mismatches):
  - `md-app-201-0443-01` (noisy_ocr): gold=`affirmed_in_part_reversed_in_part`, pred=`affirmed` | evidence_span: `JUDGMENT OF THE CIRCUIT COURT FOR BALTIMORE CITY AFFIRMED.`
  - `md-app-204-0001-01` (clean): gold=`reversed_or_vacated`, pred=`affirmed_in_part_reversed_in_part` | evidence_span: `affirmed in part and reversed in part`
- **`self_represented_flag`** (3/60 mismatches):
  - `md-app-201-0054-01` (noisy_ocr): gold=`false`, pred=`UNKNOWN`
  - `md-app-203-0225-01` (noisy_ocr): gold=`false`, pred=`true` | evidence_span: `Edward C. McReady, Chevy Chase, MD, for appellant.`
- **`remand_or_procedural_stay_flag`** (1/60 mismatches):
  - `md-app-202-0617-01` (noisy_ocr): gold=`true`, pred=`false` | evidence_span: `JUDGMENTS AFFIRMED; COSTS TO BE PAID BY APPELLANT.`
