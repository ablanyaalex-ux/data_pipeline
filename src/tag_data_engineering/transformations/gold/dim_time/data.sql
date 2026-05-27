-- Generated dimension: one row per 15-minute interval across a 24-hour day (96 rows total).
-- time_key: HHMM as integer (e.g. 0900, 1445)

WITH quarter_hours AS (
    SELECT EXPLODE(SEQUENCE(0, 95)) AS quarter_hour_of_day
),

time_attributes AS (
    SELECT
        quarter_hour_of_day,
        quarter_hour_of_day * 15 AS minutes_from_midnight,
        FLOOR((quarter_hour_of_day * 15) / 60) AS hour_24,
        (quarter_hour_of_day * 15) % 60 AS minute_of_hour
    FROM quarter_hours
)

SELECT
    CAST(LPAD(CAST(hour_24 AS STRING), 2, '0') || LPAD(CAST(minute_of_hour AS STRING), 2, '0') AS INT) AS time_key,
    CAST(quarter_hour_of_day + 1 AS INT)                                                              AS interval_15_minute_key,
    CAST(minutes_from_midnight AS INT)                                                                AS minutes_from_midnight,
    CAST(hour_24 AS INT)                                                                              AS hour_24,
    CAST(minute_of_hour AS INT)                                                                       AS minute_of_hour,
    CAST(
        LPAD(CAST(hour_24 AS STRING), 2, '0') || ':' || LPAD(CAST(minute_of_hour AS STRING), 2, '0') || ':00'
        AS STRING
    )                                                                                                 AS minimum_interval_time,
    CAST(
        CASE
            WHEN minutes_from_midnight + 15 = 1440 THEN '23:59:59'
            ELSE LPAD(CAST(FLOOR((minutes_from_midnight + 14) / 60) AS STRING), 2, '0')
                || ':'
                || LPAD(CAST(((minutes_from_midnight + 14) % 60) AS STRING), 2, '0')
                || ':59'
        END
        AS STRING
    )                                                                                                 AS maximum_interval_time,
    CAST(
        LPAD(CAST(hour_24 AS STRING), 2, '0') || ':' || LPAD(CAST(minute_of_hour AS STRING), 2, '0')
        AS STRING
    )                                                                                                 AS time_24h,
    CAST(
        DATE_FORMAT(
            TO_TIMESTAMP(
                CONCAT(
                    '2000-01-01 ',
                    LPAD(CAST(hour_24 AS STRING), 2, '0'),
                    ':',
                    LPAD(CAST(minute_of_hour AS STRING), 2, '0'),
                    ':00'
                )
            ),
            'hh:mm a'
        )
        AS STRING
    )                                                                                                 AS time_12h,
    CAST(
        LPAD(CAST(hour_24 AS STRING), 2, '0') || ':' || LPAD(CAST(minute_of_hour AS STRING), 2, '0') || ':00'
        AS STRING
    )                                                                                                 AS time_24h_with_seconds,
    CAST(
        LPAD(CAST(hour_24 AS STRING), 2, '0') || ':' || LPAD(CAST(minute_of_hour AS STRING), 2, '0')
            || ' - ' ||
            CASE
                WHEN minutes_from_midnight + 15 = 1440 THEN '24:00'
                ELSE LPAD(CAST(FLOOR((minutes_from_midnight + 15) / 60) AS STRING), 2, '0')
                    || ':'
                    || LPAD(CAST(((minutes_from_midnight + 15) % 60) AS STRING), 2, '0')
            END
        AS STRING
    )                                                                                                 AS interval_15_minute_label,
    CASE
        WHEN hour_24 BETWEEN 8 AND 17 THEN TRUE
        ELSE FALSE
    END                                                                                               AS is_business_hours
FROM time_attributes
