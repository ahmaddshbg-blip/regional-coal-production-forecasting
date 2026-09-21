CREATE OR REPLACE TEMP TABLE state_quarter AS
SELECT
    state_code,
    cal_year,
    cal_quarter,
    period,
    quarter_start_date,
    SUM(coal_production_short_tons) AS coal_production_short_tons,
    COUNT(*) AS mine_quarter_row_count,
    COUNT(coal_production_short_tons) AS observed_mine_count,
    COUNT(*) - COUNT(coal_production_short_tons) AS all_null_mine_count,
    CAST(SUM(CASE WHEN coal_production_short_tons > 0 THEN 1 ELSE 0 END) AS BIGINT)
        AS positive_mine_count,
    CAST(SUM(CASE WHEN coal_production_short_tons = 0 THEN 1 ELSE 0 END) AS BIGINT)
        AS zero_mine_count,
    CAST(SUM(CASE WHEN production_partially_null THEN 1 ELSE 0 END) AS BIGINT)
        AS partially_null_mine_count,
    CAST(SUM(source_row_count) AS BIGINT) AS source_row_count,
    SUM(average_employee_count) AS average_employee_count,
    SUM(hours_worked) AS hours_worked
FROM mine_quarter
GROUP BY state_code, cal_year, cal_quarter, period, quarter_start_date;
