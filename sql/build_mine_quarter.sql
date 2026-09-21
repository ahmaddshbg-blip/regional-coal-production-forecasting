CREATE OR REPLACE TEMP TABLE coal_source_typed AS
SELECT
    NULLIF(TRIM(BOTH '"' FROM TRIM(MINE_ID)), '') AS mine_id,
    NULLIF(TRIM(BOTH '"' FROM TRIM(CURR_MINE_NM)), '') AS mine_name,
    NULLIF(UPPER(TRIM(BOTH '"' FROM TRIM(STATE))), '') AS state_code,
    NULLIF(TRIM(BOTH '"' FROM TRIM(SUBUNIT_CD)), '') AS subunit_code,
    TRY_CAST(NULLIF(TRIM(BOTH '"' FROM TRIM(CAL_YR)), '') AS INTEGER) AS cal_year,
    TRY_CAST(NULLIF(TRIM(BOTH '"' FROM TRIM(CAL_QTR)), '') AS INTEGER) AS cal_quarter,
    TRY_CAST(NULLIF(TRIM(BOTH '"' FROM TRIM(AVG_EMPLOYEE_CNT)), '') AS DOUBLE) AS average_employee_count,
    TRY_CAST(NULLIF(TRIM(BOTH '"' FROM TRIM(HOURS_WORKED)), '') AS DOUBLE) AS hours_worked,
    TRY_CAST(NULLIF(TRIM(BOTH '"' FROM TRIM(COAL_PRODUCTION)), '') AS DOUBLE) AS coal_production_short_tons,
    NULLIF(TRIM(BOTH '"' FROM TRIM(COAL_PRODUCTION)), '') AS coal_production_raw
FROM quarterly_source
WHERE UPPER(TRIM(BOTH '"' FROM TRIM(COAL_METAL_IND))) = 'C';

CREATE OR REPLACE TEMP TABLE master_mines AS
SELECT
    NULLIF(TRIM(BOTH '"' FROM TRIM(MINE_ID)), '') AS mine_id,
    NULLIF(UPPER(TRIM(BOTH '"' FROM TRIM(STATE))), '') AS current_state_code,
    NULLIF(TRIM(BOTH '"' FROM TRIM(COAL_METAL_IND)), '') AS coal_metal_indicator
FROM mine_master;

CREATE OR REPLACE TEMP TABLE mine_quarter AS
SELECT
    mine_id,
    state_code,
    cal_year,
    cal_quarter,
    CAST(cal_year AS VARCHAR) || 'Q' || CAST(cal_quarter AS VARCHAR) AS period,
    CASE
        WHEN cal_year IS NOT NULL AND cal_quarter BETWEEN 1 AND 4
        THEN MAKE_DATE(cal_year, ((cal_quarter - 1) * 3) + 1, 1)
        ELSE NULL
    END AS quarter_start_date,
    SUM(coal_production_short_tons) AS coal_production_short_tons,
    SUM(average_employee_count) AS average_employee_count,
    SUM(hours_worked) AS hours_worked,
    COUNT(*) AS source_row_count,
    COUNT(coal_production_short_tons) AS reported_production_row_count,
    COUNT(*) - COUNT(coal_production_short_tons) AS missing_production_row_count,
    COUNT(coal_production_short_tons) = 0 AS production_all_null,
    COUNT(coal_production_short_tons) > 0
        AND COUNT(coal_production_short_tons) < COUNT(*) AS production_partially_null
FROM coal_source_typed
GROUP BY mine_id, state_code, cal_year, cal_quarter;
