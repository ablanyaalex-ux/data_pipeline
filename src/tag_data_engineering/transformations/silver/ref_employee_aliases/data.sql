SELECT
    CAST(`hr_name` AS STRING)     AS hr_name,
    CAST(`alias_name` AS STRING)  AS alias_name,
    CAST(`employee_id` AS STRING) AS employee_id,
    CAST(`systems` AS STRING)     AS systems
FROM bronze.ref_employee_aliases
