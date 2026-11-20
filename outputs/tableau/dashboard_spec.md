# Tableau Public Dashboard Specification — Maryland Court Eviction Warrant Analytics

## Data Extract & Privacy Governance
* **Hyper Extract:** `outputs/tableau/court_dashboard.hyper` (Schema: `Extract`)
* **CSV Fallbacks:**
  * `outputs/tableau/court_dashboard_county_overall.csv` (24 rows — 24 Maryland jurisdictions)
  * `outputs/tableau/court_dashboard_county_category.csv` (county × housing case category)
  * `outputs/tableau/court_dashboard_monthly.csv` (405 rows — county × category × month)
* **Governance Enforcement:** Zero case-level rows or PII fields are exported. Small-cell suppression (`< 10` petitions) is enforced upstream in SQL (`0` suppressed overall county rows; `245` suppressed monthly cells).

---

## Dashboard Layout (1400 × 900 Desktop Canvas)

### Row 1 — Executive KPI Tiles (`county_overall`)
1. **Total Petitions Filed:** `SUM([total_cases])`
2. **Clearance Rate (%):** `SUM([closed_cases]) / SUM([total_cases])`
3. **Median Days to Resolution (Closed):** `MEDIAN([median_days_closed])` (annotate with KM censor-adjusted median from analytical brief)
4. **Executed Eviction Rate (%):** `SUM([evicted_cases]) / SUM([total_cases])`
5. **Institutional Batch E-Filer Share (%):** `AVG([batch_efiler_pct])`

### Row 2 — Geographic & Temporal Views
* **Left — Maryland County Choropleth Map (`county_overall`):**
  * Geographic Role: County (`county_name`, State = `"Maryland"`, FIPS = `jurisdiction_fips`).
  * Color: `median_days_closed` (diverging/sequential blue scale); `NULL` / suppressed jurisdictions colored light gray (`#D9D9D9`) with tooltip note `"Suppressed (<10 closed cases)"`.
  * Tooltip: `county_name`, `total_cases`, `clearance_rate_pct`, `eviction_rate_pct`, `median_days_closed`, `pct_disposed_within_60d`.
* **Right — Monthly Filings vs. Dispositions Trend (`monthly_trends`):**
  * Dual-line chart on `month_start` (Continuous Month): `SUM([filings_count])` vs. `SUM([dispositions_count])` + reference note for extract cutoff date (`2026-09-30`).

### Row 3 — Time-Standard Compliance Comparison (`county_by_category`)
* **Horizontal Bar Chart:** `pct_disposed_within_60d` and `pct_disposed_within_90d` by `county_name`, sorted descending, with vertical reference lines at 75% and 90%.

### Global Filters (Apply to All Worksheets)
* `region` (Capital, Central, Eastern Shore, Southern, Western)
* `county_name`
* `case_category` (Failure to Pay Rent, Public Housing FTPR, Tenant Holding Over, Wrongful Detainer, Breach of Lease)
* `month_start`

### Mandatory Dashboard Footer Caption
> *Source: District Court of Maryland Eviction Case Data (Maryland Open Data, `mvqb-b4hf`), aligned to NODS-core schemas. Cells with fewer than 10 cases are suppressed for privacy. Closed-case medians reflect resolved petitions only; see the analytical brief for Kaplan–Meier right-censored estimates. Descriptive operational metrics only—do not interpret jurisdiction differences as causal.*

## Tableau Public Link
* **Profile:** https://public.tableau.com/app/profile/adeli
* **Published Workbook URL:** *(Paste exact workbook URL here after publishing from Tableau Public Desktop.)*
