-- Dimension: Roles
-- Maps roles to groups for attribution analysis (consumer vs OS staff)

SELECT
    CAST(id AS BIGINT) AS role_id,
    name AS role_name,
    symbol AS role_symbol,
    description,
    CASE
        WHEN id = 1 THEN 'consumer'
        WHEN id = 2 THEN 'company_user'
        WHEN id BETWEEN 3 AND 14 THEN 'internal'
        ELSE 'unknown'
    END AS role_group
FROM silver.cms_roles
