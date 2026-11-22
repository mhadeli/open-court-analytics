"""Phase 1 Orchestrator: Build NODS-aligned DuckDB warehouse and enforce PII/QA assertions."""

from __future__ import annotations

from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "md_eviction_cases.csv"
DB_PATH = PROJECT_ROOT / "data" / "processed" / "court_warehouse.duckdb"
SQL_DIR = PROJECT_ROOT / "sql"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def run_sql_file(con: duckdb.DuckDBPyConnection, sql_file: Path) -> None:
    sql_text = sql_file.read_text(encoding="utf-8")
    sql_text = sql_text.replace("__RAW_CSV_PATH__", str(RAW_CSV))
    con.execute(sql_text)
    print(f"[ok] Executed {sql_file.name}")


def verify_governance_and_qa(con: duckdb.DuckDBPyConnection) -> None:
    """Assert critical PII governance and data-integrity invariants."""
    # 1. Zero unmapped county FIPS
    unmapped = con.execute(
        "SELECT COUNT(*) FROM nods_cases WHERE jurisdiction_fips IS NULL"
    ).fetchone()[0]
    assert unmapped == 0, f"Found {unmapped} unmapped jurisdiction rows!"

    # 2. Zero raw PII / direct identifier columns in v_analyst_cases
    analyst_cols = {
        row[0] for row in con.execute("DESCRIBE v_analyst_cases").fetchall()
    }
    forbidden_pii = {"case_id", "tenant_city_raw", "tenant_zip_raw", "raw_case_number"}
    leaked = analyst_cols & forbidden_pii
    assert not leaked, f"PII governance violation: {leaked} exposed in v_analyst_cases!"

    # 3. Zero unsuppressed small cells (< 10 cases) in public views
    county_counts = ["total_cases", "closed_cases", "evicted_cases"]
    for view_name, count_cols in [
        ("v_public_county_summary", county_counts),
        ("v_public_county_overall", county_counts),
        ("v_public_monthly_trends", ["filings_count", "dispositions_count", "evictions_count"]),
    ]:
        for count_col in count_cols:
            bad_cells = con.execute(
                f"SELECT COUNT(*) FROM {view_name} WHERE {count_col} < 10"
            ).fetchone()[0]
            assert bad_cells == 0, (
                f"Small-cell suppression violation in {view_name}.{count_col}: {bad_cells} cells"
            )

    # 4. Zero impossible timelines in v_analyst_cases
    bad_dates = con.execute(
        "SELECT COUNT(*) FROM v_analyst_cases WHERE days_observed < 0"
    ).fetchone()[0]
    assert bad_dates == 0, f"Found {bad_dates} negative duration rows in v_analyst_cases!"

    print("[ok] All PII governance, small-cell suppression (<10), and QA assertions passed.")


def main() -> None:
    if not RAW_CSV.exists():
        raise FileNotFoundError(
            f"Raw dataset not found at {RAW_CSV}. Run `python src/db/00_fetch_court_data.py` first."
        )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(str(DB_PATH))
    try:
        for fname in [
            "01_staging_load.sql",
            "02_nods_transform.sql",
            "03_pii_governance_views.sql",
            "04_data_quality_audit.sql",
        ]:
            run_sql_file(con, SQL_DIR / fname)

        verify_governance_and_qa(con)

        # Export QA audit summary to outputs/qa_audit_summary.csv
        audit_df = con.execute("SELECT * FROM qa_audit_summary").df()
        audit_df.to_csv(OUTPUTS_DIR / "qa_audit_summary.csv", index=False)

        print("\n=== Phase 1 Data Quality & Governance Audit ===")
        print(audit_df.to_string(index=False))

        date_bounds = con.execute(
            "SELECT MIN(filing_date), MAX(filing_date), MAX(extract_cutoff_date) FROM v_analyst_cases"
        ).fetchone()
        print(
            f"\nAnalyst cohort filing window: {date_bounds[0]} to {date_bounds[1]} "
            f"(extract cutoff: {date_bounds[2]})"
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
