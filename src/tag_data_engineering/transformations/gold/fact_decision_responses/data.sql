-- Fact: Decision Responses
-- Tracks consumer, supplier (company/system), and system responses to initial decisions
-- Replaces consumer_responses, supplier_responses_*, system_responses CTEs

WITH initial_decision_context AS (
    SELECT
        fcid.case_id,
        fcid.initial_decision_id,
        fd.created_date AS decision_created_at
    FROM gold.fact_case_initial_decisions fcid
    INNER JOIN gold.fact_decisions fd ON fcid.initial_decision_id = fd.decision_id
),
-- Consumer responses (role_id NOT IN 0, 2, -2)
consumer_responses AS (
    SELECT
        case_id,
        consumer_response_date,
        consumer_response_user_id,
        consumer_response_action
    FROM (
        SELECT
            fcst.case_id,
            fcst.transition_date AS consumer_response_date,
            fcst.user_id AS consumer_response_user_id,
            fcst.status_action AS consumer_response_action,
            ROW_NUMBER() OVER (PARTITION BY fcst.case_id ORDER BY fcst.transition_date) AS rn
        FROM gold.fact_case_status_transitions fcst
        INNER JOIN gold.dim_users u ON fcst.user_id = u.user_id
        INNER JOIN initial_decision_context idc ON fcst.case_id = idc.case_id
        WHERE fcst.status_from IN ('decision issued', 'company decision issued', 'customer decision issued', 'final response required', 'under appeal noresponse')
          AND u.role_id NOT IN (0, 2, -2)  -- Exclude unknown, company, and system
          AND fcst.transition_date > idc.decision_created_at
    )
    WHERE rn = 1
),
-- Company responses (role_id = 2)
supplier_responses_company AS (
    SELECT
        case_id,
        supplier_response_date,
        supplier_response_user_id,
        supplier_response_action
    FROM (
        SELECT
            fcst.case_id,
            fcst.transition_date AS supplier_response_date,
            fcst.user_id AS supplier_response_user_id,
            fcst.status_action AS supplier_response_action,
            ROW_NUMBER() OVER (PARTITION BY fcst.case_id ORDER BY fcst.transition_date) AS rn
        FROM gold.fact_case_status_transitions fcst
        INNER JOIN gold.dim_users u ON fcst.user_id = u.user_id
        INNER JOIN initial_decision_context idc ON fcst.case_id = idc.case_id
        WHERE fcst.status_from IN ('decision issued', 'company decision issued', 'customer decision issued', 'final response required')
          AND u.role_id = 2  -- Company user
          AND fcst.transition_date > idc.decision_created_at
    )
    WHERE rn = 1
),
-- System responses for supplier (role_id = -2) - fallback when no company response
supplier_responses_system AS (
    SELECT
        case_id,
        supplier_response_date,
        supplier_response_user_id,
        supplier_response_action
    FROM (
        SELECT
            fcst.case_id,
            fcst.transition_date AS supplier_response_date,
            fcst.user_id AS supplier_response_user_id,
            fcst.status_action AS supplier_response_action,
            ROW_NUMBER() OVER (PARTITION BY fcst.case_id ORDER BY fcst.transition_date) AS rn
        FROM gold.fact_case_status_transitions fcst
        INNER JOIN gold.dim_users u ON fcst.user_id = u.user_id
        INNER JOIN initial_decision_context idc ON fcst.case_id = idc.case_id
        WHERE fcst.status_from IN ('decision issued', 'company decision issued', 'customer decision issued', 'final response required')
          AND u.role_id = -2  -- System user
          AND fcst.transition_date > idc.decision_created_at
    )
    WHERE rn = 1
),
-- Combined supplier responses (company takes priority over system)
supplier_responses AS (
    SELECT
        COALESCE(src.case_id, srs.case_id) AS case_id,
        CASE
            WHEN src.supplier_response_action IS NOT NULL THEN src.supplier_response_action
            WHEN srs.supplier_response_action IS NOT NULL THEN srs.supplier_response_action
        END AS supplier_response_action,
        CASE
            WHEN src.supplier_response_date IS NOT NULL THEN src.supplier_response_date
            WHEN srs.supplier_response_date IS NOT NULL THEN srs.supplier_response_date
        END AS supplier_response_date,
        CASE
            WHEN src.supplier_response_user_id IS NOT NULL THEN src.supplier_response_user_id
            WHEN srs.supplier_response_user_id IS NOT NULL THEN srs.supplier_response_user_id
        END AS supplier_response_user_id
    FROM supplier_responses_company src
    FULL OUTER JOIN supplier_responses_system srs ON src.case_id = srs.case_id
),
-- System responses for "No Response" scenarios (role_id = -2, action = 'complete decision by system')
system_no_responses AS (
    SELECT
        fcst.case_id,
        MIN(fcst.transition_date) AS system_response_date,
        MAX(fcst.user_id) AS system_response_user_id,
        MAX(fcst.status_action) AS system_response_action
    FROM gold.fact_case_status_transitions fcst
    INNER JOIN gold.dim_users u ON fcst.user_id = u.user_id
    INNER JOIN initial_decision_context idc ON fcst.case_id = idc.case_id
    WHERE fcst.status_from IN ('decision issued', 'company decision issued', 'customer decision issued', 'final response required', 'under appeal noresponse')
      AND u.role_id = -2  -- System
      AND fcst.transition_date > idc.decision_created_at
      AND fcst.status_action = 'complete decision by system'
    GROUP BY fcst.case_id
),
all_cases_with_decisions AS (
    SELECT DISTINCT case_id
    FROM initial_decision_context
)
SELECT
    c.case_id,
    cr.consumer_response_date,
    cr.consumer_response_user_id,
    cr.consumer_response_action,
    sr.supplier_response_date,
    sr.supplier_response_user_id,
    sr.supplier_response_action,
    snr.system_response_date,
    snr.system_response_user_id,
    snr.system_response_action
FROM all_cases_with_decisions c
LEFT JOIN consumer_responses cr ON c.case_id = cr.case_id
LEFT JOIN supplier_responses sr ON c.case_id = sr.case_id
LEFT JOIN system_no_responses snr ON c.case_id = snr.case_id
WHERE cr.consumer_response_date IS NOT NULL
   OR sr.supplier_response_date IS NOT NULL
   OR snr.system_response_date IS NOT NULL
