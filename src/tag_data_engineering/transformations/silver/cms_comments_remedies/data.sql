-- Silver transformation for comments_remedies

SELECT DISTINCT
  CAST(id AS BIGINT) AS id,
  CAST(remedy_type AS STRING) AS remedy_type,
  CAST(text AS STRING) AS text,
  CAST(comment_id AS BIGINT) AS comment_id,
  CAST(created_at AS TIMESTAMP) AS created_at,
  CAST(updated_at AS TIMESTAMP) AS updated_at,
  CAST(value AS DECIMAL(15,2)) AS value,
  CAST(implemented_at AS TIMESTAMP) AS implemented_at
FROM bronze.cms_comments_remedies
