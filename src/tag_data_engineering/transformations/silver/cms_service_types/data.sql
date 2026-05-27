-- Silver transformation for service_types
-- Reference table with renamed boolean columns

SELECT
    CAST(id AS BIGINT) AS id,
    CAST(name AS STRING) AS name,
    CAST(sector_id AS BIGINT) AS sector_id,
    CAST(category_id AS BIGINT) AS category_id,
    CAST(active AS BOOLEAN) AS is_active,
    CAST(voluntary_jurisdiction AS BOOLEAN) AS is_voluntary_jurisdiction
FROM bronze.cms_service_types
