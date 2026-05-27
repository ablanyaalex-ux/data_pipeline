-- Fact: Case Status Transitions
-- Tracks all status changes for cases with FK references to dimensions

SELECT
    chcst.histories_id AS case_status_transition_id,
    chcst.complaint_id AS case_id,
    chcst.user_id,
    chcst.status_from,
    dcs_from.case_status_id AS status_from_id,
    chcst.status_to,
    dcs_to.case_status_id AS status_to_id,
    chcst.status_action,
    chcst.created_at AS transition_date,
    dd.date_id AS transition_date_id
FROM silver.cms_histories_case_status_transitions chcst
LEFT JOIN gold.dim_case_statuses dcs_from
    ON chcst.status_from = dcs_from.status_name
LEFT JOIN gold.dim_case_statuses dcs_to
    ON chcst.status_to = dcs_to.status_name
LEFT JOIN gold.dim_dates dd
    ON CAST(chcst.created_at AS DATE) = dd.calendar_date
