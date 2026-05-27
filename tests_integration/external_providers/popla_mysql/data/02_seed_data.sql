INSERT INTO `case_audit`
(`case_verification_code`, `actioned_by`, `timestamp`, `description`, `event_type`, `draft_case_id`)
VALUES
('ABC1234567', 'system', '2025-01-10 09:15:30.123', 'Case created', 'CREATE', NULL),
('ABC1234567', 'assessor01', '2025-01-11 14:42:10.456', 'Status updated to IN_REVIEW', 'STATUS_CHANGE', '550e8400-e29b-41d4-a716-446655440000');

INSERT INTO `appellant_case`
(`verification_code`, `correlation_id`, `pcn`, `vehicle_registration`, `submitted_on_behalf`,
 `operator_code`, `submission_date`, `case_condition`, `status`, `assessor_id`,
 `decision`, `decision_date`, `withdrawn_by`, `withdrawal_reasons`, `withdrawal_date`,
 `custom_field_1`, `custom_field_2`, `primary_contact`, `secondary_contact`,
 `summary_operator`, `summary_appellant`, `summary_reasons`,
 `case_source`, `state_change_date`, `version`,
 `operator_evidence_excluded`, `status_reason`, `withdrawal_reason_code`)
VALUES
('ABC1234567', '111e8400-e29b-41d4-a716-446655440001', 'PCN001', 'AB12CDE', 0,
 'OP1', '2025-01-10 08:30:00', 'VALID', 'NEW', NULL,
 NULL, NULL, NULL, NULL, NULL,
 NULL, NULL, 1001, NULL,
 NULL, NULL, NULL,
 'ONLINE', '2025-01-10 08:30:00', 0,
 0, NULL, NULL),
('XYZ9876543', '222e8400-e29b-41d4-a716-446655440002', 'PCN002', 'XY99ZZZ', 1,
 'OP2', '2025-01-12 10:15:00', 'VALID', 'CLOSED', 12,
 'REFUSED', '2025-01-15 16:45:00', NULL, NULL, NULL,
 'Urgent', 'Handled quickly', 1002, 1003,
 'Operator summary text', 'Appellant summary text', 'Reason summary',
 'ONLINE', '2025-01-15 16:45:00', 1,
 0, 'FINAL', NULL);

INSERT INTO `user`
(`email`, `password`, `user_type`, `roles`, `name`,
 `login_attempts`, `account_locked`, `disabled`,
 `reset_requested_at`, `reset_token`, `role_id`)
VALUES
('john.doe@example.com', 'hashed_password_1', 'INTERNAL', 'ADMIN', 'John Doe',
 0, 0, 0,
 NULL, NULL, 1),
('jane.smith@example.com', 'hashed_password_2', 'OPERATOR', 'USER', 'Jane Smith',
 1, 0, 0,
 '2025-01-14 12:00:00.000', '333e8400-e29b-41d4-a716-446655440003', 2);

INSERT INTO `operator`
(`country`,`email`,`name`,`operator_code`,`phone`,`portal_account_status`,`primary_contact_id`,`url`)
VALUES
('GB','contact@operator1.com','Operator One','OP1','+44 1234 567890','ACTIVE',1001,'https://operator1.example.com'),
('GB','support@operator2.com','Operator Two','OP2','+44 9876 543210','SUSPENDED',1002,'https://operator2.example.com')
