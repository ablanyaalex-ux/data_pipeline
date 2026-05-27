SELECT
    SHA2(CONCAT(CAST(employee_id AS STRING), '|', CAST(alias_name AS STRING)), 256) AS employee_alias_id,
    CAST(hr_name AS STRING)     AS hr_name,
    CAST(alias_name AS STRING)  AS alias_name,
    CAST(employee_id AS STRING) AS employee_id,
    CAST(systems AS STRING)     AS systems
FROM silver.ref_employee_aliases
