-- Silver transformation for monthly forecasts
-- Transformations: standard casting + convert Month to DATE

SELECT
    CAST(`forecast_type` AS STRING)                 AS forecast_type,
    CAST(`version` AS STRING)                       AS forecast_version,
    CAST(`year` AS INT)                             AS forecast_year,
    TO_DATE(CAST(`month` AS STRING), 'dd/MM/yyyy')  AS forecast_month,
    CAST(`label` AS STRING)                         AS forecast_sector,
    CAST(`case_status` AS STRING)                    AS forecast_case_status,
    CAST(`case_volume` AS DECIMAL(18,6))             AS forecast_case_volume,
    CAST(`case_volume_gbp` AS DECIMAL(18,6))           AS forecast_case_volume_gbp,
    CAST(`source_file_name` AS STRING)              AS source_file_name,
    TO_DATE(REGEXP_REPLACE(ELEMENT_AT(SPLIT(CAST(`source_file_name` AS STRING), '_'), -1), '\\.csv$', ''), 'yyyyMMdd') AS source_file_date
FROM bronze.finance_monthly_forecasts
