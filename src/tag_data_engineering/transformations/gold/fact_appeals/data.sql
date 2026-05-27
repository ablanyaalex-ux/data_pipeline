-- Fact: Appeals
-- Appeal events matching query_refined.sql structure

SELECT
    CAST(id AS BIGINT) AS appeal_id,
    CAST(complaint_id AS BIGINT) AS case_id,
    CAST(user_id AS BIGINT) AS user_id,
    created_at AS created_date,
    CAST(DATE_FORMAT(created_at, 'yyyyMMdd') AS INT) AS created_date_id,
    updated_at AS updated_date,
    CAST(DATE_FORMAT(updated_at, 'yyyyMMdd') AS INT) AS updated_date_id,
    CAST(rejected AS INT) AS is_rejected,
    text,
    rejection_reason,
    reason,
    why_evidence_was_unavailable,
    why_evidence_makes_a_difference,
    account_of_events,
    factual_error,
    why_factual_error_makes_a_difference
FROM silver.cms_appeals
