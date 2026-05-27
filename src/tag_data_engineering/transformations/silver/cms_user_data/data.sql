-- Silver transformation for user_data
-- Excludes PII fields (names, addresses, phones, emails, account numbers)
-- Retains only non-sensitive location and status fields

SELECT
    CAST(id AS BIGINT) AS id,
    CAST(city AS STRING) AS city,
    CAST(postcode AS STRING) AS postcode,
    CAST(country AS STRING) AS country,
    CASE WHEN business_name IS NOT NULL AND business_name != '' THEN TRUE ELSE FALSE END AS is_business,
    CAST(already_complaint AS BOOLEAN) AS already_complaint,
    CAST(deceased AS BOOLEAN) AS is_deceased
FROM bronze.cms_user_data
