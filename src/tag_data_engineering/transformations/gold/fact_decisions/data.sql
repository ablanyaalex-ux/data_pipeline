-- Fact: Decisions
-- Decision events matching query_refined.sql structure

SELECT
    CAST(id AS BIGINT) AS decision_id,
    CAST(complaint_id AS BIGINT) AS case_id,
    CAST(author_id AS BIGINT) AS user_id,
    created_at AS created_date,
    CAST(DATE_FORMAT(created_at, 'yyyyMMdd') AS INT) AS created_date_id,
    updated_at AS updated_date,
    CAST(DATE_FORMAT(updated_at, 'yyyyMMdd') AS INT) AS updated_date_id,
    published_at AS published_date,
    CAST(DATE_FORMAT(published_at, 'yyyyMMdd') AS INT) AS published_date_id,
    CAST(published AS INT) AS is_published,
    CAST(final AS INT) AS is_final,
    outcome
FROM silver.cms_decisions
