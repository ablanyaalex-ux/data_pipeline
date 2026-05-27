-- Fact: Case Key Dates
-- Centralized date calculations for key case events
-- Replaces investigate_dates, appeal_dates, appeal_pending_dates, appeal_assigned_dates CTEs

WITH first_investigate_dates AS (
    SELECT
        fcst.case_id,
        MIN(fcst.transition_date) AS first_investigate_date
    FROM gold.fact_case_status_transitions fcst
    INNER JOIN gold.dim_case_statuses dcs
        ON fcst.status_to_id = dcs.case_status_id
        AND dcs.status_name = 'investigate'
    GROUP BY fcst.case_id
),
first_appeal_dates AS (
    SELECT
        case_id,
        MIN(created_date) AS first_appeal_date
    FROM gold.fact_appeals
    GROUP BY case_id
),
first_appeal_pending_dates AS (
    SELECT
        fcst.case_id,
        MIN(fcst.transition_date) AS first_appeal_pending_date
    FROM gold.fact_case_status_transitions fcst
    INNER JOIN gold.dim_case_statuses dcs
        ON fcst.status_to_id = dcs.case_status_id
        AND dcs.status_name = 'pending appeal'
    GROUP BY fcst.case_id
),
first_appeal_assigned_dates AS (
    SELECT
        fcst.case_id,
        MIN(fcst.transition_date) AS first_appeal_assigned_date
    FROM gold.fact_case_status_transitions fcst
    WHERE fcst.status_to = 'pending appeal'
      AND fcst.status_action = 'appeal_assigned'
    GROUP BY fcst.case_id
),
first_decision_publish_dates AS (
    SELECT
        complaint_id AS case_id,
        MIN(created_at) AS first_decision_publish_date
    FROM silver.cms_histories
    WHERE event = 'Publish Decision'
    GROUP BY complaint_id
)
SELECT
    c.case_id,
    i.first_investigate_date,
    a.first_appeal_date,
    p.first_appeal_pending_date,
    aa.first_appeal_assigned_date,
    fdpd.first_decision_publish_date
FROM gold.dim_cases c
LEFT JOIN first_investigate_dates i ON c.case_id = i.case_id
LEFT JOIN first_appeal_dates a ON c.case_id = a.case_id
LEFT JOIN first_appeal_pending_dates p ON c.case_id = p.case_id
LEFT JOIN first_appeal_assigned_dates aa ON c.case_id = aa.case_id
LEFT JOIN first_decision_publish_dates fdpd ON c.case_id = fdpd.case_id
