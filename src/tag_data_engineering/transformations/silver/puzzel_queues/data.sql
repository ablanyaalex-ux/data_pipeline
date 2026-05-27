-- Silver layer: Clean and type queues records

SELECT
  CAST(service_num AS STRING) AS service_num,
  CAST(queue_key AS STRING) AS queue_key,
  CAST(descript AS STRING) AS descript
FROM bronze.puzzel_queues;
