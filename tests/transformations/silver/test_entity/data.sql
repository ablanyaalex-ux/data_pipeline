SELECT
  CAST(id AS INT) AS id,
  name,
  CAST(value AS INT) AS value,
  description
FROM bronze.test_entity
