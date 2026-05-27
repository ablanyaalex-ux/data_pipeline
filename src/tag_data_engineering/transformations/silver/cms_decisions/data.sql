-- Silver layer: Clean and type decision records
SELECT DISTINCT
    CAST(id AS BIGINT) AS id,
    CAST(author_id AS BIGINT) AS author_id,
    CAST(complaint_id AS BIGINT) AS complaint_id,
    CAST(created_at AS TIMESTAMP) AS created_at,
    CAST(updated_at AS TIMESTAMP) AS updated_at,
    CAST(published AS BOOLEAN) AS published,
    CAST(final AS BOOLEAN) AS final,
    CAST(outcome AS STRING) AS outcome,
    CAST(service_type_id AS BIGINT) AS service_type_id,
    CAST(final_challenge_type AS STRING) AS final_challenge_type,
    CAST(published_at AS TIMESTAMP) AS published_at
FROM
    bronze.cms_decisions
