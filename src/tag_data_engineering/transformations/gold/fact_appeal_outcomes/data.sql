-- Fact: Appeal Outcomes
-- Tracks appeal outcomes, party involvement, and assignment status
-- Replaces appeals_by_party and appeal_outcomes CTEs

WITH appeals_by_party AS (
    SELECT
        fa.case_id,
        MAX(CASE WHEN dr.role_group = 'consumer' THEN 1 ELSE 0 END) AS has_consumer_appeal,
        MAX(CASE WHEN dr.role_group = 'company_user' THEN 1 ELSE 0 END) AS has_company_appeal,
        MAX(CASE WHEN dr.role_group = 'internal' THEN 1 ELSE 0 END) AS has_internal_appeal
    FROM gold.fact_appeals fa
    LEFT JOIN gold.dim_users du ON fa.user_id = du.user_id
    LEFT JOIN gold.dim_roles dr ON du.role_id = dr.role_id
    GROUP BY fa.case_id
),
latest_case_status AS (
    SELECT
        fcst.case_id,
        dcs.status_name AS current_status
    FROM gold.fact_case_status_transitions fcst
    INNER JOIN gold.dim_case_statuses dcs ON fcst.status_to_id = dcs.case_status_id
    INNER JOIN (
        SELECT
            case_id,
            MAX(transition_date) AS latest_transition
        FROM gold.fact_case_status_transitions
        GROUP BY case_id
    ) latest
        ON fcst.case_id = latest.case_id
        AND fcst.transition_date = latest.latest_transition
),
cases_with_appeal_assigned AS (
    SELECT DISTINCT case_id
    FROM gold.fact_case_status_transitions
    WHERE status_action = 'appeal_assigned'
),
appeal_outcomes AS (
    SELECT
        fcst.case_id,
        -- Status-based detection (transitions)
        MAX(CASE
            WHEN dcs.status_name LIKE '%maintained decision%'
                OR dcs.status_name LIKE '%maintain decision%'
            THEN 1 ELSE 0
        END) AS has_rejected_appeal_status,
        MAX(CASE
            WHEN dcs.status_name LIKE '%changed decision%'
                OR dcs.status_name LIKE '%change decision%'
                OR dcs.status_name LIKE '%decided appeal accepted%'
            THEN 1 ELSE 0
        END) AS has_accepted_appeal_status,
        -- Action-based detection
        MAX(CASE
            WHEN fcst.status_action = 'maintain decision'
            THEN 1 ELSE 0
        END) AS has_rejected_appeal_action,
        MAX(CASE
            WHEN fcst.status_action = 'change decision'
            THEN 1 ELSE 0
        END) AS has_accepted_appeal_action,
        -- Ongoing appeals detection (current status only)
        MAX(CASE
            WHEN lcs.current_status IN ('under appeal', 'appeal decision overdue', 'joint appeal', 'company appeal', 'under customer appeal', 'check appeal evidence', 'under appeal noresponse')
            THEN 1 ELSE 0
        END) AS has_ongoing_appeal,
        -- Appeal assignment detection
        MAX(CASE
            WHEN cwaa.case_id IS NOT NULL
            THEN 1 ELSE 0
        END) AS has_appeal_assigned
    FROM gold.fact_case_status_transitions fcst
    LEFT JOIN gold.dim_case_statuses dcs ON fcst.status_to_id = dcs.case_status_id
    LEFT JOIN latest_case_status lcs ON fcst.case_id = lcs.case_id
    LEFT JOIN cases_with_appeal_assigned cwaa ON fcst.case_id = cwaa.case_id
    -- Only look at cases that have had appeals
    WHERE EXISTS (SELECT 1 FROM gold.fact_appeals fa WHERE fa.case_id = fcst.case_id)
    GROUP BY fcst.case_id
),
all_cases_with_appeals AS (
    SELECT DISTINCT case_id
    FROM gold.fact_appeals
)
SELECT
    c.case_id,
    -- Party flags
    COALESCE(abp.has_consumer_appeal, 0) AS has_consumer_appeal,
    COALESCE(abp.has_company_appeal, 0) AS has_company_appeal,
    COALESCE(abp.has_internal_appeal, 0) AS has_internal_appeal,
    -- Combined consumer flag (consumer OR internal)
    GREATEST(COALESCE(abp.has_consumer_appeal, 0), COALESCE(abp.has_internal_appeal, 0)) AS has_consumer_or_internal_appeal,
    -- Outcome flags (status-based)
    COALESCE(ao.has_rejected_appeal_status, 0) AS has_rejected_appeal_status,
    COALESCE(ao.has_accepted_appeal_status, 0) AS has_accepted_appeal_status,
    -- Outcome flags (action-based)
    COALESCE(ao.has_rejected_appeal_action, 0) AS has_rejected_appeal_action,
    COALESCE(ao.has_accepted_appeal_action, 0) AS has_accepted_appeal_action,
    -- Status flags
    COALESCE(ao.has_ongoing_appeal, 0) AS has_ongoing_appeal,
    COALESCE(ao.has_appeal_assigned, 0) AS has_appeal_assigned,
    -- Derived flag: ongoing but not assigned
    CASE
        WHEN COALESCE(ao.has_ongoing_appeal, 0) = 1
         AND COALESCE(ao.has_appeal_assigned, 0) = 0
        THEN 1
        ELSE 0
    END AS has_unallocated_appeal
FROM all_cases_with_appeals c
LEFT JOIN appeals_by_party abp ON c.case_id = abp.case_id
LEFT JOIN appeal_outcomes ao ON c.case_id = ao.case_id
