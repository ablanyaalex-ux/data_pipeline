-- Puzzel SQL Server Test Data for Integration Testing

USE [ConnectCallData_26295];


-- Seed data: dbo.agents

INSERT INTO [dbo].[agents] (
    [agent_id],
    [customer_key],
    [user_name],
    [user_num],
    [full_name],
    [usergroup_id],
    [usergroup_name],
    [email],
    [mobile],
    [dte_updated],
    [chat_role],
    [chat_master_user_id],
    [unblockable_role],
    [unblockable_group],
    [deleted],
    [puzzel_id]
)
VALUES
(1001, '12345', 'AgentOne',   '10001', 'Test Agent One',   10, 'Ops Team A', 'agent.one@test.example',   '+447700900001', '2025-12-01 09:15:00', NULL, 501, 0, 0, 0, 'PUZ-1001'),
(1002, '23456', 'AgentTwo',   '10002', 'Test Agent Two',   10, 'Ops Team A', 'agent.two@test.example',   '+447700900002', '2025-12-02 10:30:00', 0, 502, 0, 0, 0, 'PUZ-1002'),
(1003, '34567', 'AgentThree', '10003', 'Test Agent Three', 20, 'Ops Team B', 'agent.three@test.example', '+447700900003', '2025-12-03 11:45:00', 1, 503, 1, 1, 0, 'PUZ-1003');


-- Seed data: dbo.queues

INSERT INTO [dbo].[queues] ([service_num], [queue_key], [descript])
VALUES
('1234567890', 'General_Inquiries', 'General Enquiries'),
('1234567890', 'Retention_Queue', 'Retention Queue'),
('9876543210', 'Callback_Queue', 'Callback Queue');


-- Seed data: dbo.call_events
-- Note: rec_id is IDENTITY; we use IDENTITY_INSERT so we can set rec_id values manually

SET IDENTITY_INSERT [dbo].[call_events] OFF;
SET IDENTITY_INSERT [dbo].[call_events] ON;

INSERT INTO [dbo].[call_events] (
    [rec_id],
    [customer_key],
    [call_id],
    [call_sequence],
    [media_type_id],
    [dte_start],
    [duration_tot_sec],
    [duration_speak_sec],
    [dte_speak_start],
    [source],
    [destination],
    [additional_source],
    [redirect_source],
    [service_num],
    [queue_key],
    [menue_key],
    [menue_choice],
    [agent_id],
    [event_type],
    [result_code],
    [answered],
    [ciq],
    [call_transfer],
    [wrap_up_sec],
    [alert_ms],
    [setup_ms],
    [block_duration_sec],
    [internal_iq_session_id],
    [internal_odr_id],
    [dte_updated],
    [sla],
    [alt_sla],
    [dte_scheduled_callback],
    [result_response],
    [request_id],
    [hold],
    [consult],
    [leg_type],
    [originating],
    [add_originating],
    [caller_on_hold_sec]
)
VALUES
(900000001,'12345',100000001,1,1,'2025-12-10 09:00:00',420,300,'2025-12-10 09:02:00',
 '07123456789','07234567890',NULL,NULL,'1234567890',
 'queue_key_01','menu2','095638',1001,'c','e',1,'a',0,35,1200,500,0,NULL,1234567890,'2025-12-10 09:10:00',20,25,NULL,0,700000001,0,0,'Agent','07564738287',NULL,0),
(900000002,'23456',100000002,1,1,'2025-12-11 10:15:00',180,120,'2025-12-11 10:16:00',
 '07111111111','07222222222',NULL,NULL,'1234567890',
 'comms_b2b_02','info_busy','133',1002,'i',NULL,1,'q',0,20,800,450,0,NULL,1234567891,'2025-12-11 10:20:00',30,30,'2025-12-11 11:00:00 +00:00',1,700000002,0,0,NULL,'07511112222',NULL,10),
(900000003,'34567',100000003,2,2,'2025-12-12 14:05:00',600,0,NULL,
 '07333333333','07444444444','07555555555','07666666666','9876543210',
 'new_business_25','message1_eg1','143245',1003,'m','s',0,NULL,1,0,1500,700,15,NULL,1234567892,'2025-12-12 14:15:00',45,60,'2025-12-12 15:00:00 +00:00',2,700000003,1,1,'Caller','07533334444',NULL,25);

SET IDENTITY_INSERT [dbo].[call_events] OFF;

