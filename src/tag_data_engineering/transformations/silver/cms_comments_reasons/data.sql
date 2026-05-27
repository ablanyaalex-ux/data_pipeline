-- Silver transformation for comments_reasons

SELECT DISTINCT
  CAST(id AS BIGINT) AS id,
  CAST(reason_type AS STRING) AS reason_type,
  CAST(text AS STRING) AS text,
  CAST(comment_id AS BIGINT) AS comment_id,
  CAST(created_at AS TIMESTAMP) AS created_at,
  CAST(updated_at AS TIMESTAMP) AS updated_at
FROM bronze.cms_comments_reasons
