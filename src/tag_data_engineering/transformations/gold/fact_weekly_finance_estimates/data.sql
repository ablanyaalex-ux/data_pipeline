WITH budgets AS (
    SELECT
        'budget'               AS record_type,
        budget_type            AS finance_type,
        budget_version         AS finance_version,
        budget_year            AS finance_year,
        budget_week_commencing AS period_date,
        budget_sector          AS sector,
        budget_case_status     AS case_status,
        budget_case_volume     AS case_volume,
        budget_case_volume_gbp AS case_volume_gbp,
        source_file_name,
        source_file_date
    FROM silver.finance_weekly_budgets
),

forecasts AS (
    SELECT
        'forecast'              AS record_type,
        forecast_type           AS finance_type,
        forecast_version        AS finance_version,
        forecast_year           AS finance_year,
        forecast_week_commencing AS period_date,
        forecast_sector         AS sector,
        forecast_case_status    AS case_status,
        forecast_case_volume    AS case_volume,
        forecast_case_volume_gbp AS case_volume_gbp,
        source_file_name,
        source_file_date
    FROM silver.finance_weekly_forecasts
),

combined AS (
    SELECT * FROM budgets
    UNION ALL
    SELECT * FROM forecasts
),

latest AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY finance_year, period_date, sector, case_status, record_type
            ORDER BY source_file_date DESC
        ) AS rn
    FROM combined
)

SELECT
    SHA2(CONCAT(
        CAST(record_type AS STRING), '|',
        CAST(finance_year AS STRING), '|',
        CAST(period_date AS STRING), '|',
        CAST(sector AS STRING), '|',
        CAST(case_status AS STRING)
    ), 256)          AS weekly_finance_estimate_id,
    record_type,
    finance_type,
    finance_version,
    finance_year,
    period_date,
    sector,
    case_status,
    case_volume,
    case_volume_gbp,
    source_file_name,
    source_file_date
FROM latest
WHERE rn = 1
