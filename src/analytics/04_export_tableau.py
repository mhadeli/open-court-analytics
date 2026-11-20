"""Phase 3.4: Export Suppressed Public Aggregates to Tableau (.hyper + CSV fallback).

Governance Rule:
- Exports ONLY `v_public_county_overall`, `v_public_county_summary`, and `v_public_monthly_trends`.
- Asserts zero case-level rows, zero PII columns, and zero unsuppressed small cells (< 10).
"""

from __future__ import annotations

from pathlib import Path
import duckdb
import pandas as pd
from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    Nullability,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "court_warehouse.duckdb"
TABLEAU_DIR = PROJECT_ROOT / "outputs" / "tableau"


def dtype_to_hyper(dtype: object, col_name: str) -> SqlType:
    s = str(dtype).lower()
    if "date" in col_name or "month" in col_name:
        return SqlType.date()
    if "bool" in s:
        return SqlType.bool()
    if "int" in s:
        return SqlType.big_int()
    if "float" in s:
        return SqlType.double()
    return SqlType.text()


def assert_public_safe(df: pd.DataFrame, table_name: str, count_col: str) -> None:
    forbidden = {"case_id", "case_id_hash", "tenant_city_raw", "tenant_zip_raw", "tenant_zip3"}
    leaked = set(df.columns) & forbidden
    assert not leaked, f"Governance violation in Tableau export {table_name}: {leaked}"
    bad_small = df[count_col].dropna()
    assert (bad_small < 10).sum() == 0, f"Unsuppressed <10 cell found in {table_name}!"


def write_hyper(tables: dict[str, pd.DataFrame], hyper_path: Path) -> None:
    if hyper_path.exists():
        hyper_path.unlink()

    with HyperProcess(
        telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU,
        parameters={"log_dir": "/tmp"},
    ) as hyper:
        with Connection(
            endpoint=hyper.endpoint,
            database=str(hyper_path),
            create_mode=CreateMode.CREATE_AND_REPLACE,
        ) as conn:
            conn.catalog.create_schema("Extract")
            for tname, df in tables.items():
                cols = [
                    TableDefinition.Column(
                        name=col,
                        type=dtype_to_hyper(df[col].dtype, col),
                        nullability=Nullability.NULLABLE,
                    )
                    for col in df.columns
                ]
                tdef = TableDefinition(table_name=TableName("Extract", tname), columns=cols)
                conn.catalog.create_table(tdef)

                rows = []
                for tup in df.itertuples(index=False, name=None):
                    clean_row = []
                    for col_name, val in zip(df.columns, tup):
                        if pd.isna(val):
                            clean_row.append(None)
                        elif "date" in col_name or "month" in col_name:
                            clean_row.append(pd.Timestamp(val).date())
                        elif isinstance(val, (bool,)):
                            clean_row.append(bool(val))
                        else:
                            clean_row.append(val)
                    rows.append(clean_row)

                with Inserter(conn, tdef) as inserter:
                    inserter.add_rows(rows)
                    inserter.execute()
    print(f"[ok] Wrote Tableau Hyper extract -> {hyper_path}")


def write_dashboard_spec(county_overall: pd.DataFrame, monthly: pd.DataFrame) -> None:
    suppressed_counties = int(county_overall["is_suppressed"].sum())
    suppressed_months = int(monthly["is_suppressed"].sum())
    spec = f"""# Tableau Public Dashboard Specification — Maryland Court Eviction Warrant Analytics

## Data Extract & Privacy Governance
* **Hyper Extract:** `outputs/tableau/court_dashboard.hyper` (Schema: `Extract`)
* **CSV Fallbacks:**
  * `outputs/tableau/court_dashboard_county_overall.csv` ({len(county_overall)} rows — 24 Maryland jurisdictions)
  * `outputs/tableau/court_dashboard_county_category.csv` (county × housing case category)
  * `outputs/tableau/court_dashboard_monthly.csv` ({len(monthly)} rows — county × category × month)
* **Governance Enforcement:** Zero case-level rows or PII fields are exported. Small-cell suppression (`< 10` petitions) is enforced upstream in SQL (`{suppressed_counties}` suppressed overall county rows; `{suppressed_months}` suppressed monthly cells).

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
* **Published URL:** *(Add your Tableau Public workbook URL here after opening `court_dashboard.hyper` in Tableau Public Desktop and publishing.)*
"""
    (TABLEAU_DIR / "dashboard_spec.md").write_text(spec, encoding="utf-8")
    print(f"[ok] Wrote {TABLEAU_DIR / 'dashboard_spec.md'}")


def main() -> None:
    TABLEAU_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    county_overall = con.execute("SELECT * FROM v_public_county_overall ORDER BY county_name").df()
    county_category = con.execute("SELECT * FROM v_public_county_summary ORDER BY county_name, case_category").df()
    monthly = con.execute("SELECT * FROM v_public_monthly_trends ORDER BY month_start, county_name").df()
    con.close()

    assert_public_safe(county_overall, "v_public_county_overall", "total_cases")
    assert_public_safe(county_category, "v_public_county_summary", "total_cases")
    assert_public_safe(monthly, "v_public_monthly_trends", "filings_count")

    # Export CSV fallbacks
    county_overall.to_csv(TABLEAU_DIR / "court_dashboard_county_overall.csv", index=False)
    county_category.to_csv(TABLEAU_DIR / "court_dashboard_county_category.csv", index=False)
    monthly.to_csv(TABLEAU_DIR / "court_dashboard_monthly.csv", index=False)

    # Export Tableau Hyper extract
    write_hyper(
        {
            "county_overall": county_overall,
            "county_by_category": county_category,
            "monthly_trends": monthly,
        },
        TABLEAU_DIR / "court_dashboard.hyper",
    )
    write_dashboard_spec(county_overall, monthly)
    print("[ok] Phase 3.4 Tableau exports & privacy assertions complete.")


if __name__ == "__main__":
    main()
