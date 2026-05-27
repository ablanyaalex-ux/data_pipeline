SELECT
    CAST(id AS BIGINT) AS id,
    CAST(name AS STRING) AS name,
    CAST(symbol AS STRING) AS symbol
FROM bronze.cms_channels
