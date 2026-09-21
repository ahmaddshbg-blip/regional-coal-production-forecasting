SELECT 'raw_quarterly_rows' AS check_name, CAST(COUNT(*) AS VARCHAR) AS observed_value
FROM quarterly_source
UNION ALL
SELECT 'coal_source_rows', CAST(COUNT(*) AS VARCHAR)
FROM coal_source_typed
UNION ALL
SELECT 'coal_distinct_mines', CAST(COUNT(DISTINCT mine_id) AS VARCHAR)
FROM coal_source_typed
UNION ALL
SELECT 'duplicate_source_keys', CAST(COALESCE(SUM(row_count - 1), 0) AS VARCHAR)
FROM (
    SELECT COUNT(*) AS row_count
    FROM coal_source_typed
    GROUP BY mine_id, cal_year, cal_quarter, subunit_code
    HAVING COUNT(*) > 1
) duplicate_keys
UNION ALL
SELECT 'invalid_coal_mine_ids', CAST(COUNT(*) AS VARCHAR)
FROM coal_source_typed
WHERE mine_id IS NULL OR NOT regexp_full_match(mine_id, '[0-9]+')
UNION ALL
SELECT 'invalid_coal_periods', CAST(COUNT(*) AS VARCHAR)
FROM coal_source_typed
WHERE cal_year IS NULL OR cal_quarter NOT BETWEEN 1 AND 4
UNION ALL
SELECT 'invalid_coal_production_values', CAST(COUNT(*) AS VARCHAR)
FROM coal_source_typed
WHERE coal_production_raw IS NOT NULL AND coal_production_short_tons IS NULL
UNION ALL
SELECT 'negative_coal_production_rows', CAST(COUNT(*) AS VARCHAR)
FROM coal_source_typed
WHERE coal_production_short_tons < 0
UNION ALL
SELECT 'duplicate_master_mine_ids', CAST(COALESCE(SUM(row_count - 1), 0) AS VARCHAR)
FROM (
    SELECT COUNT(*) AS row_count
    FROM master_mines
    WHERE mine_id IS NOT NULL
    GROUP BY mine_id
    HAVING COUNT(*) > 1
) duplicate_mines
UNION ALL
SELECT 'unmatched_coal_mine_ids', CAST(COUNT(*) AS VARCHAR)
FROM (
    SELECT DISTINCT source.mine_id
    FROM coal_source_typed source
    LEFT JOIN master_mines master USING (mine_id)
    WHERE source.mine_id IS NOT NULL AND master.mine_id IS NULL
) unmatched_mines
UNION ALL
SELECT 'mine_quarter_rows', CAST(COUNT(*) AS VARCHAR)
FROM mine_quarter
UNION ALL
SELECT 'mine_quarter_positive_rows', CAST(COUNT(*) AS VARCHAR)
FROM mine_quarter
WHERE coal_production_short_tons > 0
UNION ALL
SELECT 'mine_quarter_zero_rows', CAST(COUNT(*) AS VARCHAR)
FROM mine_quarter
WHERE coal_production_short_tons = 0
UNION ALL
SELECT 'mine_quarter_all_null_rows', CAST(COUNT(*) AS VARCHAR)
FROM mine_quarter
WHERE coal_production_short_tons IS NULL
UNION ALL
SELECT 'state_count', CAST(COUNT(DISTINCT state_code) AS VARCHAR)
FROM mine_quarter
UNION ALL
SELECT 'period_min', MIN(period)
FROM mine_quarter
UNION ALL
SELECT 'period_max', MAX(period)
FROM mine_quarter
UNION ALL
SELECT 'state_quarter_rows', CAST(COUNT(*) AS VARCHAR)
FROM state_quarter
UNION ALL
SELECT 'missing_state_mine_quarters', CAST(COUNT(*) AS VARCHAR)
FROM mine_quarter
WHERE state_code IS NULL;
