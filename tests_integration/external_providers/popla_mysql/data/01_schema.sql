
-- case_audit table schema
-- case_audit table schema from popla MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `case_audit` (
`id` bigint NOT NULL AUTO_INCREMENT,
`case_verification_code` char(10) DEFAULT NULL,
`actioned_by` varchar(255) NOT NULL,
`timestamp` datetime(3) NOT NULL,
`description` varchar(1000) NOT NULL,
`event_type` varchar(30) DEFAULT NULL,
`draft_case_id` char(36) DEFAULT NULL,
PRIMARY KEY (`id`),
KEY `idx_case_audit_verification_code` (`case_verification_code`)
) ENGINE=InnoDB AUTO_INCREMENT=5695491 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- appellant_case table schema
-- appellant_case table schema from popla MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `appellant_case` (
`case_id` int NOT NULL AUTO_INCREMENT,
`verification_code` char(10) DEFAULT NULL,
`correlation_id` char(36) DEFAULT NULL,
`pcn` varchar(255) DEFAULT NULL,
`vehicle_registration` varchar(10) DEFAULT NULL,
`submitted_on_behalf` tinyint(1) DEFAULT '0',
`operator_code` char(3) DEFAULT NULL,
`submission_date` datetime DEFAULT CURRENT_TIMESTAMP,
`case_condition` varchar(32) DEFAULT NULL,
`status` varchar(8) DEFAULT 'NEW',
`assessor_id` int DEFAULT NULL,
`decision` varchar(10) DEFAULT NULL,
`decision_date` datetime DEFAULT NULL,
`withdrawn_by` varchar(10) DEFAULT NULL,
`withdrawal_reasons` text,
`withdrawal_date` datetime DEFAULT NULL,
`custom_field_1` varchar(255) DEFAULT NULL,
`custom_field_2` varchar(255) DEFAULT NULL,
`primary_contact` int DEFAULT NULL,
`secondary_contact` int DEFAULT NULL,
`summary_operator` text,
`summary_appellant` text,
`summary_reasons` text,
`case_source` varchar(10) DEFAULT 'ONLINE',
`state_change_date` datetime DEFAULT CURRENT_TIMESTAMP,
`version` int DEFAULT '0',
`operator_evidence_excluded` tinyint(1) DEFAULT '0',
`status_reason` varchar(32) DEFAULT NULL,
`withdrawal_reason_code` varchar(50) DEFAULT NULL,
PRIMARY KEY (`case_id`),
UNIQUE KEY `verification_code` (`verification_code`),
KEY `idx_appellant_case_operator` (`operator_code`),
KEY `idx_appellant_case_assessor` (`assessor_id`),
KEY `idx_case_primary_contact` (`primary_contact`),
KEY `idx_case_secondary_contact` (`secondary_contact`),
KEY `idx_appellant_case_submission_date` (`submission_date`),
FULLTEXT KEY `idx_pcn` (`pcn`),
FULLTEXT KEY `idx_vehicle_registration` (`vehicle_registration`),
FULLTEXT KEY `idx_operator_code` (`operator_code`),
FULLTEXT KEY `idx_status` (`status`),
FULLTEXT KEY `idx_case_condition` (`case_condition`),
FULLTEXT KEY `idx_decision` (`decision`),
FULLTEXT KEY `idx_verification_code` (`verification_code`),
FULLTEXT KEY `idx_cases_all` (`pcn`,`vehicle_registration`,`operator_code`,`status`,`case_condition`,`decision`,`verification_code`)
) ENGINE=InnoDB AUTO_INCREMENT=399517 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- user table schema
-- user table schema from popla MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `user` (
`user_id` int NOT NULL AUTO_INCREMENT,
`email` varchar(100) NOT NULL,
`password` varchar(100) NOT NULL,
`user_type` varchar(10) NOT NULL,
`roles` varchar(255) DEFAULT NULL,
`name` varchar(70) DEFAULT NULL,
`login_attempts` int DEFAULT '0',
`account_locked` tinyint(1) DEFAULT '0',
`disabled` tinyint(1) DEFAULT '0',
`reset_requested_at` datetime(3) DEFAULT NULL,
`reset_token` varchar(36) DEFAULT NULL,
`role_id` int DEFAULT NULL,
PRIMARY KEY (`user_id`),
UNIQUE KEY `idx_user_email` (`email`),
UNIQUE KEY `idx_user_reset_token` (`reset_token`),
FULLTEXT KEY `idx_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=1668 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- operator table schema
-- operator table schema from popla MySQL database
-- This is the official schema that cannot be changed

CREATE TABLE `operator` (
`operator_code` char(3) NOT NULL,
`email` varchar(100) DEFAULT NULL,
`name` varchar(100) DEFAULT NULL,
`phone` varchar(50) DEFAULT NULL,
`portal_account_status` varchar(32) DEFAULT NULL,
`primary_contact_id` int DEFAULT NULL,
`url` varchar(100) DEFAULT NULL,
`country` char(5) DEFAULT NULL,
PRIMARY KEY (`operator_code`),
KEY `idx_operator_contact` (`primary_contact_id`),
FULLTEXT KEY `idx_operator_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
