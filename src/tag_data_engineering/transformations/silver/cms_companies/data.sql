-- Silver layer: Apply transformations, typing, and business logic
SELECT DISTINCT
    CAST(id AS BIGINT) AS id,
    COALESCE(name, CONCAT('Unknown company ', id)) AS name,
    COALESCE(reporting_name, CONCAT('Unknown company ', id)) AS reporting_name
FROM
    bronze.cms_companies
WHERE
    active IS NULL OR active != '0'
