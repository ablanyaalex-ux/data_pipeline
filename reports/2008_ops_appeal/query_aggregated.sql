select
    -- count(case_id) as case_count,
    -- sum(has_decision) case_with_decision_count,
    -- sum(has_appeal) case_with_appeal_count,
    -- sum(has_pending_appeal_status) case_with_pending_appeal_status_count,
    -- sum(has_appeal * has_pending_appeal_status) case_with_appeal_and_pending_appeal_status_count,
    -- sum(has_decision_dre) case_with_decision_dre_count,
    sum(has_decision_dre_manager) decisions, -- case_with_decision_dre_manager_count,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status) appeals, --  case_with_decision_and_appeal_and_status_dre_manager_count,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_consumer_appeal) consumer_appeal, --  case_with_decision_and_appeal_and_status_dre_manager_count_and_consumer_appeal,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_company_appeal) customer_appeal, --  case_with_decision_and_appeal_and_status_dre_manager_count_and_company_appeal,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_company_appeal * has_consumer_appeal) both_appeal, --  case_with_decision_and_appeal_and_status_dre_manager_count_and_double_appeal,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_rejected_appeal_status) rejected_status, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_rejected_appeal_status,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_accepted_appeal_status) accepted_status, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_accepted_appeal_status,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_rejected_appeal_action) rejected_action, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_rejected_appeal_action,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_accepted_appeal_action) accepted_action, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_accepted_appeal_action,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * (CASE WHEN has_rejected_appeal_status = 1 OR has_rejected_appeal_action = 1 THEN 1 ELSE 0 END)) rejected, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_rejected_appeal,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_accepted_appeal_action) accepted, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_accepted_appeal
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_ongoing_appeal) appeal_ongoing, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_ongoing_appeal,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_appeal_assigned) appeal_assigned, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_assigned_appeal,
    sum(has_decision_dre_manager * has_appeal * has_pending_appeal_status * has_unallocated_appeal) unallocated_appeal, -- case_with_decision_and_appeal_and_status_dre_manager_count_and_unallocated_appeal,
    sum(has_decision_dre_manager * has_attempted_appeal) attempted_appeal -- case_with_decision_dre_manager_count_and_attempted_appeal
from results
;
