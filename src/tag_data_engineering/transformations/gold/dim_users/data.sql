-- Dimension: Users
-- User dimension with derived full name and active status
-- Note: silver.cms_users filters to active users only, so is_active is always true

SELECT
    CAST(id AS BIGINT) AS user_id,
    first_name,
    last_name,
    TRIM(CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, ''))) AS full_name,
    CAST(role_id AS INT) AS role_id,
    CAST(company_id AS BIGINT) AS company_id,
    title,
    CASE WHEN disabled = false OR disabled IS NULL THEN true ELSE false END AS is_active
FROM silver.cms_users
