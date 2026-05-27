SELECT
    CAST(queue_key AS STRING)    AS queue_key,
    MAX(CAST(descript AS STRING)) AS queue_name
FROM silver.puzzel_queues
GROUP BY queue_key
