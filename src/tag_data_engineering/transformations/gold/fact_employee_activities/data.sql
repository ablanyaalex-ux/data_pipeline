SELECT
    SHA2(CONCAT(
        COALESCE(CAST(eu.org_hierarchy_level_4 AS STRING), ''), '|',
        CAST(CAST(rb.adherence_start_date AS DATE) AS STRING), '|',
        COALESCE(CAST(eu.employee_id AS STRING), ''), '|',
        COALESCE(split(rb.activity_name, '_')[0], ''), '|',
        COALESCE(CAST(mp.activity_type AS STRING), ''), '|',
        COALESCE(CAST(mp.activity_group AS STRING), ''), '|',
        CAST(rb.is_paid AS STRING), '|',
        COALESCE(CAST(fert.hierarchy_id AS STRING), '')
    ), 256)                                                     AS employee_activity_id,
    CAST(eu.org_hierarchy_level_4 AS STRING)                    AS campaign,
    CAST(rb.adherence_start_date AS DATE)                       AS start_date,
    CAST(eu.employee_id AS STRING)                              AS employee_id,
    CAST(eu.display_name AS STRING)                             AS display_name,
    CAST(split(rb.activity_name, '_')[0] AS STRING)             AS activity_type,
    CAST(mp.activity_type AS STRING)                            AS activity_type_mapped,
    CAST(mp.activity_group AS STRING)                           AS activity_grouping,
    SUM(CASE WHEN rb.is_paid = true THEN (unix_timestamp(rb.activity_end_time) - unix_timestamp(rb.activity_start_time)) ELSE 0 END) AS total_duration_seconds,
    CAST(ROUND(SUM(CASE WHEN rb.is_paid = true THEN (unix_timestamp(rb.activity_end_time) - unix_timestamp(rb.activity_start_time)) ELSE 0 END) / 60.0, 2) AS DOUBLE) AS total_duration_minutes,
    CAST(ROUND(SUM(CASE WHEN rb.is_paid = true THEN (unix_timestamp(rb.activity_end_time) - unix_timestamp(rb.activity_start_time)) ELSE 0 END) / 3600.0, 2) AS DOUBLE) AS total_duration_hours,
    CAST(rb.is_paid AS BOOLEAN)                                 AS is_paid,
    CAST(eu.org_hierarchy_level_3 AS STRING)                    AS business_unit,
    CAST(fert.hierarchy_id AS STRING)                           AS hierarchy_id,
    CAST(DATE_FORMAT(CAST(rb.adherence_start_date AS DATE), 'yyyyMMdd') AS INT) AS start_date_key
FROM silver.verint_employee_adherence_expected_activities rb
LEFT JOIN silver.verint_activity_mapping mp
    ON LOWER(split(rb.activity_name, '_')[0]) = LOWER(mp.activity_name)
LEFT JOIN silver.entra_users eu
    ON LOWER(eu.user_principal_name) = LOWER(rb.employee_identifier)
LEFT JOIN gold.dim_employee_reporting_lines fert
    ON eu.employee_id = fert.employee_id
    AND rb.adherence_start_date BETWEEN fert.date_from AND COALESCE(fert.date_to, '9999-12-31')
GROUP BY
    eu.org_hierarchy_level_4,
    rb.adherence_start_date,
    eu.employee_id,
    eu.display_name,
    split(rb.activity_name, '_')[0],
    mp.activity_type,
    mp.activity_group,
    rb.is_paid,
    eu.org_hierarchy_level_3,
    fert.hierarchy_id
