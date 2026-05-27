-- Initial Decision Deep Dive Report
-- Raw query using the existing stored procedure from Reporting database
-- This provides a case-level view of all initial decisions with party responses and timing metrics
--
-- Key Metrics:
-- - # Decisions: DISTINCTCOUNT of Case_ID where Initial_Decision_Date is not null
-- - Days to Decision: AVERAGE of DaysToInitialDecision
-- - Response times for both consumer and supplier
-- - Decision maker details (DRE, coach, leader, business unit)
--
-- Data Source: Reporting.dbo.CustomerJourney_InitialDecisionDeepDive stored procedure
-- Dependencies:
--   - CMS_Prod.Trn_OS.Decisions_And_Appeals_V2_Post05062022 (base decision and appeal data)
--   - CMS_Prod.Trn.* tables (Complaints, Companies, Sectors, Issues, Channels, Users, etc.)
--   - CMS_Prod.Trn_OS.DatesTable (InvestigateDate for days to decision calculation)
--   - [Static Dimensions].dbo.System_User_Mappings (DRE organizational hierarchy)

SELECT 
    Case_ID,
    Supplier,
    Consumer_Service_Type,
    Decision_Service_Type,
    Complaint_Type,
    Sector,
    Channel,
    ConsumerActivatedAccount,
    Initial_Decision_Date,
    Initial_Decision_time,
    Initial_Decision_Month,
    Initial_Decision_Outcome,
    Initial_Decision_Consumer_Response,
    Initial_Decision_Consumer_Response_Date,
    Initial_Decision_Supplier_Response,
    Initial_Decision_Supplier_Response_Date,
    TimeForConsumerToRespond,
    TimeForSupplierToRespond,
    MaxTimeForBothPartiesToRespond,
    OutstandingTimeForConsumerToRespond,
    OutstandingTimeForSupplierToRespond,
    InvestigateDate,
    DaysToInitialDecision,
    Decision_Completed_By,
    Decision_Coach,
    Decision_Leader,
    Decision_Business_Unit,
    Decision_Role,
    InitialDecisionWC,
    usage_type
FROM Reporting.dbo.CustomerJourney_InitialDecisionDeepDive;
