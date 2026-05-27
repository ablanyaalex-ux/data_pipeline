-- Silver transformation for roles
-- Simple reference table - all columns retained

SELECT
    CAST(id AS BIGINT) AS id,
    CAST(name AS STRING) AS name,
    CAST(symbol AS STRING) AS symbol,
    CAST(description AS STRING) AS description,
    CAST(role_type AS STRING) AS role_type
FROM bronze.cms_roles
