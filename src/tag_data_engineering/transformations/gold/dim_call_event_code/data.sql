SELECT
    SHA2(CONCAT(CAST(event_type AS STRING), '|', CAST(result_code AS STRING)), 256) AS call_event_code_id,
    CAST(event_type AS STRING)         AS event_type,
    CAST(result_code AS STRING)        AS result_code,
    CAST(event_description AS STRING)  AS event_description,
    CAST(is_dropped AS INT)            AS is_dropped,
    CAST(is_queue_answered AS INT)     AS is_queue_answered,
    CAST(is_timed_out AS INT)          AS is_timed_out,
    CAST(is_volume AS INT)             AS is_volume,
    CAST(is_call_answered AS INT)      AS is_call_answered
FROM silver.puzzel_call_event_codes
