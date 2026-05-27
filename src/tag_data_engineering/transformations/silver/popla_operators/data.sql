SELECT
    CAST(operator_code AS STRING)          AS operator_code,
    CAST(email AS STRING)                  AS email,
    CAST(name AS STRING)                   AS name,
    CAST(phone AS STRING)                  AS phone,
    CAST(portal_account_status AS STRING)  AS portal_account_status,
    CAST(url AS STRING)                    AS url,
    CAST(country AS STRING)                AS country
FROM
    bronze.popla_operators
