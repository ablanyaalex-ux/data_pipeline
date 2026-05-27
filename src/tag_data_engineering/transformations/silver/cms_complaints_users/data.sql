-- Silver transformation for complaint_users
-- Junction table linking complaints to assigned users

SELECT
    CAST(complaint_id AS BIGINT) AS complaint_id,
    CAST(user_id AS BIGINT) AS user_id
FROM bronze.cms_complaints_users
