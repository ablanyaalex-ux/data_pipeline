-- Silver transformation for comments

SELECT DISTINCT
  CAST(id AS BIGINT) AS id,
  CAST(text AS STRING) AS text,
  CAST(published AS BOOLEAN) AS published,
  CAST(base_type AS STRING) AS base_type,
  CAST(base_id AS BIGINT) AS base_id,
  CAST(author_id AS BIGINT) AS author_id,
  CAST(created_at AS TIMESTAMP) AS created_at,
  CAST(updated_at AS TIMESTAMP) AS updated_at,
  CAST(proposed AS BOOLEAN) AS proposed,
  CAST(author_type AS STRING) AS author_type,
  CAST(disputed AS BOOLEAN) AS disputed,
  CAST(parent_id AS INT) AS parent_id,
  CAST(comment_type AS STRING) AS comment_type,
  CAST(accepted AS BOOLEAN) AS accepted
FROM bronze.cms_comments
