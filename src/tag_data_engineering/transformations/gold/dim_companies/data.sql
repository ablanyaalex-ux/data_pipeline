SELECT
    CAST(company.id AS BIGINT)   AS company_id,
    CAST(company.name AS STRING) AS company_name
FROM silver.cms_companies AS company
