-- Complete history of DRE case assignments derived from CMS histories events.
-- Each row represents one assignment or unassignment event for a case.

WITH assigned_agent_events AS (
    SELECT
        CAST(hist.id AS BIGINT)            AS histories_id,
        CAST(hist.complaint_id AS BIGINT)  AS case_id,
        CAST(hist.created_at AS TIMESTAMP) AS transition_at,
        CAST(hist.created_at AS DATE)      AS transition_date,
        CAST(hist.event AS STRING)         AS assignment_event,
        CAST(hist.details AS STRING)       AS assignment_details,
        CASE
            WHEN LOWER(hist.event) LIKE 'dre%unassigned%'
             AND LOWER(hist.details) LIKE '% unassigned from the case'
                THEN 'unassigned'
            ELSE 'assigned'
        END AS assignment_action,

        CASE
            WHEN (
                LOWER(hist.details) LIKE 'i % have assigned myself using get next'
                OR LOWER(hist.details) LIKE 'i % have assigned myself using get-next'
            )
                THEN TRIM(
                    REGEXP_EXTRACT(
                        CAST(hist.details AS STRING),
                        '^I\\s+(.*?)\\s+have assigned myself using Get(?:-| )Next$',
                        1
                    )
                )

            ELSE TRIM(
                REGEXP_EXTRACT(
                    CAST(hist.details AS STRING),
                    '^(.*)\\s\\([^()]+\\)\\s(?:assigned|unassigned from the case)$',
                    1
                )
            )
        END AS parsed_assigned_agent_name

    FROM silver.cms_histories AS hist
    WHERE hist.complaint_id IS NOT NULL
      AND LOWER(hist.event) <> 'manual status change'
      AND (
            (
                LOWER(hist.event) LIKE 'dre%assigned%'
                AND LOWER(hist.details) LIKE '% assigned'
                AND LOWER(hist.details) NOT LIKE '% assigned to %'
            )
            OR
            (
                LOWER(hist.event) LIKE 'dre%unassigned%'
                AND LOWER(hist.details) LIKE '% unassigned from the case'
            )
            OR
            (
                (
                    LOWER(hist.details) LIKE 'i % have assigned myself using get next'
                    OR LOWER(hist.details) LIKE 'i % have assigned myself using get-next'
                )
                AND (
                    LOWER(hist.event) LIKE 'dre%assigned%'
                    OR LOWER(hist.event) LIKE 'case allocation - %'
                )
            )
      )
)

SELECT
    assigned_agent_events.case_id,
    from_utc_timestamp(assigned_agent_events.transition_date, 'Europe/London')               AS transition_date,
    CAST(assigned_agent_events.assignment_action AS STRING)                                  AS assignment_action,
    CAST(assigned_agent_events.parsed_assigned_agent_name AS STRING)                         AS parsed_assigned_agent_name,

    ROW_NUMBER() OVER (
        PARTITION BY assigned_agent_events.case_id
        ORDER BY
            assigned_agent_events.transition_at,
            assigned_agent_events.histories_id
    ) AS case_assignment_sequence,

    CASE
        WHEN ROW_NUMBER() OVER (
            PARTITION BY assigned_agent_events.case_id
            ORDER BY
                assigned_agent_events.transition_at DESC,
                assigned_agent_events.histories_id DESC
        ) = 1 THEN 1
        ELSE 0
    END AS is_latest_assignment_for_case,

    CAST(DATE_FORMAT(from_utc_timestamp(assigned_agent_events.transition_date, 'Europe/London'), 'yyyyMMdd') AS INT) AS transition_date_key
FROM assigned_agent_events
WHERE assigned_agent_events.transition_date >= trunc(add_months(current_date(), -24), 'MM')
