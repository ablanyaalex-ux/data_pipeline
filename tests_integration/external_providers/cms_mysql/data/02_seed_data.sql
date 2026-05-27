-- CMS MySQL Test Data for Integration Testing
-- Auto-generated from test fixtures

SET NAMES utf8mb4;

USE cms_prod;

-- appeals data
INSERT INTO `appeals` (`id`, `new_evidence`, `user_id`, `complaint_id`, `created_at`, `updated_at`, `text`, `rejected`, `rejection_reason`, `reason`, `why_evidence_was_unavailable`, `why_evidence_makes_a_difference`, `account_of_events`, `factual_error`, `why_factual_error_makes_a_difference`)
VALUES
  (1, 1, 1, 1001, '2023-02-01T10:00:00', '2023-02-01T10:00:00', 'I have new evidence to support my case', 0, NULL, 'new-evidence', 'Was not available at time of original complaint', 'This changes the outcome', NULL, NULL, NULL),
  (2, 0, 2, 1001, '2023-02-02T14:00:00', '2023-02-02T14:00:00', 'Company disagrees with decision', 0, NULL, 'factual-errors', NULL, NULL, NULL, 'The dates in the decision are incorrect', 'Correct dates show we responded in time'),
  (3, 0, 10, 1002, '2023-03-15T09:30:00', '2023-03-15T09:30:00', 'OS staff appeal on behalf of consumer', 0, NULL, 'new-evidence', NULL, NULL, 'Consumer provided additional documentation', NULL, NULL),
  (4, 0, 1, 1003, '2023-04-10T11:00:00', '2023-04-10T11:00:00', 'Appeal rejected - not valid', 1, 'Appeal does not meet criteria', 'not-listed', NULL, NULL, NULL, NULL, NULL)
;

-- channels data
INSERT INTO `channels` (`id`, `name`, `symbol`)
VALUES
  (1, 'Web Form', 'web'),
  (2, 'Telephone', 'phone'),
  (3, 'Email', 'email'),
  (4, 'Letter', 'letter'),
  (5, 'In Person', 'in_person'),
  (6, 'Social Media', 'social_media')
;

-- companies data
INSERT INTO `companies` (`id`, `name`, `active`, `business`, `symbol`, `parent_id`, `reporting_name`, `business_validation`, `active_types`, `term_seconds`, `in_administration`, `charging_arrangement`, `is_account_number_required`, `proposal_facility`, `tom_pilot_participant`, `tom_pilot_start_at`, `company_type`, `created_at`, `updated_at`, `heat_trust_member`)
VALUES
  (1, 'Energy Corp UK', 1, 1, 'ECU', NULL, 'Energy Corp', 1, 1, 86400, 0, 'standard', 1, 0, 0, NULL, 1, '2024-01-15T10:00:00', '2024-01-20T14:22:33', 0),
  (2, 'Water Services Ltd', 1, 0, 'WSL', NULL, 'Water Services', 1, 1, 43200, 0, 'tiered', 1, 1, 1, '2024-03-01T00:00:00', 2, '2024-02-01T09:30:00', '2024-06-15T11:45:00', 1),
  (3, NULL, 1, 1, 'ECW', 1, 'Energy Corp Wales Division', 0, 0, NULL, 0, NULL, 0, 0, 0, NULL, 1, '2024-02-20T08:00:00', '2024-02-28T16:30:00', 0),
  (4, 'Defunct Power Co', 0, 1, 'DPC', NULL, 'Defunct Power', 0, 0, 0, 1, 'legacy', 0, 0, 0, NULL, 3, '2020-01-01T00:00:00', '2023-12-31T23:59:59', 0)
;

-- complaints data
INSERT INTO `complaints` (`id`, `status`, `company_id`, `sector_id`, `company_response_id`, `response_at`, `first_complained_at`, `created_at`, `updated_at`, `details`, `issue_id`, `remedies`, `user_datum_id`, `service_type_id`, `customer_type`, `consumer_id`, `status_changed_at`, `reference`, `decision_at`, `next_action_at`, `representative_datum_id`, `company_referral`, `prev_status`, `prev_next_action_at`, `channel_id`, `business`, `existing_customer`, `sensitive_data_consent`, `usage`, `va_user_present`, `spii_user_present`, `tor_type`, `status_details`, `correspondence_datum_id`, `prev_company_id`, `processing_next_action`, `scd_consent`, `supplier_complaint_reference`, `submission_source`, `submission_source_item_id`, `call_opt_out`, `referral_type`)
VALUES
  (1001, 'investigation', 10, 1, NULL, NULL, '2024-01-15 09:30:00', '2024-01-20 10:00:00', '2024-02-01 14:30:00', 'Customer received incorrect billing for 3 months', 5, NULL, 101, 2, 'domestic', 201, '2024-02-01 14:30:00', 'REF-2024-001001', NULL, '2024-02-15 10:00:00', NULL, 0, 'new_complaint', '2024-01-25 10:00:00', 1, 0, 1, 1, 'standard', 0, 0, NULL, 'Under investigation', NULL, NULL, 0, 1, NULL, 'web', NULL, 0, NULL),
  (1002, 'closed_resolved', 10, 1, 50, '2024-01-18 11:00:00', '2024-01-10 08:00:00', '2024-01-12 09:00:00', '2024-01-25 16:00:00', 'Service outage not communicated to customer', 3, 'Apology and credit applied', 102, 2, 'domestic', 202, '2024-01-25 16:00:00', 'REF-2024-001002', '2024-01-25 15:00:00', NULL, NULL, 0, 'investigation', '2024-01-20 10:00:00', 2, 0, 1, 1, 'standard', 0, 0, NULL, 'Resolved with apology', 301, NULL, 0, 1, 'SUP-REF-123', 'phone', 'CALL-456', 0, NULL),
  (1003, 'new_complaint', 11, 2, NULL, NULL, '2024-02-01 10:00:00', '2024-02-01 10:30:00', '2024-02-01 10:30:00', 'Product arrived damaged', 7, NULL, 103, 3, 'business', 203, '2024-02-01 10:30:00', 'REF-2024-001003', NULL, '2024-02-08 10:00:00', 401, 1, NULL, NULL, 3, 1, 0, 1, 'commercial', 0, 0, 'standard', 'Awaiting company response', NULL, NULL, 0, 0, NULL, 'email', 'EMAIL-789', 1, 'direct'),
  (1004, 'decision_made', 12, 1, 51, '2024-01-20 14:00:00', '2024-01-05 11:00:00', '2024-01-08 09:00:00', '2024-02-05 17:00:00', 'Contract terms unclear, customer overcharged', 5, 'Partial refund of £150', 104, 2, 'domestic', 204, '2024-02-05 17:00:00', 'REF-2024-001004', '2024-02-05 16:00:00', NULL, NULL, 0, 'investigation', '2024-02-01 10:00:00', 1, 0, 1, 1, 'standard', 1, 0, NULL, 'Decision issued', 302, NULL, 0, 1, NULL, 'web', NULL, 0, NULL),
  (1005, 'closed_withdrawn', 10, 1, NULL, NULL, '2024-01-22 15:00:00', '2024-01-23 09:00:00', '2024-01-30 11:00:00', 'Customer withdrew complaint', 2, NULL, 105, 1, 'domestic', 205, '2024-01-30 11:00:00', 'REF-2024-001005', NULL, NULL, NULL, 0, 'new_complaint', '2024-01-28 10:00:00', 2, 0, 1, 0, 'standard', 0, 1, NULL, 'Withdrawn by consumer', NULL, NULL, 0, NULL, NULL, 'phone', NULL, 0, NULL),
  (1006, 'investigation', 13, 3, 52, '2024-02-02 09:00:00', '2024-01-28 10:00:00', '2024-01-29 11:00:00', '2024-02-06 10:00:00', 'Delay in processing insurance claim', 8, NULL, 106, 4, 'domestic', 206, '2024-02-03 14:00:00', 'REF-2024-001006', NULL, '2024-02-10 10:00:00', 402, 0, 'new_complaint', '2024-02-05 10:00:00', 1, 0, 1, 1, 'standard', 0, 0, 'expedited', 'Awaiting documentation', 303, 14, 1, 1, 'INS-2024-001', 'web', 'FORM-101', 0, 'transfer')
;

-- complaints_users data
INSERT INTO `complaints_users` (`complaint_id`, `user_id`)
VALUES
  (1001, 1),
  (1001, 2),
  (1002, 2),
  (1002, 3),
  (1003, 4),
  (1004, 1),
  (1004, 5),
  (1005, 2)
;

-- decision_issues data
INSERT INTO `decision_issues` (`id`, `issue`, `outcome`, `body`, `decision_id`, `created_at`, `updated_at`)
VALUES
  (1, 'Billing Dispute', 'upheld', 'Customer was overcharged for 3 months. Company failed to apply correct tariff.', 1, '2024-01-20 10:00:00', '2024-01-20 10:00:00'),
  (2, 'Service Quality', 'not_upheld', 'Service levels were within acceptable parameters.', 1, '2024-01-20 10:05:00', '2024-01-20 10:05:00'),
  (3, 'Contract Terms', 'upheld', 'Contract terms were unclear and misleading.', 2, '2024-01-22 14:00:00', '2024-01-22 14:00:00'),
  (4, 'Customer Service', 'partially_upheld', 'Customer service response time was delayed but resolution was appropriate.', 3, '2024-01-25 09:00:00', '2024-01-25 11:30:00'),
  (5, 'Switching Issues', 'upheld', 'Switch was not processed within the guaranteed timeframe.', 4, '2024-02-01 15:00:00', '2024-02-01 15:00:00'),
  (6, 'Meter Reading', 'not_upheld', 'Meter readings were accurately recorded.', 4, '2024-02-01 15:30:00', '2024-02-01 15:30:00')
;

-- decisions data
INSERT INTO `decisions` (`id`, `body`, `author_id`, `complaint_id`, `created_at`, `updated_at`, `attachment_id`, `published`, `final`, `outcome`, `service_type_id`, `final_challenge_type`, `published_at`)
VALUES
  (1, 'Decision body for complaint 1001', 10, 1001, '2023-01-15T10:00:00', '2023-01-15T10:00:00', NULL, 1, 0, 'upheld', 1, NULL, '2023-01-15T10:00:00'),
  (2, 'Decision body for complaint 1002', 11, 1002, '2023-02-20T14:30:00', '2023-02-20T14:30:00', 100, 1, 0, 'not upheld', 2, NULL, '2023-02-20T14:30:00'),
  (3, 'Final decision for complaint 1001 after appeal', 12, 1001, '2023-03-10T09:00:00', '2023-03-10T09:00:00', NULL, 1, 1, 'upheld', 1, 'new-evidence', '2023-03-10T09:00:00'),
  (4, 'Draft decision - not published', 10, 1003, '2023-04-01T11:00:00', '2023-04-01T11:00:00', NULL, 0, 0, NULL, 1, NULL, NULL),
  (5, 'Decision with XXX outcome (excluded)', 10, 1004, '2023-05-01T10:00:00', '2023-05-01T10:00:00', NULL, 1, 0, 'XXX', 1, NULL, '2023-05-01T10:00:00'),
  (6, 'Duplicate decision for complaint 1002 (earlier - should be inactive)', 11, 1002, '2023-02-19T10:00:00', '2023-02-19T10:00:00', NULL, 1, 0, 'upheld', 2, NULL, '2023-02-19T10:00:00')
;

-- histories data
INSERT INTO `histories` (`id`, `event`, `details`, `user_id`, `complaint_id`, `created_at`, `updated_at`, `additional_info`, `history_type`)
VALUES
  (1, 'Status Changed [investigate]', 'new to investigate', 10, 1001, '2023-01-10T10:00:00', '2023-01-10T10:00:00', NULL, 'status_change'),
  (2, 'Status Changed [decision_issued]', 'investigate to decision_issued', 10, 1001, '2023-01-15T10:00:00', '2023-01-15T10:00:00', NULL, 'status_change'),
  (3, 'Status Changed [pending_appeal]', 'decision_issued to Pending Appeal', 1, 1001, '2023-02-01T10:00:00', '2023-02-01T10:00:00', NULL, 'status_change'),
  (4, 'Status Changed [under_appeal]', 'Pending Appeal to under_appeal', 10, 1001, '2023-02-05T09:00:00', '2023-02-05T09:00:00', NULL, 'status_change'),
  (5, 'Publish Decision', 'Decision published', 10, 1001, '2023-01-15T10:30:00', '2023-01-15T10:30:00', NULL, 'action'),
  (6, 'Status Changed [investigate]', 'new to investigate', 11, 1002, '2023-02-15T14:00:00', '2023-02-15T14:00:00', NULL, 'status_change'),
  (7, 'Status Changed [decision_issued]', 'investigate to decision_issued', 11, 1002, '2023-02-20T14:30:00', '2023-02-20T14:30:00', NULL, 'status_change'),
  (8, 'DRE one assigned', 'Case assigned to DRE', 12, 1001, '2023-02-10T08:00:00', '2023-02-10T08:00:00', NULL, 'assignment')
;

-- roles data
INSERT INTO `roles` (`id`, `name`, `symbol`, `description`, `role_type`)
VALUES
  (1, 'Administrator', 'admin', 'System administrator with full access', 'system'),
  (2, 'Case Handler', 'case_handler', 'Handles complaint cases', 'operational'),
  (3, 'Senior Case Handler', 'senior_case_handler', 'Senior staff for complex cases', 'operational'),
  (4, 'Team Leader', 'team_leader', 'Manages a team of case handlers', 'management'),
  (5, 'Ombudsman', 'ombudsman', 'Final decision maker', 'decision'),
  (6, 'Consumer', 'consumer', 'Customer making a complaint', 'external'),
  (7, 'Company Representative', 'company_rep', 'Represents the company in complaints', 'external'),
  (8, 'Quality Assurance', 'qa', 'Reviews case quality', 'operational')
;

-- sectors data
INSERT INTO `sectors` (`id`, `name`, `active`, `symbol`)
VALUES
  (1, 'Energy', 1, 'energy'),
  (2, 'Telecoms', 1, 'telecoms'),
  (3, 'Financial Services', 1, 'financial_services'),
  (4, 'Water', 1, 'water'),
  (5, 'Retail', 0, 'retail'),
  (6, 'Transport', 1, 'transport')
;

-- service_types data
INSERT INTO `service_types` (`id`, `name`, `active`, `sector_id`, `voluntary_jurisdiction`, `category_id`)
VALUES
  (1, 'Electricity Supply', 1, 1, 0, 1),
  (2, 'Gas Supply', 1, 1, 0, 1),
  (3, 'Dual Fuel', 1, 1, 0, 1),
  (4, 'Mobile Phone', 1, 2, 0, 2),
  (5, 'Broadband', 1, 2, 0, 2),
  (6, 'Landline', 1, 2, 0, 2),
  (7, 'Home Insurance', 1, 3, 1, 3),
  (8, 'Motor Insurance', 0, 3, 1, 3)
;

-- user_data data
INSERT INTO `user_data` (`id`, `title`, `first_name`, `last_name`, `business_name`, `account_number`, `address_1`, `address_2`, `city`, `postcode`, `telephone_number`, `is_not_company_customer`, `already_complaint`, `alternative_phone_number`, `country`, `deceased`, `best_contact_method`, `best_time_to_call`, `referral_email`)
VALUES
  (101, 'Mr', 'John', 'Smith', NULL, 'ACC-001234', '123 High Street', NULL, 'London', 'SW1A 1AA', '07700900001', NULL, 0, NULL, 'UK', 0, 'phone', 'afternoon', NULL),
  (102, 'Mrs', 'Jane', 'Doe', NULL, 'ACC-005678', '456 Oak Avenue', 'Flat 2B', 'Manchester', 'M1 1AA', '07700900002', NULL, 1, '01onal234567', 'UK', 0, 'email', NULL, 'jane.doe@email.com'),
  (103, NULL, NULL, NULL, 'Tech Solutions Ltd', 'BUS-009876', '1 Business Park', 'Unit 5', 'Birmingham', 'B1 1AA', '01onal345678', 'false', 0, NULL, 'UK', NULL, 'phone', 'morning', NULL),
  (104, 'Ms', 'Sarah', 'Wilson', NULL, 'ACC-002345', '789 Elm Road', NULL, 'Leeds', 'LS1 1AA', '07700900003', NULL, 1, '07700900004', 'UK', 0, 'phone', 'evening', NULL),
  (105, 'Dr', 'Michael', 'Brown', NULL, 'ACC-003456', '321 Pine Lane', NULL, 'Bristol', 'BS1 1AA', '07700900005', 'true', 0, NULL, 'UK', 0, 'email', NULL, 'm.brown@email.com'),
  (106, 'Mr', 'Robert', 'Taylor', NULL, 'ACC-004567', '654 Maple Close', NULL, 'Glasgow', 'G1 1AA', '07700900006', NULL, 0, NULL, 'UK', 1, NULL, NULL, NULL)
;

-- users data
INSERT INTO `users` (`id`, `name`, `description`, `first_name`, `last_name`, `email`, `password_hash`, `role_id`, `created_at`, `updated_at`, `company_id`, `title`, `email_verified`, `activated_at`, `last_logged_at`, `proxy`, `disabled`, `telephone_number`, `disabled_get_next`, `disabled_get_next_appeals`, `managing_agent`)
VALUES
  (1, 'consumer1', NULL, 'John', 'Smith', 'john.smith@email.com', 'xxx', 1, '2023-01-01T10:00:00', '2023-01-01T10:00:00', NULL, 'Mr', 1, '2023-01-01T10:00:00', '2024-01-15T09:00:00', 0, 0, '07700900001', 0, 1, 0),
  (2, 'company_user1', NULL, 'Jane', 'Doe', 'jane.doe@energycorp.com', 'xxx', 2, '2023-01-05T14:00:00', '2023-06-15T11:00:00', 1, 'Ms', 1, '2023-01-05T14:00:00', '2024-06-01T16:00:00', 0, 0, NULL, 0, 1, 0),
  (10, 'os_staff1', 'Senior case handler', 'Sarah', 'Johnson', 'sarah.johnson@ombudsman.org', 'xxx', 3, '2022-06-01T09:00:00', '2024-01-10T10:00:00', NULL, 'Mrs', 1, '2022-06-01T09:00:00', '2024-11-28T08:30:00', 1, 0, '02071234567', 0, 0, 0),
  (11, 'os_staff2', 'Case handler', 'Michael', 'Brown', 'michael.brown@ombudsman.org', 'xxx', 4, '2022-09-15T11:00:00', '2024-02-20T14:00:00', NULL, 'Mr', 1, '2022-09-15T11:00:00', '2024-11-27T17:00:00', 1, 0, NULL, 0, 0, 0),
  (12, 'os_staff3', 'Appeals specialist', 'Emily', 'Wilson', 'emily.wilson@ombudsman.org', 'xxx', 5, '2021-03-01T08:00:00', '2024-03-01T09:00:00', NULL, 'Ms', 1, '2021-03-01T08:00:00', '2024-11-28T09:15:00', 1, 0, '02071234568', 0, 0, 0),
  (100, 'disabled_user', NULL, 'Old', 'User', 'old.user@email.com', 'xxx', 1, '2020-01-01T10:00:00', '2022-12-31T23:59:59', NULL, NULL, 0, NULL, NULL, 0, 1, NULL, 1, 1, 0)
;

-- issues data
INSERT INTO `issues` (`id`, `name`, `active`)
VALUES
  (1, 'Billing query', 1),
  (2, 'Service interruption', 1),
  (3, 'Contract terms', 1),
  (4, 'Account closure', 0)
;

-- additional_info data
-- Note: complaint_id must exist in complaints; also references company_responses/company_sites (set to NULL here).
INSERT INTO `additional_info` (
  `id`, `hear_from`, `communication_needs`, `survey`, `communication`, `anything_else`,
  `complaint_id`, `created_at`, `updated_at`, `has_smart_meter`,
  `consumers_company_response_id`, `consumers_response_at`, `consumers_first_complained_at`,
  `companys_company_response_id`, `companys_response_at`, `companys_referral_notification_at`,
  `referral_evidence_included`, `accurately_recorded`, `communications_limit`, `energy_limit`,
  `turnover_limit`, `sf_evidence_step_state`, `challenge_resolution_reason`,
  `government_support_scheme_id`, `hear_from_other_text`, `site_issue_id`,
  `supplier_business_categorisation`, `number_of_employees`, `balance_or_turnover`,
  `balance_turnover_value`, `electricity_usage`, `gas_usage`, `eligibility_date`,
  `review_eligibility_period_seconds`, `company_sites_id`
)
VALUES
  (1, 'website', 0, 0, 'email', 'General notes redacted', 1001, '2024-01-20 10:05:00', '2024-02-01 14:35:00', 1,
   NULL, NULL, '2024-01-15', NULL, '0123-01-11', '0021-09-24', 0, 1, NULL, NULL,
   NULL, NULL, 'Reason redacted', NULL, NULL, NULL,
   'SME', 12, 1, 250000, 3200, 1800, '2024-01-01', 2592000, NULL),

  (2, 'phone', 1, 1, 'phone', 'Accessibility requirements redacted', 1002, '2024-01-12 09:05:00', '2024-01-25 16:05:00', 0,
   NULL, NULL, '2024-01-10', NULL, NULL, NULL, 1, 1, NULL, NULL,
   NULL, NULL, NULL, NULL, 'Other source redacted', NULL,
   'SME', 4, 0, NULL, 1200, 600, '2023-12-15', 2592000, NULL),

  (3, 'email', NULL, 0, 'letter', NULL, 1003, '2024-02-01 10:35:00', '2024-02-01 10:35:00', NULL,
   NULL, NULL, '2024-02-01', NULL, NULL, NULL, 0, 0, NULL, NULL,
   NULL, NULL, NULL, NULL, NULL, NULL,
   'MICRO', 2, 0, NULL, NULL, NULL, NULL, NULL, NULL),

  (4, 'web_form', 0, 1, 'email', 'Notes redacted', 1004, '2024-01-08 09:05:00', '2024-02-05 17:05:00', 1,
   NULL, NULL, '2024-01-05', NULL, NULL, NULL, 0, 1, NULL, NULL,
   NULL, NULL, 'Reason redacted', NULL, NULL, NULL,
   'SME', 25, 1, 1000000, 5400, 2200, '2023-12-01', 2592000, NULL)
;

-- decision_remedies data
-- Note: decision_id must exist in decisions (we use ids 1..4 from your seed).
INSERT INTO `decision_remedies` (`id`, `remedy`, `description`, `decision_id`, `created_at`, `updated_at`, `value`)
VALUES
  (1, 'credit', 'Redacted remedy description', 1, '2024-01-20 10:10:00', '2024-01-20 10:10:00', 50.00),
  (2, 'apology', 'Redacted remedy description', 1, '2024-01-20 10:11:00', '2024-01-20 10:11:00', NULL),
  (3, 'refund', 'Redacted remedy description', 2, '2024-01-22 14:10:00', '2024-01-22 14:10:00', 150.00),
  (4, 'service_action', 'Redacted remedy description', 3, '2024-01-25 09:10:00', '2024-01-25 09:10:00', NULL),
  (5, 'credit', 'Redacted remedy description', 4, '2024-02-01 15:40:00', '2024-02-01 15:40:00', 25.00)
;

-- comments data
-- Note: author_id should exist in users (we use ids 10/11/12/1/2 from your seed).
INSERT INTO `comments` (
  `id`, `text`, `published`, `base_type`, `base_id`, `author_id`, `created_at`, `updated_at`,
  `proposed`, `author_type`, `disputed`, `parent_id`, `comment_type`, `accepted`
)
VALUES
  (1, 'Comment text redacted', 1, 'Complaint', 1001, 10, '2024-02-01 15:00:00', '2024-02-01 15:00:00', 0, 'User', 0, NULL, 'internal_note', 1),
  (2, 'Comment text redacted', 1, 'Complaint', 1002, 11, '2024-01-25 16:10:00', '2024-01-25 16:10:00', 0, 'User', 0, NULL, 'internal_note', 1),
  (3, 'Comment text redacted', 0, 'Complaint', 1003, 12, '2024-02-01 11:00:00', '2024-02-01 11:00:00', 1, 'User', 0, NULL, 'draft', NULL),
  (4, 'Comment text redacted', 1, 'Decision', 1, 10, '2024-01-20 10:20:00', '2024-01-20 10:20:00', 0, 'User', 0, NULL, 'decision_note', 1),
  (5, 'Comment text redacted', 1, 'Complaint', 1004, 1, '2024-02-05 17:10:00', '2024-02-05 17:10:00', 0, 'User', 1, NULL, 'internal_note', 0)
;

-- comments_reasons data
INSERT INTO `comments_reasons` (`id`, `reason_type`, `text`, `comment_id`, `created_at`, `updated_at`)
VALUES
  (1, 'process', 'Reason text redacted', 1, '2024-02-01 15:05:00', '2024-02-01 15:05:00'),
  (2, 'evidence', 'Reason text redacted', 4, '2024-01-20 10:25:00', '2024-01-20 10:25:00'),
  (3, 'quality', 'Reason text redacted', 2, '2024-01-25 16:15:00', '2024-01-25 16:15:00')
;

-- comments_remedies data
INSERT INTO `comments_remedies` (
  `id`, `remedy_type`, `text`, `comment_id`, `created_at`, `updated_at`, `value`, `implemented_at`
)
VALUES
  (1, 'credit', 'Remedy note redacted', 4, '2024-01-20 10:26:00', '2024-01-20 10:26:00', 50.00, '2024-01-21 09:00:00'),
  (2, 'refund', 'Remedy note redacted', 4, '2024-01-22 14:11:00', '2024-01-22 14:11:00', 150.00, NULL),
  (3, 'apology', 'Remedy note redacted', 1, '2024-02-01 15:06:00', '2024-02-01 15:06:00', NULL, '2024-02-02 12:00:00'),
  (4, 'service_action', 'Remedy note redacted', 2, '2024-01-25 16:16:00', '2024-01-25 16:16:00', NULL, NULL)
;

