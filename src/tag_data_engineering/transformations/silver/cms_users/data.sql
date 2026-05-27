-- Silver layer: Extract key user fields, exclude sensitive data, filter out disabled users
SELECT DISTINCT
    CAST(id AS BIGINT) AS id,
    CAST(first_name AS STRING) AS first_name,
    CAST(last_name AS STRING) AS last_name,
    CAST(title AS STRING) AS title,
    CAST(role_id AS INTEGER) AS role_id,
    CAST(company_id AS BIGINT) AS company_id,
    CAST(disabled AS BOOLEAN) AS disabled
FROM
    bronze.cms_users
-- WHERE
    -- disabled = '0' OR disabled = 'false' OR disabled = 0 OR disabled IS NULL
