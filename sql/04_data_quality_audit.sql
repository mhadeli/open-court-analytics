-- Phase 1.4: Automated Data Quality & Governance Audit Summary

DROP TABLE IF EXISTS qa_audit_summary;
CREATE TABLE qa_audit_summary AS
SELECT 'raw_event_rows' AS metric, COUNT(*) AS value, 'Total raw event records ingested' AS notes
FROM raw_court_events
UNION ALL
SELECT 'messy_case_numbers_cleaned', COUNT(*), 'Rows with internal whitespace normalized in casenumber'
FROM raw_court_events
WHERE raw_case_number <> clean_case_number
UNION ALL
SELECT 'distinct_cases_raw', COUNT(*), 'Unique normalized case_id values in nods_cases'
FROM nods_cases
UNION ALL
SELECT 'unmapped_jurisdiction_rows', COUNT(*), 'Cases missing valid Maryland county FIPS (must be 0)'
FROM nods_cases
WHERE jurisdiction_fips IS NULL
UNION ALL
SELECT 'left_truncated_no_petition', COUNT(*), 'Cases with warrant return only (petition predated extract window)'
FROM nods_cases
WHERE filing_date IS NULL
UNION ALL
SELECT 'impossible_date_cases', COUNT(*), 'Cases where disposition_date < filing_date (excluded from v_analyst_cases)'
FROM nods_cases
WHERE has_impossible_date = TRUE
UNION ALL
SELECT 'analyst_cohort_cases', COUNT(*), 'Valid petition-cohort cases exposed in v_analyst_cases'
FROM v_analyst_cases
UNION ALL
SELECT 'right_censored_open_cases', COUNT(*), 'Open cases in v_analyst_cases right-censored at extract cutoff'
FROM v_analyst_cases
WHERE is_right_censored = TRUE
UNION ALL
SELECT 'suppressed_county_category_cells', COUNT(*), 'County-category cells suppressed under < 10 threshold'
FROM v_public_county_summary
WHERE is_suppressed = TRUE;
