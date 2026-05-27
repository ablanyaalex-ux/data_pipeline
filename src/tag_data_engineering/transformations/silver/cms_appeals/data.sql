-- Silver layer: Clean and type appeal records
SELECT DISTINCT
    CAST(id AS BIGINT) AS id,
    CAST(user_id AS BIGINT) AS user_id,
    CAST(complaint_id AS BIGINT) AS complaint_id,
    CAST(created_at AS TIMESTAMP) AS created_at,
    CAST(updated_at AS TIMESTAMP) AS updated_at,
    CAST(rejected AS BOOLEAN) AS rejected,
    CAST(text AS STRING) AS text,
    CAST(rejection_reason AS STRING) AS rejection_reason,
    CAST(reason AS STRING) AS reason,
    CAST(why_evidence_was_unavailable AS STRING) AS why_evidence_was_unavailable,
    CAST(why_evidence_makes_a_difference AS STRING) AS why_evidence_makes_a_difference,
    CAST(account_of_events AS STRING) AS account_of_events,
    CAST(factual_error AS STRING) AS factual_error,
    CAST(why_factual_error_makes_a_difference AS STRING) AS why_factual_error_makes_a_difference
FROM
    bronze.cms_appeals
