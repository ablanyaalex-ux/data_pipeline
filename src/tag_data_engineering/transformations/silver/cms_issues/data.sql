-- Silver transformation for issues

SELECT DISTINCT
  CAST(id AS BIGINT) AS id,
  CAST(name AS STRING) AS name,
  CAST(active AS BOOLEAN) AS active
FROM bronze.cms_issues
