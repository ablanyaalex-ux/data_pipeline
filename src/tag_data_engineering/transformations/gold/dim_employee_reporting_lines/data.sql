WITH hr_islands AS (
    SELECT
        employee_id,
        CONCAT(first_name, ' ', surname) AS full_name,
        line_manager_id,
        line_manager_name,
        skip_line_manager_id,
        skip_line_manager_name,
        source_file_date,
        ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY source_file_date)
        - ROW_NUMBER() OVER (
            PARTITION BY employee_id, line_manager_id, skip_line_manager_id
            ORDER BY source_file_date
        ) AS island_id,
        hierarchy_level_2 AS company_name
    FROM silver.myhr_hierarchy_history
    WHERE hierarchy_level_2 IN ('Communications', 'Flexible Resolution Services', 'Energy Ombudsman')
),
hr_reporting_lines AS (
    SELECT
        employee_id,
        full_name,
        line_manager_name,
        skip_line_manager_name,
        MIN(source_file_date) AS date_from,
        LEAD(MIN(source_file_date)) OVER (PARTITION BY employee_id ORDER BY MIN(source_file_date)) AS date_to,
        CONCAT(
            employee_id,
            '-',
            COALESCE(line_manager_id, ''),
            '-',
            COALESCE(skip_line_manager_id, ''),
            '-',
            DATE_FORMAT(MIN(source_file_date), 'yyyyMMdd')
        ) AS hierarchy_id,
        company_name
    FROM hr_islands
    GROUP BY employee_id, line_manager_id, skip_line_manager_id, island_id, full_name, line_manager_name, skip_line_manager_name, company_name
),
entra_reporting_lines AS (
    SELECT
        SUBSTRING(SHA2(CONCAT(display_name, CAST(account_created_datetime AS STRING)), 256), 1, 6) AS employee_id,
        display_name AS full_name,
        'davies_resourcing' AS line_manager_name,
        'davies_resourcing' AS skip_line_manager_name,
        account_created_datetime AS date_from,
        CAST(NULL AS TIMESTAMP) AS date_to,
        CONCAT(
            SUBSTRING(SHA2(CONCAT(display_name, CAST(account_created_datetime AS STRING)), 256), 1, 6),
            '-davies_resourcing-davies_resourcing-',
            DATE_FORMAT(account_created_datetime, 'yyyyMMdd')
        ) AS hierarchy_id,
        'davies_resourcing' AS company_name
    FROM silver.entra_users
    WHERE company_name IN ('Davies Group', 'Cynergie Resourcing Limited')
)
SELECT * FROM hr_reporting_lines
UNION ALL
SELECT * FROM entra_reporting_lines
