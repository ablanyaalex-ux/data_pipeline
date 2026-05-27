-- Silver layer: Clean and type history records
-- Keeps details column for gold layer parsing
SELECT DISTINCT
    CAST(id AS BIGINT) AS id,
    CAST(event AS STRING) AS event,
    CAST(details AS STRING) AS details,
    CAST(complaint_id AS BIGINT) AS complaint_id,
    CAST(user_id AS BIGINT) AS user_id,
    CAST(created_at AS TIMESTAMP) AS created_at
FROM
    bronze.cms_histories
