-- Silver transformation for sectors
-- Reference table with renamed active column

SELECT
    CAST(id AS BIGINT) AS id,
    CAST(name AS STRING) AS name,
    CAST(symbol AS STRING) AS symbol,
    CAST(active AS BOOLEAN) AS is_active
FROM bronze.cms_sectors
