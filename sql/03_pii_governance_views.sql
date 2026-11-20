-- Phase 1.3: PII Governance & Masked Analytical / Public Views
-- Downstream analytics MUST query only v_analyst_cases or v_public_* views.
-- Raw geographic quasi-identifiers (tenant_city_raw, full tenant_zip_raw) and raw case_id are excluded.

DROP VIEW IF EXISTS v_analyst_cases;
CREATE VIEW v_analyst_cases AS
SELECT
    SHA256('OPEN_COURT_SALT_V1::CASE::' || case_id) AS case_id_hash,
    jurisdiction_fips,
    county_name,
    region,
    court_type,
    case_category,
    filing_date,
    DATE_TRUNC('month', filing_date) AS filing_month,
    EXTRACT(YEAR FROM filing_date) AS filing_year,
    disposition_date,
    disposition_type,
    case_status,
    evicted_flag,
    batch_efiler_flag,
    event_count,
    extract_cutoff_date,
    days_observed,
    is_right_censored,
    -- Coarsen 5-digit ZIP to 3-digit prefix (ZIP3) as a de-identification safeguard
    CASE
        WHEN LENGTH(REGEXP_REPLACE(COALESCE(tenant_zip_raw, ''), '[^0-9]', '', 'g')) >= 3
        THEN LEFT(REGEXP_REPLACE(tenant_zip_raw, '[^0-9]', '', 'g'), 3)
        ELSE NULL
    END AS tenant_zip3
FROM nods_cases
WHERE filing_date IS NOT NULL
  AND has_impossible_date = FALSE;

-- Public county-by-category aggregate view with strict small-cell suppression (< 10 cases)
DROP VIEW IF EXISTS v_public_county_summary;
CREATE VIEW v_public_county_summary AS
WITH base AS (
    SELECT
        jurisdiction_fips,
        county_name,
        region,
        case_category,
        COUNT(*) AS n_cases,
        SUM(CASE WHEN case_status = 'Closed' THEN 1 ELSE 0 END) AS n_closed,
        SUM(CASE WHEN evicted_flag THEN 1 ELSE 0 END) AS n_evicted,
        SUM(CASE WHEN batch_efiler_flag THEN 1 ELSE 0 END) AS n_batch_efiler,
        MEDIAN(CASE WHEN case_status = 'Closed' THEN days_observed END) AS median_days_closed,
        AVG(CASE WHEN case_status = 'Closed' AND days_observed <= 30 THEN 1.0 WHEN case_status = 'Closed' THEN 0.0 END) AS pct_closed_30d,
        AVG(CASE WHEN case_status = 'Closed' AND days_observed <= 60 THEN 1.0 WHEN case_status = 'Closed' THEN 0.0 END) AS pct_closed_60d,
        AVG(CASE WHEN case_status = 'Closed' AND days_observed <= 90 THEN 1.0 WHEN case_status = 'Closed' THEN 0.0 END) AS pct_closed_90d
    FROM v_analyst_cases
    GROUP BY 1, 2, 3, 4
)
SELECT
    'Maryland' AS state,
    jurisdiction_fips,
    county_name,
    region,
    case_category,
    CASE WHEN n_cases < 10 THEN TRUE ELSE FALSE END AS is_suppressed,
    CASE WHEN n_cases < 10 THEN NULL ELSE n_cases END AS total_cases,
    CASE WHEN n_cases < 10 THEN NULL ELSE n_closed END AS closed_cases,
    CASE WHEN n_cases < 10 THEN NULL ELSE n_evicted END AS evicted_cases,
    CASE WHEN n_cases < 10 THEN NULL ELSE ROUND(100.0 * n_closed / n_cases, 2) END AS clearance_rate_pct,
    CASE WHEN n_cases < 10 THEN NULL ELSE ROUND(100.0 * n_evicted / n_cases, 2) END AS eviction_rate_pct,
    CASE WHEN n_cases < 10 THEN NULL ELSE ROUND(100.0 * n_batch_efiler / n_cases, 2) END AS batch_efiler_pct,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(median_days_closed, 1) END AS median_days_closed,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(100.0 * pct_closed_30d, 2) END AS pct_disposed_within_30d,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(100.0 * pct_closed_60d, 2) END AS pct_disposed_within_60d,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(100.0 * pct_closed_90d, 2) END AS pct_disposed_within_90d
FROM base;

-- Public overall county summary (rolled across all housing categories, < 10 suppression enforced)
DROP VIEW IF EXISTS v_public_county_overall;
CREATE VIEW v_public_county_overall AS
WITH base AS (
    SELECT
        jurisdiction_fips,
        county_name,
        region,
        COUNT(*) AS n_cases,
        SUM(CASE WHEN case_status = 'Closed' THEN 1 ELSE 0 END) AS n_closed,
        SUM(CASE WHEN evicted_flag THEN 1 ELSE 0 END) AS n_evicted,
        SUM(CASE WHEN batch_efiler_flag THEN 1 ELSE 0 END) AS n_batch_efiler,
        MEDIAN(CASE WHEN case_status = 'Closed' THEN days_observed END) AS median_days_closed,
        AVG(CASE WHEN case_status = 'Closed' AND days_observed <= 30 THEN 1.0 WHEN case_status = 'Closed' THEN 0.0 END) AS pct_closed_30d,
        AVG(CASE WHEN case_status = 'Closed' AND days_observed <= 60 THEN 1.0 WHEN case_status = 'Closed' THEN 0.0 END) AS pct_closed_60d,
        AVG(CASE WHEN case_status = 'Closed' AND days_observed <= 90 THEN 1.0 WHEN case_status = 'Closed' THEN 0.0 END) AS pct_closed_90d
    FROM v_analyst_cases
    GROUP BY 1, 2, 3
)
SELECT
    'Maryland' AS state,
    jurisdiction_fips,
    county_name,
    region,
    CASE WHEN n_cases < 10 THEN TRUE ELSE FALSE END AS is_suppressed,
    CASE WHEN n_cases < 10 THEN NULL ELSE n_cases END AS total_cases,
    CASE WHEN n_cases < 10 THEN NULL ELSE n_closed END AS closed_cases,
    CASE WHEN n_cases < 10 THEN NULL ELSE n_evicted END AS evicted_cases,
    CASE WHEN n_cases < 10 THEN NULL ELSE ROUND(100.0 * n_closed / n_cases, 2) END AS clearance_rate_pct,
    CASE WHEN n_cases < 10 THEN NULL ELSE ROUND(100.0 * n_evicted / n_cases, 2) END AS eviction_rate_pct,
    CASE WHEN n_cases < 10 THEN NULL ELSE ROUND(100.0 * n_batch_efiler / n_cases, 2) END AS batch_efiler_pct,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(median_days_closed, 1) END AS median_days_closed,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(100.0 * pct_closed_30d, 2) END AS pct_disposed_within_30d,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(100.0 * pct_closed_60d, 2) END AS pct_disposed_within_60d,
    CASE WHEN n_cases < 10 OR n_closed < 10 THEN NULL ELSE ROUND(100.0 * pct_closed_90d, 2) END AS pct_disposed_within_90d
FROM base;

-- Public monthly county filing vs. disposition trend view (< 10 small-cell suppression enforced)
DROP VIEW IF EXISTS v_public_monthly_trends;
CREATE VIEW v_public_monthly_trends AS
WITH monthly AS (
    SELECT
        jurisdiction_fips,
        county_name,
        region,
        case_category,
        CAST(filing_month AS DATE) AS month_start,
        COUNT(*) AS n_filings,
        SUM(CASE WHEN case_status = 'Closed' THEN 1 ELSE 0 END) AS n_dispositions,
        SUM(CASE WHEN evicted_flag THEN 1 ELSE 0 END) AS n_evictions
    FROM v_analyst_cases
    GROUP BY 1, 2, 3, 4, 5
)
SELECT
    'Maryland' AS state,
    jurisdiction_fips,
    county_name,
    region,
    case_category,
    month_start,
    CASE WHEN n_filings < 10 THEN TRUE ELSE FALSE END AS is_suppressed,
    CASE WHEN n_filings < 10 THEN NULL ELSE n_filings END AS filings_count,
    CASE WHEN n_filings < 10 THEN NULL ELSE n_dispositions END AS dispositions_count,
    CASE WHEN n_filings < 10 THEN NULL ELSE n_evictions END AS evictions_count
FROM monthly;
