-- Date dimension table
-- Generates all dates from 2010-01-01 to 2035-12-31
-- Uses Spark SQL sequence function for date generation
-- Joins to silver.gov_uk_bank_holidays for England and Wales bank holiday enrichment

WITH date_series AS (
    SELECT EXPLODE(SEQUENCE(TO_DATE('2010-01-01'), TO_DATE('2035-12-31'), INTERVAL 1 DAY)) AS calendar_date
)
SELECT
    CAST(DATE_FORMAT(date_series.calendar_date, 'yyyyMMdd') AS INT) AS date_id,
    date_series.calendar_date,
    YEAR(date_series.calendar_date) AS year,
    MONTH(date_series.calendar_date) AS month,
    DAY(date_series.calendar_date) AS day,
    DATE_FORMAT(date_series.calendar_date, 'MMMM') AS month_name,
    DATE_FORMAT(date_series.calendar_date, 'EEEE') AS day_name,
    QUARTER(date_series.calendar_date) AS quarter,
    WEEKOFYEAR(date_series.calendar_date) AS week_of_year,
    CASE WHEN DAYOFWEEK(date_series.calendar_date) = 1 THEN 7 ELSE DAYOFWEEK(date_series.calendar_date) - 1 END AS day_of_week,
    CASE WHEN DAYOFWEEK(date_series.calendar_date) IN (1, 7) THEN TRUE ELSE FALSE END AS is_weekend,
    TRUNC(date_series.calendar_date, 'MM') AS first_day_of_month,
    LAST_DAY(date_series.calendar_date) AS last_day_of_month,
    CAST(DATE_SUB(date_series.calendar_date, CASE WHEN DAYOFWEEK(date_series.calendar_date) = 1 THEN 6 ELSE DAYOFWEEK(date_series.calendar_date) - 2 END) AS DATE) AS week_start_date,
    CAST(DATE_ADD(DATE_SUB(date_series.calendar_date, CASE WHEN DAYOFWEEK(date_series.calendar_date) = 1 THEN 6 ELSE DAYOFWEEK(date_series.calendar_date) - 2 END), 6) AS DATE) AS week_end_date,
    DAYOFWEEK(date_series.calendar_date) AS spark_day_of_week,
    CASE WHEN bh.holiday_date IS NOT NULL THEN TRUE ELSE FALSE END AS is_bank_holiday,
    bh.holiday_name AS bank_holiday_name,
    DATE_FORMAT(date_series.calendar_date, 'MMMM yyyy') AS month_year_label,
    CAST(DATE_FORMAT(date_series.calendar_date, 'yyyyMM') AS INT) AS month_year_sort,
    DATE_FORMAT(CAST(DATE_SUB(date_series.calendar_date, CASE WHEN DAYOFWEEK(date_series.calendar_date) = 1 THEN 6 ELSE DAYOFWEEK(date_series.calendar_date) - 2 END) AS DATE), 'dd/MM/yyyy') AS week_label,
    CAST(DATE_FORMAT(CAST(DATE_SUB(date_series.calendar_date, CASE WHEN DAYOFWEEK(date_series.calendar_date) = 1 THEN 6 ELSE DAYOFWEEK(date_series.calendar_date) - 2 END) AS DATE), 'yyyyMMdd') AS INT) AS week_sort,
    CAST(DATE_FORMAT(date_series.calendar_date, 'yyyy') AS STRING) AS year_label
FROM date_series
LEFT JOIN silver.gov_uk_bank_holidays AS bh
    ON date_series.calendar_date = bh.holiday_date
    AND bh.region = 'england-and-wales'
