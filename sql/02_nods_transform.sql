-- Phase 1.2: Normalize raw court events into NODS-aligned relational tables
-- Reference: National Open Court Data Standards (NODS) Civil/Housing Core Elements

DROP TABLE IF EXISTS dim_jurisdictions;
CREATE TABLE dim_jurisdictions (
    raw_county VARCHAR PRIMARY KEY,
    jurisdiction_fips VARCHAR(5) NOT NULL,
    county_name VARCHAR NOT NULL,
    region VARCHAR NOT NULL
);

INSERT INTO dim_jurisdictions VALUES
    ('Allegany',        '24001', 'Allegany County',        'Western'),
    ('Anne Arundel',    '24003', 'Anne Arundel County',    'Central'),
    ('Baltimore',       '24005', 'Baltimore County',       'Central'),
    ('Calvert',         '24009', 'Calvert County',         'Southern'),
    ('Caroline',        '24011', 'Caroline County',        'Eastern Shore'),
    ('Carroll',         '24013', 'Carroll County',         'Central'),
    ('Cecil',           '24015', 'Cecil County',           'Eastern Shore'),
    ('Charles',         '24017', 'Charles County',         'Southern'),
    ('Dorchester',      '24019', 'Dorchester County',      'Eastern Shore'),
    ('Frederick',       '24021', 'Frederick County',       'Central'),
    ('Garrett',         '24023', 'Garrett County',         'Western'),
    ('Harford',         '24025', 'Harford County',         'Central'),
    ('Howard',          '24027', 'Howard County',          'Central'),
    ('Kent',            '24029', 'Kent County',            'Eastern Shore'),
    ('Montgomery',      '24031', 'Montgomery County',      'Capital'),
    ('Prince George''s','24033', 'Prince George''s County','Capital'),
    ('Queen Anne''s',   '24035', 'Queen Anne''s County',   'Eastern Shore'),
    ('Saint Mary''s',   '24037', 'St. Mary''s County',     'Southern'),
    ('Somerset',        '24039', 'Somerset County',        'Eastern Shore'),
    ('Talbot',          '24041', 'Talbot County',          'Eastern Shore'),
    ('Washington',      '24043', 'Washington County',      'Western'),
    ('Wicomico',        '24045', 'Wicomico County',        'Eastern Shore'),
    ('Worcester',       '24047', 'Worcester County',       'Eastern Shore'),
    ('Baltimore City',  '24510', 'Baltimore City',         'Central');

-- Standardized event table (NODS Event element crosswalk)
DROP TABLE IF EXISTS nods_events;
CREATE TABLE nods_events AS
SELECT
    'EVT-' || CAST(r.raw_row_id AS VARCHAR) AS event_id,
    r.clean_case_number AS case_id,
    j.jurisdiction_fips,
    r.event_date,
    CASE
        WHEN r.raw_event_type ILIKE 'Petition%Warrant%' THEN 'Warrant Petition Filed'
        WHEN r.raw_event_type ILIKE '%Evicted%'         THEN 'Warrant Executed (Evicted)'
        WHEN r.raw_event_type ILIKE '%Cancelled%'       THEN 'Warrant Cancelled'
        WHEN r.raw_event_type ILIKE '%Expired%'         THEN 'Warrant Expired'
        ELSE 'Other Event'
    END AS event_type,
    r.raw_event_type,
    -- Institutional e-filing vendors use '<VENDOR>::Warrant of Restitution' notation in event comments
    CASE
        WHEN r.event_comment LIKE '%::%' THEN TRUE
        ELSE FALSE
    END AS batch_efiler_flag
FROM raw_court_events r
LEFT JOIN dim_jurisdictions j
    ON r.raw_county = j.raw_county;

-- Case-level table (1 row per unique normalized case_id)
DROP TABLE IF EXISTS nods_cases;
CREATE TABLE nods_cases AS
WITH cutoff AS (
    SELECT MAX(event_date) AS extract_cutoff_date FROM raw_court_events
),
case_agg AS (
    SELECT
        r.clean_case_number AS case_id,
        ANY_VALUE(j.jurisdiction_fips) AS jurisdiction_fips,
        ANY_VALUE(j.county_name) AS county_name,
        ANY_VALUE(j.region) AS region,
        ANY_VALUE(r.raw_case_type) AS raw_case_type,
        -- Crosswalk local District Court housing types into clean NODS Civil-Housing subcategories
        CASE
            WHEN ANY_VALUE(r.raw_case_type) = 'Failure to Pay Rent'                   THEN 'Failure to Pay Rent'
            WHEN ANY_VALUE(r.raw_case_type) = 'Failure to Pay Rent - Housing Authority' THEN 'Public Housing FTPR'
            WHEN ANY_VALUE(r.raw_case_type) = 'Tenant Holding Over'                   THEN 'Tenant Holding Over'
            WHEN ANY_VALUE(r.raw_case_type) = 'Wrongful Detainer'                     THEN 'Wrongful Detainer'
            WHEN ANY_VALUE(r.raw_case_type) = 'Breach of Lease'                       THEN 'Breach of Lease'
            ELSE 'Other Housing'
        END AS case_category,
        MIN(CASE WHEN r.raw_event_type ILIKE 'Petition%' THEN r.event_date END) AS filing_date,
        MAX(CASE WHEN r.raw_event_type ILIKE 'Warrant%'  THEN COALESCE(r.evicted_date, r.event_date) END) AS disposition_date,
        MAX(CASE WHEN r.raw_event_type ILIKE '%Evicted%'   THEN 1 ELSE 0 END) AS evicted_flag,
        MAX(CASE WHEN r.raw_event_type ILIKE '%Cancelled%' THEN 1 ELSE 0 END) AS cancelled_flag,
        MAX(CASE WHEN r.raw_event_type ILIKE '%Expired%'   THEN 1 ELSE 0 END) AS expired_flag,
        MAX(CASE WHEN r.event_comment LIKE '%::%'          THEN 1 ELSE 0 END) AS batch_efiler_flag,
        COUNT(*) AS event_count,
        ANY_VALUE(r.tenant_city_raw) AS tenant_city_raw,
        ANY_VALUE(r.tenant_zip_raw) AS tenant_zip_raw
    FROM raw_court_events r
    LEFT JOIN dim_jurisdictions j
        ON r.raw_county = j.raw_county
    GROUP BY r.clean_case_number
)
SELECT
    c.case_id,
    c.jurisdiction_fips,
    c.county_name,
    c.region,
    'District Court' AS court_type,
    c.case_category,
    c.raw_case_type,
    c.filing_date,
    c.disposition_date,
    CASE
        WHEN c.evicted_flag = 1   THEN 'Evicted'
        WHEN c.cancelled_flag = 1 THEN 'Cancelled'
        WHEN c.expired_flag = 1   THEN 'Expired'
        ELSE 'Pending'
    END AS disposition_type,
    CASE
        WHEN c.disposition_date IS NOT NULL THEN 'Closed'
        ELSE 'Open'
    END AS case_status,
    CAST(c.evicted_flag AS BOOLEAN) AS evicted_flag,
    CAST(c.batch_efiler_flag AS BOOLEAN) AS batch_efiler_flag,
    c.event_count,
    k.extract_cutoff_date,
    CASE
        WHEN c.filing_date IS NULL THEN NULL
        WHEN c.disposition_date IS NOT NULL THEN DATEDIFF('day', c.filing_date, c.disposition_date)
        ELSE DATEDIFF('day', c.filing_date, k.extract_cutoff_date)
    END AS days_observed,
    CASE
        WHEN c.filing_date IS NOT NULL AND c.disposition_date IS NULL THEN TRUE
        ELSE FALSE
    END AS is_right_censored,
    CASE
        WHEN c.filing_date IS NOT NULL AND c.disposition_date IS NOT NULL AND c.disposition_date < c.filing_date THEN TRUE
        ELSE FALSE
    END AS has_impossible_date,
    c.tenant_city_raw,
    c.tenant_zip_raw
FROM case_agg c
CROSS JOIN cutoff k;

-- Party-level table (pseudonymized party IDs; documents representation transparency)
DROP TABLE IF EXISTS nods_parties;
CREATE TABLE nods_parties AS
SELECT
    SHA256('OPEN_COURT_SALT_V1::PLAINTIFF::' || case_id) AS party_id_hash,
    case_id,
    'Plaintiff/Landlord' AS party_role,
    CASE
        WHEN batch_efiler_flag THEN 'Institutional Batch E-Filer'
        ELSE 'Standard Filer'
    END AS representation_type
FROM nods_cases
UNION ALL
SELECT
    SHA256('OPEN_COURT_SALT_V1::DEFENDANT::' || case_id) AS party_id_hash,
    case_id,
    'Defendant/Tenant' AS party_role,
    'Unknown (Not Reported in Public Extract)' AS representation_type
FROM nods_cases;
