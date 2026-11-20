-- Phase 1.1: Stage raw Maryland District Court eviction event records
-- Source: Maryland Open Data Portal (Socrata resource mvqb-b4hf)

DROP TABLE IF EXISTS raw_court_events;

CREATE TABLE raw_court_events AS
SELECT
    ROW_NUMBER() OVER () AS raw_row_id,
    TRIM(casenumber) AS raw_case_number,
    -- Normalize clerk whitespace inconsistencies (e.g., '22- 313632' -> '22-313632')
    REGEXP_REPLACE(UPPER(TRIM(casenumber)), '\s+', '', 'g') AS clean_case_number,
    TRY_CAST(LEFT(eventdate, 10) AS DATE) AS event_date,
    TRY_CAST(LEFT(evicteddate, 10) AS DATE) AS evicted_date,
    TRIM(eventtype) AS raw_event_type,
    NULLIF(TRIM(eventcomment), '') AS event_comment,
    TRIM(county) AS raw_county,
    TRIM(location) AS court_location,
    TRIM(casetype) AS raw_case_type,
    NULLIF(TRIM(tenantcity), '') AS tenant_city_raw,
    NULLIF(TRIM(tenantstate), '') AS tenant_state_raw,
    NULLIF(TRIM(tenantzipcode), '') AS tenant_zip_raw,
    TRY_CAST(year AS INTEGER) AS event_year,
    TRY_CAST(evictionyear AS INTEGER) AS eviction_year
FROM read_csv_auto('__RAW_CSV_PATH__', all_varchar = true, header = true)
WHERE casenumber IS NOT NULL;
