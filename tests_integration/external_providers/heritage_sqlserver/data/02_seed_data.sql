USE [Static Dimensions];
GO

INSERT INTO [dbo].[System_User_Mappings] (
    [Employee Id], [Firstname], [Surname], [Full Name],
    [Hierarchy Level 2], [Hierarchy Level 3], [Hierarchy Level 4],
    [Reports To], [Line Manager Id], [Line Manager],
    [Job Title], [Puzzle Name], [Puzzle ID],
    [CMS Name], [CMS ID],
    [Peppermint Name], [Peppermint ID],
    [POPLA Name], [POPLA ID],
    [POPLA CMS Name], [POPLA CMS ID],
    [TOM_Role_1_ID], [TOM_Role_2_ID], [TOM_Role_3_ID],
    [Line_Manager_Email], [OM], [Department], [Leaver],
    [DRE_CMS_ID], [DRE_CMS_Name], [DRE_CMS_DDI_Number],
    [GlidePathStartDate],
    [Contractual_Leave_Date],
    [Place of Work], [Office], [windowsusername],
    [DaviesResourcing_ID], [EntraSSOEmail],
    [DaviesResourcing_Line_Manager_ID],
    [Coach_CMS_ID], [Leader_CMS_ID]
)
VALUES
(
    '011915', 'Employee', 'A', 'Employee A',
    'Org Unit A', 'Division A', 'Department A',
    NULL, '012129', 'Manager A',
    'Role A', 'Employee A', 458393,
    'Employee A', 312460,
    NULL, NULL,
    NULL, NULL,
    NULL, NULL,
    NULL, NULL, NULL,
    NULL, 'Supervisor A', 'Operations', 1,
    682986, 'Employee A', NULL,
    NULL,
    CAST('2024-09-30' AS date),
    'Location A', 'Office A', 'user.a',
    NULL, 'user.a@domain.org',
    NULL,
    NULL, NULL
),
(
    '011985', 'Employee', 'B', 'Employee B',
    'Org Unit B', 'Division B', 'Department B',
    NULL, '011796', 'Manager B',
    'Role B', 'Employee B', 485026,
    'Employee B', 380159,
    NULL, NULL,
    NULL, NULL,
    NULL, NULL,
    NULL, NULL, NULL,
    NULL, 'Supervisor B', 'Operations', 0,
    672774, 'Employee B', NULL,
    NULL,
    NULL,
    'Location B', 'Office B', 'user.b',
    NULL, 'user.b@domain.org',
    NULL,
    NULL, NULL
);
GO
