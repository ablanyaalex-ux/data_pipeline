SELECT
    CAST(`region` AS STRING)       AS region,
    TO_DATE(`holiday_date`, 'dd/MM/yyyy') AS holiday_date,
    CAST(`holiday_name` AS STRING) AS holiday_name,
    CAST(`notes` AS STRING)        AS notes,
    CAST(`is_bunting` AS BOOLEAN)  AS is_bunting,
    CAST(`source_file_name` AS STRING) AS source_file_name
FROM bronze.gov_uk_bank_holidays
