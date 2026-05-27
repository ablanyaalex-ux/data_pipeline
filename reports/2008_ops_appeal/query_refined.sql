with
case_ids_with_decisions as (
    select distinct case_id
    from gold.fact_decisions
),
case_ids_with_appeals as (
    select distinct case_id
    from gold.fact_appeals
),
case_ids_with_attempted_appeals as (
    select distinct case_id
    from gold.fact_appeals
    where reason = 'not-listed'
),
case_ids_with_pending_appeal_status as (
    select distinct case_id
    from gold.fact_case_key_dates
    where first_appeal_pending_date is not null
)
select
    dc.case_id,
    dc.created_date,
    um.dre_cms_id,
    um.line_manager as dre_coach,
    du.full_name as dre_name,
    comp.name as company_name,
    fckd.first_appeal_date as appeal_date,
    DATEDIFF(day, fckd.first_appeal_pending_date, fckd.first_appeal_assigned_date) as days_in_appeal,
    (case when ciwd.case_id is not null then 1 else 0 end) as has_decision,
    (case when ciwp.case_id is not null then 1 else 0 end) as has_appeal,
    (case when cwpas.case_id is not null then 1 else 0 end) as has_pending_appeal_status,
    (case when ciwd.case_id is not null and um.dre_cms_id is not null then 1 else 0 end) has_decision_dre,
    (case when ciwd.case_id is not null and um.dre_cms_id is not null and um.line_manager is not null then 1 else 0 end) has_decision_dre_manager,
    (case when ciwaa.case_id is not null then 1 else 0 end) as has_attempted_appeal,
    fao.has_consumer_appeal as has_raw_consumer_appeal,
    fao.has_company_appeal as has_company_appeal,
    fao.has_internal_appeal as has_internal_appeal,
    fao.has_consumer_or_internal_appeal as has_consumer_appeal,
    COALESCE(fao.has_rejected_appeal_status, 0) as has_rejected_appeal_status,
    COALESCE(fao.has_accepted_appeal_status, 0) as has_accepted_appeal_status,
    COALESCE(fao.has_rejected_appeal_action, 0) as has_rejected_appeal_action,
    COALESCE(fao.has_accepted_appeal_action, 0) as has_accepted_appeal_action,
    COALESCE(fao.has_ongoing_appeal, 0) as has_ongoing_appeal,
    COALESCE(fao.has_appeal_assigned, 0) as has_appeal_assigned,
    COALESCE(fao.has_unallocated_appeal, 0) as has_unallocated_appeal
from gold.dim_cases dc
left join gold.fact_case_initial_decisions fcid
    on fcid.case_id = dc.case_id
left join gold.fact_decisions fd
    on fcid.initial_decision_id = fd.decision_id
left join gold.dim_users du
    on fd.user_id = du.user_id
left join bronze.cms_complaints comp_case
    on comp_case.id = dc.case_id
left join bronze.cms_companies comp
    on comp_case.company_id = comp.id
left join gold.fact_case_key_dates fckd
    on fckd.case_id = dc.case_id
left join case_ids_with_appeals ciwp
    on ciwp.case_id = dc.case_id
left join case_ids_with_attempted_appeals ciwaa
    on ciwaa.case_id = dc.case_id
left join case_ids_with_pending_appeal_status cwpas
    on cwpas.case_id = dc.case_id
left join case_ids_with_decisions ciwd
    on ciwd.case_id = dc.case_id
left join silver.heritage_system_user_mappings um
    on um.dre_cms_id = fd.user_id
left join gold.fact_appeal_outcomes fao
    on fao.case_id = dc.case_id
-- order by dc.created_date desc
;
