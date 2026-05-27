SELECT
    CAST(user_id AS BIGINT)                  AS user_id,
    CAST(email AS STRING)                    AS email,
    CAST(password AS STRING)                 AS password,
    CAST(user_type AS STRING)                AS user_type,
    CAST(roles AS STRING)                    AS roles,
    CAST(name AS STRING)                     AS name,
    CAST(login_attempts AS BIGINT)           AS login_attempts,
    CAST(account_locked AS BIGINT)           AS account_locked,
    CAST(disabled AS BIGINT)                 AS disabled,
    CAST(reset_requested_at AS TIMESTAMP)    AS reset_requested_at,
    CAST(reset_token AS STRING)              AS reset_token,
    CAST(role_id AS BIGINT)                  AS role_id
FROM
    bronze.popla_users
