-- Decisions Report - Simplified using gold transformations
select
    dc.case_id,
    -- Case details
    comp_case.reference as case_reference,
    dc.created_date as case_created_date,
    comp.name as supplier,
    st_consumer.name as consumer_service_type,
    st_decision.name as decision_service_type,
    sec.name as sector,
    ch.name as channel,
    CASE WHEN u_consumer.activated_at = '1900-01-01' THEN 'No' ELSE 'Yes' END as consumer_activated_account,
    comp_case.usage as usage_type,

    -- Initial decision details
    CAST(fd.created_date AS DATE) as initial_decision_date,
    DATE_FORMAT(fd.created_date, 'HH:mm:ss') as initial_decision_time,
    dm.decision_month as initial_decision_month,
    fd.outcome as initial_decision_outcome,

    -- Consumer response
    CASE
        WHEN fdr.consumer_response_action IS NULL AND fdr.system_response_action = 'complete decision by system' THEN 'No Response'
        WHEN fdr.consumer_response_action IS NOT NULL THEN fdr.consumer_response_action
        ELSE NULL
    END as initial_decision_consumer_response,
    COALESCE(
        CAST(fdr.consumer_response_date AS DATE),
        CAST(fdr.system_response_date AS DATE)
    ) as initial_decision_consumer_response_date,

    -- Supplier response
    fdr.supplier_response_action as initial_decision_supplier_response,
    CAST(fdr.supplier_response_date AS DATE) as initial_decision_supplier_response_date,

    -- Response timing metrics
    DATEDIFF(DAY, fd.created_date, fdr.consumer_response_date) as time_for_consumer_to_respond,
    DATEDIFF(DAY, fd.created_date, fdr.supplier_response_date) as time_for_supplier_to_respond,
    CASE
        WHEN DATEDIFF(DAY, fd.created_date, fdr.consumer_response_date) >= DATEDIFF(DAY, fd.created_date, fdr.supplier_response_date)
        THEN DATEDIFF(DAY, fd.created_date, fdr.consumer_response_date)
        ELSE DATEDIFF(DAY, fd.created_date, fdr.supplier_response_date)
    END as max_time_for_both_parties_to_respond,
    CASE
        WHEN fdr.consumer_response_date IS NULL THEN DATEDIFF(DAY, fd.created_date, CURRENT_DATE())
        ELSE NULL
    END as outstanding_time_for_consumer_to_respond,
    CASE
        WHEN fdr.supplier_response_date IS NULL THEN DATEDIFF(DAY, fd.created_date, CURRENT_DATE())
        ELSE NULL
    END as outstanding_time_for_supplier_to_respond,

    -- Investigation date and days to decision
    CAST(fckd.first_investigate_date AS DATE) as investigate_date,
    DATEDIFF(DAY, fckd.first_investigate_date, fd.created_date) as days_to_initial_decision,

    -- Decision maker details (from system_user_mappings)
    CASE
        WHEN um_direct.cms_id IS NULL THEN um_dre.full_name
        ELSE um_direct.full_name
    END as decision_completed_by,
    CASE
        WHEN um_direct.cms_id IS NULL THEN um_dre.line_manager
        ELSE um_direct.line_manager
    END as decision_coach,
    CASE
        WHEN um_direct.cms_id IS NULL THEN um_dre.om
        ELSE um_direct.om
    END as decision_leader,
    CASE
        WHEN um_direct.cms_id IS NULL THEN um_dre.hierarchy_level_2
        ELSE um_direct.hierarchy_level_2
    END as decision_business_unit,
    CASE
        WHEN um_direct.cms_id IS NULL THEN um_dre.job_title
        ELSE um_direct.job_title
    END as decision_role,

    -- Week commencing date
    dd_decision.week_start_date as initial_decision_wc

from gold.dim_cases dc
-- Join to fact tables for decision context
inner join gold.fact_case_initial_decisions fcid
    on fcid.case_id = dc.case_id
inner join gold.fact_decisions fd
    on fd.decision_id = fcid.initial_decision_id
left join gold.fact_case_key_dates fckd
    on fckd.case_id = dc.case_id
left join gold.fact_decision_responses fdr
    on fdr.case_id = dc.case_id
-- Case details
left join bronze.cms_complaints comp_case
    on comp_case.id = dc.case_id
left join silver.cms_companies comp
    on comp_case.company_id = comp.id
left join silver.cms_sectors sec
    on comp_case.sector_id = sec.id
left join silver.cms_service_types st_consumer
    on comp_case.service_type_id = st_consumer.id
left join silver.cms_service_types st_decision
    on fd.service_type_id = st_decision.id
left join silver.cms_channels ch
    on comp_case.channel_id = ch.id
left join bronze.cms_users u_consumer
    on comp_case.consumer_id = u_consumer.id
-- Join to dim_dates for decision date attributes (month, week commencing)
left join gold.dim_dates dd_decision
    on dd_decision.calendar_date = CAST(fd.created_date AS DATE)
-- Decision maker mappings (try direct CMS ID first, then DRE_CMS_ID)
left join silver.heritage_system_user_mappings um_direct
    on um_direct.cms_id = fd.user_id
left join silver.heritage_system_user_mappings um_dre
    on um_dre.dre_cms_id = fd.user_id
where fd.created_date is not null
;
