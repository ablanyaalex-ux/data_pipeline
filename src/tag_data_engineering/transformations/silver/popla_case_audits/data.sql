SELECT
    CAST(id AS BIGINT)                       AS id,
    CAST(case_verification_code AS STRING)   AS case_verification_code,
    CAST(actioned_by AS STRING)              AS actioned_by,
    CAST(`timestamp` AS TIMESTAMP)           AS timestamp,
    CAST(description AS STRING)              AS description,
    CAST(event_type AS STRING)               AS event_type,
    CAST(draft_case_id AS STRING)            AS draft_case_id
FROM
    bronze.popla_case_audits
