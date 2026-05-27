-- Dimension: Case Statuses
-- Extracts all unique statuses from history status change events
-- Both "from" and "to" statuses are captured

WITH raw_statuses AS (
    SELECT status_to AS status_value
    FROM silver.cms_histories_case_status_transitions

    UNION

    SELECT status_from AS status_value
    FROM silver.cms_histories_case_status_transitions
)
SELECT DISTINCT
    SHA2(status_value, 256) AS case_status_id,
    status_value AS status_name
FROM raw_statuses
WHERE status_value IS NOT NULL
  AND status_value != ''
