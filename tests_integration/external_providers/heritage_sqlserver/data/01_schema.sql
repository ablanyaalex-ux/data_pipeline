IF DB_ID('Static Dimensions') IS NULL
BEGIN
    CREATE DATABASE [Static Dimensions];
END;
GO
USE [Static Dimensions];
GO

IF SCHEMA_ID('dbo') IS NULL
BEGIN
    EXEC ('CREATE SCHEMA [dbo]');
END;
GO


IF OBJECT_ID('[dbo].[System_User_Mappings]', 'U') IS NOT NULL
BEGIN
    DROP TABLE [dbo].[System_User_Mappings];
END;
GO

CREATE TABLE [dbo].[System_User_Mappings](
	[Employee Id] [nvarchar](255) NULL,
	[Firstname] [nvarchar](255) NULL,
	[Surname] [nvarchar](255) NULL,
	[Full Name] [nvarchar](255) NULL,
	[Hierarchy Level 2] [nvarchar](255) NULL,
	[Hierarchy Level 3] [nvarchar](255) NULL,
	[Hierarchy Level 4] [nvarchar](255) NULL,
	[Reports To] [nvarchar](255) NULL,
	[Line Manager Id] [nvarchar](25) NULL,
	[Line Manager] [nvarchar](255) NULL,
	[Job Title] [nvarchar](255) NULL,
	[Puzzle Name] [nvarchar](255) NULL,
	[Puzzle ID] [int] NULL,
	[CMS Name] [nvarchar](255) NULL,
	[CMS ID] [int] NULL,
	[Peppermint Name] [nvarchar](255) NULL,
	[Peppermint ID] [nvarchar](255) NULL,
	[POPLA Name] [nvarchar](255) NULL,
	[POPLA ID] [nvarchar](255) NULL,
	[POPLA CMS Name] [nvarchar](255) NULL,
	[POPLA CMS ID] [nvarchar](255) NULL,
	[TOM_Role_1_ID] [int] NULL,
	[TOM_Role_2_ID] [int] NULL,
	[TOM_Role_3_ID] [int] NULL,
	[Line_Manager_Email] [nvarchar](255) NULL,
	[OM] [nvarchar](255) NULL,
	[Department] [nvarchar](50) NULL,
	[Leaver] [int] NULL,
	[DRE_CMS_ID] [int] NULL,
	[DRE_CMS_Name] [nvarchar](255) NULL,
	[DRE_CMS_DDI_Number] [nvarchar](255) NULL,
	[GlidePathStartDate] [date] NULL,
	[GlidePathGroupNumber] [int] NULL,
	[Contractual_Leave_Date] [date] NULL,
	[Place of Work] [nvarchar](255) NULL,
	[Office] [nvarchar](255) NULL,
	[windowsusername] [nvarchar](255) NULL,
	[DaviesResourcing_ID] [nvarchar](20) NULL,
	[EntraSSOEmail] [nvarchar](255) NULL,
	[DaviesResourcing_Line_Manager_ID] [nchar](20) NULL,
	[Coach_CMS_ID] [nvarchar](255) NULL,
	[Leader_CMS_ID] [nvarchar](255) NULL
) ON [PRIMARY]
GO
