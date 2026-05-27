-- Silver transformation for decision remedies

SELECT DISTINCT
  CAST(id AS BIGINT) AS id,
  CAST(remedy AS STRING) AS remedy,
  CAST(description AS STRING) AS description,
  CAST(decision_id AS BIGINT) AS decision_id,
  CAST(created_at AS TIMESTAMP) AS created_at,
  CAST(updated_at AS TIMESTAMP) AS updated_at,
  CAST(value AS DECIMAL(15,2)) AS value
FROM bronze.cms_decision_remedies
