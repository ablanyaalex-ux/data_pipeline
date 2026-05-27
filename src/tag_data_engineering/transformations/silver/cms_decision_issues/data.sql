-- Silver transformation for decision_issues
-- Excludes body field (large text content) for performance

SELECT
    CAST(id AS BIGINT) AS id,
    CAST(decision_id AS BIGINT) AS decision_id,
    CAST(issue AS STRING) AS issue,
    CAST(outcome AS STRING) AS outcome,
    CAST(created_at AS TIMESTAMP) AS created_at,
    CAST(updated_at AS TIMESTAMP) AS updated_at
FROM bronze.cms_decision_issues
