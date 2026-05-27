-- Silver: Case Status Transitions from Histories
-- Extracts and parses status change events from cms_histories
-- Provides cleaned "from" and "to" statuses and extracted actions for downstream gold layer consumption

SELECT
    CAST(id AS BIGINT) AS histories_id,
    CAST(complaint_id AS BIGINT) AS complaint_id,
    CAST(user_id AS BIGINT) AS user_id,
    CAST(created_at AS TIMESTAMP) AS created_at,
    LOWER(TRIM(REPLACE(SUBSTRING(details, LOCATE(' to ', details) + 4), '_', ' '))) AS status_to,
    LOWER(TRIM(REPLACE(SUBSTRING(details, 1, LOCATE(' to ', details) - 1), '_', ' '))) AS status_from,
    CASE WHEN event LIKE '%[%]%'
        THEN LOWER(TRIM(REPLACE(SUBSTRING(event, LOCATE('[', event) + 1, LOCATE(']', event) - LOCATE('[', event) - 1), '_', ' ')))
        ELSE NULL
    END AS status_action
FROM bronze.cms_histories
WHERE event LIKE 'Status Changed %'
  AND LOCATE(' to ', details) > 0
