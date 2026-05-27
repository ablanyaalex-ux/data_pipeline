IF DB_ID('ConnectCallData_26295') IS NULL
BEGIN
    CREATE DATABASE [ConnectCallData_26295];
END;

USE [ConnectCallData_26295];


IF SCHEMA_ID('dbo') IS NULL
BEGIN
    EXEC ('CREATE SCHEMA [dbo]');
END;



-- agents table schema
-- Source: Puzzel SQL Server database (ConnectCallData_26295)
-- Extracted from sys.columns via linked server

IF OBJECT_ID('[dbo].[agents]', 'U') IS NOT NULL
BEGIN
    DROP TABLE [dbo].[agents];
END;


CREATE TABLE [dbo].[agents](
	[agent_id] [int] NOT NULL,
	[customer_key] [varchar](50) NOT NULL,
	[user_name] [nvarchar](50) NULL,
	[user_num] [varchar](50) NULL,
	[full_name] [nvarchar](500) NULL,
	[usergroup_id] [int] NULL,
	[usergroup_name] [nvarchar](250) NULL,
	[email] [nvarchar](256) NOT NULL,
	[mobile] [nvarchar](256) NOT NULL,
	[dte_updated] [datetime] NULL,
	[chat_role] [tinyint] NULL,
	[chat_master_user_id] [int] NULL,
	[unblockable_role] [tinyint] NULL,
	[unblockable_group] [int] NULL,
	[deleted] [bit] NOT NULL,
	[puzzel_id] [varchar](255) NULL,
	CONSTRAINT [PK_agents] PRIMARY KEY ([agent_id])
) ON [PRIMARY]



-- call_events table schema
-- Source: Puzzel SQL Server database (ConnectCallData_26295)
-- Extracted from sys.columns via linked server

IF OBJECT_ID('[dbo].[call_events]', 'U') IS NOT NULL
BEGIN
    DROP TABLE [dbo].[call_events];
END;


CREATE TABLE [dbo].[call_events](
	[rec_id] [bigint] IDENTITY(1,1) NOT NULL,
	[customer_key] [varchar](100) NULL,
	[call_id] [numeric](19,0) NOT NULL,
	[call_sequence] [int] NULL,
	[media_type_id] [int] NULL,
	[dte_start] [datetime] NOT NULL,
	[duration_tot_sec] [int] NOT NULL,
	[duration_speak_sec] [int] NULL,
	[dte_speak_start] [datetime] NULL,
	[source] [varchar](500) NULL,
	[destination] [varchar](500) NULL,
	[additional_source] [varchar](500) NULL,
	[redirect_source] [varchar](500) NULL,
	[service_num] [varchar](100) NULL,
	[queue_key] [nvarchar](100) NULL,
	[menue_key] [nvarchar](100) NULL,
	[menue_choice] [varchar](255) NULL,
	[agent_id] [int] NULL,
	[event_type] [char](1) NOT NULL,
	[result_code] [char](2) NULL,
	[answered] [tinyint] NULL,
	[ciq] [char](1) NULL,
	[call_transfer] [bit] NULL,
	[wrap_up_sec] [int] NULL,
	[alert_ms] [int] NULL,
	[setup_ms] [int] NULL,
	[block_duration_sec] [int] NULL,
	[internal_iq_session_id] [uniqueidentifier] NULL,
	[internal_odr_id] [bigint] NULL,
	[dte_updated] [datetime] NULL,
	[sla] [int] NULL,
	[alt_sla] [int] NULL,
	[dte_scheduled_callback] [datetimeoffset](7) NULL,
	[result_response] [int] NULL,
	[request_id] [bigint] NULL,
	[hold] [int] NULL,
	[consult] [int] NULL,
	[leg_type] [varchar](50) NULL,
	[originating] [varchar](50) NULL,
	[add_originating] [varchar](50) NULL,
	[caller_on_hold_sec] [int] NULL,
	CONSTRAINT [PK_call_events] PRIMARY KEY ([rec_id])
) ON [PRIMARY]



-- queues table schema
-- Source: Puzzel SQL Server database (ConnectCallData_26295)
-- Extracted from sys.columns via linked server

IF OBJECT_ID('[dbo].[queues]', 'U') IS NOT NULL
BEGIN
    DROP TABLE [dbo].[queues];
END;


CREATE TABLE [dbo].[queues](
	[service_num] [varchar](100) NOT NULL,
	[queue_key] [nvarchar](100) NOT NULL,
	[descript] [nvarchar](255) NULL
) ON [PRIMARY]

