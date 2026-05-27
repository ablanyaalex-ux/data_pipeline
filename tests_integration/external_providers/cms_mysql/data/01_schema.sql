-- CMS MySQL Schema for Integration Testing
-- Auto-generated from test fixtures
-- Tables are created in the database specified by MYSQL_DATABASE env var

-- appeals table schema
-- Appeals table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `appeals` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `new_evidence` tinyint(1) DEFAULT NULL,
  `user_id` bigint NOT NULL,
  `complaint_id` bigint NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `text` mediumtext COLLATE utf8mb3_unicode_ci,
  `rejected` tinyint(1) DEFAULT '0',
  `rejection_reason` text COLLATE utf8mb3_unicode_ci,
  `reason` varchar(16) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `why_evidence_was_unavailable` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `why_evidence_makes_a_difference` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `account_of_events` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `factual_error` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `why_factual_error_makes_a_difference` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  PRIMARY KEY (`id`),
  KEY `index_appeals_on_user_id` (`user_id`),
  KEY `index_appeals_on_complaint_id` (`complaint_id`)
) ENGINE=InnoDB AUTO_INCREMENT=302 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- channels table schema
-- Channels table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `channels` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  `symbol` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_channels_on_symbol` (`symbol`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- companies table schema
-- Companies table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `companies` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `active` tinyint(1) DEFAULT '0',
  `business` tinyint(1) NOT NULL DEFAULT '0',
  `symbol` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `parent_id` bigint DEFAULT NULL,
  `reporting_name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `business_validation` tinyint(1) DEFAULT '1',
  `active_types` tinyint(1) DEFAULT '1',
  `term_seconds` int DEFAULT '4838400',
  `in_administration` tinyint(1) NOT NULL DEFAULT '0',
  `charging_arrangement` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `is_account_number_required` tinyint(1) NOT NULL DEFAULT '0',
  `proposal_facility` tinyint(1) DEFAULT '1',
  `tom_pilot_participant` tinyint(1) NOT NULL DEFAULT '0',
  `tom_pilot_start_at` datetime DEFAULT NULL,
  `company_type` int DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `heat_trust_member` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_companies_on_symbol` (`symbol`),
  KEY `index_companies_on_parent_id` (`parent_id`),
  KEY `index_companies_on_updated_at` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;
-- complaints table schema
-- Complaints table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `complaints` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `status` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  `company_id` bigint DEFAULT NULL,
  `sector_id` bigint DEFAULT NULL,
  `company_response_id` bigint DEFAULT NULL,
  `response_at` datetime DEFAULT NULL,
  `first_complained_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `details` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `issue_id` bigint DEFAULT NULL,
  `remedies` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `user_datum_id` bigint DEFAULT NULL,
  `service_type_id` bigint DEFAULT NULL,
  `customer_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `consumer_id` bigint DEFAULT NULL,
  `status_changed_at` datetime DEFAULT NULL,
  `reference` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `decision_at` datetime DEFAULT NULL,
  `next_action_at` datetime DEFAULT NULL,
  `representative_datum_id` bigint DEFAULT NULL,
  `company_referral` tinyint(1) DEFAULT NULL,
  `prev_status` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `prev_next_action_at` datetime DEFAULT NULL,
  `channel_id` int DEFAULT NULL,
  `existing_customer` tinyint(1) DEFAULT NULL,
  `sensitive_data_consent` tinyint(1) DEFAULT NULL,
  `usage` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `va_user_present` tinyint(1) DEFAULT NULL,
  `spii_user_present` tinyint(1) DEFAULT NULL,
  `business` tinyint(1) DEFAULT NULL,
  `tor_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `status_details` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT 'Unknown',
  `correspondence_datum_id` bigint DEFAULT NULL,
  `prev_company_id` bigint DEFAULT NULL,
  `processing_next_action` tinyint(1) DEFAULT '0',
  `scd_consent` tinyint(1) DEFAULT NULL,
  `supplier_complaint_reference` varchar(36) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `submission_source` varchar(24) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `submission_source_item_id` varchar(64) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `call_opt_out` tinyint(1) DEFAULT NULL,
  `referral_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_complaints_on_reference` (`reference`),
  KEY `index_complaints_on_company_id` (`company_id`),
  KEY `index_complaints_on_sector_id` (`sector_id`),
  KEY `index_complaints_on_company_response_id` (`company_response_id`),
  KEY `index_complaints_on_issue_id` (`issue_id`),
  KEY `index_complaints_on_user_datum_id` (`user_datum_id`),
  KEY `index_complaints_on_service_type_id` (`service_type_id`),
  KEY `index_complaints_on_consumer_id` (`consumer_id`),
  KEY `index_complaints_on_representative_datum_id` (`representative_datum_id`),
  KEY `index_complaints_on_next_action_at` (`next_action_at`),
  KEY `index_complaints_on_correspondence_datum_id` (`correspondence_datum_id`),
  KEY `index_complaints_on_updated_at` (`updated_at`),
  KEY `index_complaints_on_created_at` (`created_at`),
  KEY `index_complaints_on_supplier_complaint_reference` (`supplier_complaint_reference`),
  KEY `index_complaints_on_submission_source` (`submission_source`),
  KEY `index_complaints_on_submission_source_item_id` (`submission_source_item_id`),
  KEY `index_complaints_on_referral_type` (`referral_type`)
) ENGINE=InnoDB AUTO_INCREMENT=1462308 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

-- complaints_users table schema
-- Complaint_users table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `complaints_users` (
  `complaint_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  KEY `index_complaints_users_on_complaint_id` (`complaint_id`),
  KEY `index_complaints_users_on_user_id` (`user_id`),
  KEY `index_complaints_users_on_complaint_id_and_user_id` (`complaint_id`,`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- decision_issues table schema
-- Decision_issues table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `decision_issues` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `issue` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `outcome` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `body` mediumtext COLLATE utf8mb3_unicode_ci,
  `decision_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `index_decision_issues_on_decision_id` (`decision_id`)
) ENGINE=InnoDB AUTO_INCREMENT=565 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- decisions table schema
-- Decisions table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraint to attachments removed for test compatibility

CREATE TABLE `decisions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `body` mediumtext COLLATE utf8mb3_unicode_ci,
  `author_id` bigint DEFAULT NULL,
  `complaint_id` bigint NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `attachment_id` bigint DEFAULT NULL,
  `published` tinyint(1) DEFAULT NULL,
  `final` tinyint(1) NOT NULL DEFAULT '0',
  `outcome` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `service_type_id` bigint DEFAULT NULL,
  `final_challenge_type` varchar(28) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `published_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_decisions_on_attachment_id` (`attachment_id`),
  KEY `index_decisions_on_author_id` (`author_id`),
  KEY `index_decisions_on_complaint_id` (`complaint_id`),
  KEY `index_decisions_on_service_type_id` (`service_type_id`),
  KEY `index_decisions_on_published_at` (`published_at`)
) ENGINE=InnoDB AUTO_INCREMENT=623 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- histories table schema
-- Histories table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraints removed for test compatibility

CREATE TABLE `histories` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `event` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `details` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `user_id` bigint DEFAULT NULL,
  `complaint_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `additional_info` text COLLATE utf8mb3_unicode_ci,
  `history_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `index_histories_on_user_id` (`user_id`),
  KEY `index_histories_on_complaint_id` (`complaint_id`),
  KEY `index_histories_on_history_type` (`history_type`),
  KEY `index_histories_on_event` (`event`),
  KEY `index_histories_on_history_type_and_complaint_id_and_event` (`history_type`,`complaint_id`,`event`)
) ENGINE=InnoDB AUTO_INCREMENT=403720 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- roles table schema
-- Roles table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `roles` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  `symbol` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `role_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_roles_on_symbol` (`symbol`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- sectors table schema
-- Sectors table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `sectors` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `active` tinyint(1) DEFAULT '0',
  `symbol` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_sectors_on_symbol` (`symbol`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- service_types table schema
-- Service_types table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraints removed for test compatibility

CREATE TABLE `service_types` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `active` tinyint(1) DEFAULT '0',
  `sector_id` bigint DEFAULT NULL,
  `voluntary_jurisdiction` tinyint(1) NOT NULL DEFAULT '0',
  `category_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `index_service_types_on_sector_id` (`sector_id`),
  KEY `index_service_types_on_category_id` (`category_id`)
) ENGINE=InnoDB AUTO_INCREMENT=47 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- user_data table schema
-- User_data table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `user_data` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `first_name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `last_name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `business_name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `account_number` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `address_1` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `address_2` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `city` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `postcode` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `telephone_number` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `is_not_company_customer` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `already_complaint` tinyint(1) DEFAULT NULL,
  `alternative_phone_number` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `country` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `deceased` tinyint(1) DEFAULT NULL,
  `best_contact_method` varchar(32) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `best_time_to_call` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `referral_email` varchar(254) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `index_user_data_on_referral_email` (`referral_email`)
) ENGINE=InnoDB AUTO_INCREMENT=9734 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- users table schema
-- Users table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraints removed for test compatibility

CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `description` mediumtext COLLATE utf8mb3_unicode_ci,
  `first_name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `last_name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `email` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `password_hash` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `role_id` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `company_id` bigint DEFAULT NULL,
  `title` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `email_verified` tinyint(1) NOT NULL DEFAULT '0',
  `activated_at` datetime DEFAULT NULL,
  `last_logged_at` datetime DEFAULT NULL,
  `proxy` tinyint(1) DEFAULT '1',
  `disabled` tinyint(1) NOT NULL DEFAULT '0',
  `telephone_number` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `disabled_get_next` tinyint(1) DEFAULT '0',
  `disabled_get_next_appeals` tinyint(1) NOT NULL DEFAULT '1',
  `managing_agent` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_users_on_email_unique` (`email`),
  KEY `index_users_on_company_id` (`company_id`),
  KEY `index_users_on_role_id` (`role_id`),
  KEY `index_users_on_company_id_and_role_id` (`company_id`,`role_id`),
  KEY `index_users_on_disabled_get_next_appeals` (`disabled_get_next_appeals`),
  KEY `index_users_on_name` (`name`),
  KEY `index_users_on_managing_agent` (`managing_agent`)
) ENGINE=InnoDB AUTO_INCREMENT=2810 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- issues table schema
-- issues table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `issues` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `active` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- additional_info table schema
-- additional_info table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraints removed for test compatibility (company_sites, company_responses, complaints)

CREATE TABLE `additional_info` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `hear_from` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `communication_needs` tinyint(1) DEFAULT NULL,
  `survey` tinyint(1) NOT NULL DEFAULT '0',
  `communication` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `anything_else` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `complaint_id` bigint NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `has_smart_meter` tinyint(1) DEFAULT NULL,
  `consumers_company_response_id` bigint DEFAULT NULL,
  `consumers_response_at` date DEFAULT NULL,
  `consumers_first_complained_at` date DEFAULT NULL,
  `companys_company_response_id` bigint DEFAULT NULL,
  `companys_response_at` date DEFAULT NULL,
  `companys_referral_notification_at` date DEFAULT NULL,
  `referral_evidence_included` tinyint(1) NOT NULL DEFAULT '0',
  `accurately_recorded` tinyint(1) NOT NULL DEFAULT '0',
  `communications_limit` tinyint(1) DEFAULT NULL,
  `energy_limit` tinyint(1) DEFAULT NULL,
  `turnover_limit` tinyint(1) DEFAULT NULL,
  `sf_evidence_step_state` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `challenge_resolution_reason` text COLLATE utf8mb3_unicode_ci,
  `government_support_scheme_id` int DEFAULT NULL,
  `hear_from_other_text` varchar(800) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `site_issue_id` bigint DEFAULT NULL,
  `supplier_business_categorisation` varchar(16) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `number_of_employees` int DEFAULT NULL,
  `balance_or_turnover` int DEFAULT NULL,
  `balance_turnover_value` int DEFAULT NULL,
  `electricity_usage` int DEFAULT NULL,
  `gas_usage` int DEFAULT NULL,
  `eligibility_date` date DEFAULT NULL,
  `review_eligibility_period_seconds` int DEFAULT NULL,
  `company_sites_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `index_additional_info_on_complaint_id` (`complaint_id`),
  KEY `index_additional_info_on_consumers_company_response_id` (`consumers_company_response_id`),
  KEY `index_additional_info_on_companys_company_response_id` (`companys_company_response_id`),
  KEY `index_additional_info_on_government_support_scheme_id` (`government_support_scheme_id`),
  KEY `index_additional_info_on_eligibility_date` (`eligibility_date`),
  KEY `index_additional_info_on_company_sites_id` (`company_sites_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1056681 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- decision_remedies table schema
-- decision_remedies table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraint removed for test compatibility (decisions)

CREATE TABLE `decision_remedies` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `remedy` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `description` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `decision_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `value` decimal(15,2) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `index_decision_remedies_on_decision_id` (`decision_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1693593 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- comments table schema
-- comments table schema from CMS MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `comments` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `text` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `published` tinyint(1) DEFAULT '0',
  `base_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `base_id` bigint DEFAULT NULL,
  `author_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `proposed` tinyint(1) DEFAULT '0',
  `author_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `disputed` tinyint(1) DEFAULT '0',
  `parent_id` int DEFAULT NULL,
  `comment_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `accepted` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `index_comments_on_base_type_and_base_id` (`base_type`,`base_id`),
  KEY `index_comments_on_author_id` (`author_id`),
  KEY `index_comments_on_base_id` (`base_id`)
) ENGINE=InnoDB AUTO_INCREMENT=9988533 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- comments_reasons table schema
-- comments_reasons table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraint removed for test compatibility (comments)

CREATE TABLE `comments_reasons` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `reason_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `text` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `comment_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `index_comments_reasons_on_comment_id` (`comment_id`)
) ENGINE=InnoDB AUTO_INCREMENT=394034 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;


-- comments_remedies table schema
-- comments_remedies table schema from CMS MySQL database
-- This is the official schema that cannot be changed
-- Note: FK constraint removed for test compatibility (comments)

CREATE TABLE `comments_remedies` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `remedy_type` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `text` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `comment_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `value` decimal(15,2) DEFAULT NULL,
  `implemented_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `index_comments_remedies_on_comment_id` (`comment_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1544153 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;
