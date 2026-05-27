select count(Appealed_By_Consumer = 'Yes')
from (
    with
        cte_caseStatusAgg
        as
        (
            select
                cs.case_ID,
                [Maintain Decision date]        = min(case when cs.Status_Action = 'Maintain Decision' then CAST(cs.CREATED_AT as date)end),
                [Maintain Decision WC]          = dateadd(week,datediff(week, 0,min(case when cs.Status_Action = 'Maintain Decision'then CAST(cs.CREATED_AT as date) end)), 0),
                [Maintain Decision MC]          = CAST(DATEADD(M,DATEDIFF(M,0,min(case when cs.Status_Action = 'Maintain Decision'then CAST(cs.CREATED_AT as date)end)),0) AS DATE),
                [Pending Appeal date]           = min(case when cs.Status_to     = 'pending appeal'                                     then CAST(cs.CREATED_AT as date)end),
                [Check Appeal Evidence date]    = min(case when cs.Status_to     = 'check appeal evidence'                              then CAST(cs.CREATED_AT as date)end),
                [Appeal Start date]             = min(case when cs.Status_to     IN ('under appeal','company appeal','joint appeal')    then CAST(cs.CREATED_AT as date)end),
                [Appealend date]                = min(case when cs.Status_from   IN ('under appeal','company appeal','joint appeal')  then CAST(cs.CREATED_AT as date)end)
            from CMS_Prod.[Trn_OS].[case_Status] cs
            where
                cs.Status_Action    =  'Maintain Decision'
                OR cs.Status_to     IN ('pending appeal','check appeal evidence','under appeal','company appeal','joint appeal')
                OR cs.Status_from   IN ('under appeal','company appeal','joint appeal')
            group by
                cs.case_ID
        ),

        cte_AppealsAgg
        as
        (
            --our base for appeal data
            select
                id           = a.appeals_id,
                complaint_id = a.complaint_id,
                user_id      = a.user_id,
                reason       = a.reason,
                role_id      = u.role_id
            from silver.appeals a
                left join silver.users u
                on a.user_id = u.users_id
        ),

        cte_UNALLOCATEDAPPEALS
        as
        (
            select distinct
                app.complaint_id
            from cte_AppealsAgg app
                inner join cms_prod.trn_os.case_status cst
                on  cst.case_id       = app.complaint_id
                    and cst.status_action = 'Appeal assigned'
        ),


        cte_pcevidence_latest_id
        as
        (
            select
                complaint_id,
                MaxAppealId = max(id)
            from cte_AppealsAgg
            where role_id = 2 and reason is not null
            group by
                complaint_id
        ),
        cte_PCEVIDDENCE
        as
        (
            ---Get PC Appeal reason--
            select
                complaint_id = App.complaint_id,
                reason       = App.reason
            from cte_AppealsAgg App
                inner join cte_pcevidence_latest_id PcEvLat
                on  PcEvLat.complaint_id = App.complaint_id
                    and PcEvLat.MaxAppealId  = App.id
        ),


        cte_cevidence_latest_id
        as
        (
            select
                complaint_id,
                MaxAppealId = max(id)
            from cte_AppealsAgg
            where role_id in (1, 3, 4, 5, 6) and reason is not null
            group by
                complaint_id
        ),
        cte_CEVIDDENCE
        as
        (
            ---Get C Appeal reason--
            select
                complaint_id = App.complaint_id,
                reason       = App.reason
            from cte_AppealsAgg App
                inner join cte_cevidence_latest_id CEv
                on  CEv.complaint_id = App.complaint_id
                    and CEv.MaxAppealId  = App.id
        ),

        cte_Histories
        as
        (
            select
                id,
                complaint_id,
                Created_At,
                user_id,
                event
            from CMS_Prod.Trn.Histories
            where
                event IN ('Status Changed [appeal_assigned]','DRE one assigned', 'DRE Two assigned')
        ),
        cte_assigned_ids
        as
        (
            select
                complaint_id,
                FirstAssignedId  = min(case when event in ('DRE one assigned', 'DRE Two assigned')  then id end),
                LatestAssignedId = max(case when event =  'Status Changed [appeal_assigned]'        then id end)
            from cte_histories
            group by
                complaint_id
        ),
        cte_first_assigned
        as
        (
            select
                His.id,
                His.complaint_id,
                His.created_at,
                His.user_id
            from cte_histories      His
                inner join cte_assigned_ids Ids
                on  Ids.complaint_id    = His.complaint_id
                    and Ids.FirstAssignedId = His.id
        ),

        cte_latest_assigned
        as
        (
            select
                His.id,
                His.complaint_id,
                His.created_at,
                His.user_id
            from cte_histories      His
                inner join cte_assigned_ids Ids
                on  Ids.complaint_id    = His.complaint_id
                    and Ids.LatestAssignedId = His.id
        ),

        cte_ASSIGNEDdate
        as
        (
            ---Assigned date
            select
                c.Reference,
                [Assigned date]         = LatAss.Created_At,
                [Assigned Agent Name]   = CONCAT(i.first_name, ' ', i.last_name)
            from cte_latest_assigned                LatAss
                left join CMS_Prod.Trn.Users            b ON LatAss.user_id = b.id
                left join CMS_Prod.Trn.complaints       c ON LatAss.complaint_id = c.id
                left join CMS_Prod.Trn.Complaints_Users h ON LatAss.Complaint_id = h.complaint_id
                left join CMS_Prod.Trn.Users            i ON h.user_id = i.id
                left join CMS_Prod.Trn.Roles            j ON i.role_id = j.id
            where
                --a.event IN ('Status Changed [appeal_assigned]')
                    b.role_id BETWEEN 9 AND 13
                AND i.role_id BETWEEN 9 AND 13

        ),

        cte_ASSIGNEDdateMIN
        as
        (
            ---Assigned date
            select
                c.Reference,
                'Assigned date'         = a.Created_At,
                'Assigned Agent Name'   = CONCAT(i.first_name, ' ', i.last_name)
            from cte_first_assigned a
                left join CMS_Prod.Trn.Users b ON a.user_id = b.id
                left join CMS_Prod.Trn.complaints c ON a.complaint_id = c.id
                left join CMS_Prod.Trn.Complaints_Users h ON a.Complaint_id = h.complaint_id
                left join CMS_Prod.Trn.Users i ON h.user_id = i.id
            where --a.event IN ('DRE one assigned', 'DRE Two assigned')
                    b.role_id BETWEEN 9 AND 13
                AND i.role_id BETWEEN 9 AND 13
        ),

        cte_ReportingMaster
        as
        (
            -- select
            --          case_ID
            --         ,Moved_To_Investigate_date
            -- from	Reporting.dbo.Reporting_Master
            -- where system = 'CMS'
            SELECT
                complaint_id
                , created_at as Moved_To_Investigate_date
            from silver.PocEventCaseStatusChange
            where Status_To = 'investigate'
                and event_chage_to_first_status_to_sequence = 1
        ),

        cte_decisions_base
        as
        (
            select
                case_id,
                case_reference,
                Initial_Decision_ID,
                initial_decision_date = cast(initial_decision_date as date),
                initial_decision_user_id,
                initial_decision_user_name,
                appeal_status_outcome,
                appeal_consumer_name,
                appeal_os_name,
                appeal_pc_name,
                appeal_date,
                appeal_processed_by,
                appeal_processed_by_id,
                final_decision_date,
                dre_appeal_response
            from cms_prod.trn_os.decisions_and_appeals_v2_post05062022
        ),

        cte_decisions_ranked
        as
        (
            select
                Deci.case_id,
                Deci.case_reference,
                Deci.Initial_Decision_ID,
                Deci.initial_decision_date,
                Deci.initial_decision_user_id,
                Deci.initial_decision_user_name,
                Deci.appeal_status_outcome,
                Deci.appeal_consumer_name,
                Deci.appeal_os_name,
                Deci.appeal_pc_name,
                Deci.appeal_date,
                Deci.appeal_processed_by,
                Deci.appeal_processed_by_id,
                Deci.final_decision_date,
                Deci.dre_appeal_response,
                -- earliest initial decision date per case (what you were doing with MIN)
                min_initial_decision_date = min(Deci.initial_decision_date) over (partition by Deci.case_id order by Deci.Initial_Decision_ID asc ),
                -- pick ONE "latest" row per case based on initial_decision_id
                rn = row_number() over (partition by Deci.case_id order by Deci.initial_decision_id desc)
            from cte_decisions_base Deci
        ),

        cte_decisions
        as
        (
            select
                case_id,
                case_reference,
                Initial_Decision_date      = min_initial_decision_date, -- earliest
                Initial_Decision_User_ID   = initial_decision_user_id,
                Initial_Decision_User_Name = initial_decision_user_name,
                Appeal_Status_Outcome      = appeal_status_outcome,
                Appeal_Consumer_Name       = appeal_consumer_name,
                Appeal_OS_Name             = appeal_os_name,
                Appeal_PC_Name             = appeal_pc_name,
                Appeal_date                = appeal_date,
                Appeal_Processed_By        = appeal_processed_by,
                Appeal_Processed_By_ID     = appeal_processed_by_id,
                Final_Decision_date        = final_decision_date,
                [Final Decision WC]        = CAST(DATEADD(dd, -(DATEPART(dw, Final_Decision_Date)-1), Final_Decision_Date) AS DATE),
                [Final Decision MC]        = CAST(DATEADD(M,DATEDIFF(M,0,Final_Decision_Date),0) AS DATE) ,
                DRE_Appeal_Response        = dre_appeal_response
            from cte_decisions_ranked
            where rn = 1
        )


    /*
    CMS_Prod.Trn_Os.Decisions_and_Appeals_V2 is an old tabel using old logic where created_at in trn.decision is <= '2022-06-05'

    */

    select
        [Case Reference]                = Deci.[case_Reference],
        [Case_ID]                       = Deci.[case_ID],
        [Decision date]                 = (Deci.[Initial_Decision_date]),
        Decision_Issued_MC              = CAST(dateADD(M,dateDIFF(M,0,(Deci.[Initial_Decision_date])),0) as date),
        [Decision WC]                   = CAST(dateADD(dd, -(datePART(dw, Deci.Initial_Decision_date)-1), Deci.Initial_Decision_date) as date),
        [Coach]                         = d.[Line Manager],
        Initial_Agent_Name              = Deci.[Initial_Decision_User_Name],
        Company_Name                    = m.name ,
        Parent_Company_Name             = m.Reporting_Name,
        Sector                          = c.name,
        [Decision User Name]            = Deci.[Initial_Decision_User_Name],
        [Leader]                        = d.OM,
        [Case Has an Appeal]            = case
                                                    when Deci.[Appeal_Status_Outcome] IN  ('Not Appealed', 'Appeal Attempted')
                                                    then 0
                                                    else 1
                                                end,
        [Case Has an Accepted Appeal]   = case
                                                    when Deci.[Appeal_Status_Outcome] = 'Appeal Upheld/Appeal Accepted'
                                                    then 1
                                                    else 0
                                                end ,
        [Case Has a Rejected Appeal]    = case
                                                    when Deci.[Appeal_Status_Outcome] = 'Appeal Not Upheld/Appeal Rejected'
                                                    then 1
                                                    else 0
                                                end,
        [Case Has an Attempted Appeal]  = case
                                                    when Deci.[Appeal_Status_Outcome] = 'Appeal Attempted'
                                                    then 1
                                                    else 0
                                            end,
        OTM                             = d.[Line Manager],
        Appealed_By_Consumer            = case
                                                    when Appeal_Consumer_Name IS NOT NULL
                                                    then 'Yes'
                                                    when Appeal_OS_Name IS NOT NULL
                                                    then 'Yes'
                                                    else 'No'
                                            end,
        Appealed_By_PC                  = case
                                                    when Appeal_PC_Name IS NOT NULL
                                                    then 'Yes'
                                                    else 'No'
                                            end,
        [Double Appeal]                  = case when
                                                        case  when Appeal_Consumer_Name IS NOT NULL
                                                            then 'Yes'
                                                            when Appeal_OS_Name IS NOT NULL
                                                            then 'Yes'
                                                            else 'No'
                                                    end = 'Yes'
            AND
            case when Appeal_PC_Name IS NOT NULL
                                                            then 'Yes'
                                                            else 'No'
                                                    end = 'Yes'
                                                THEN 'Yes' ELSE 'No' END,
        Investigate_Date                = RepMas.Moved_To_Investigate_date,
        Initial_Decision_Date           = Deci.Initial_Decision_date,
        [Final Decision Date]           = CASE WHEN Deci.Appeal_Status_Outcome ='Appeal Not Upheld/Appeal Rejected' THEN CasStaAgg.[Maintain Decision date] ELSE Deci.Final_Decision_date END,
        [Final Decision WC]             = CASE WHEN Deci.Appeal_Status_Outcome ='Appeal Not Upheld/Appeal Rejected' THEN CasStaAgg.[Maintain Decision WC]   ELSE Deci.[Final Decision WC] END,
        [Final Decision MC]             = CASE WHEN Deci.Appeal_Status_Outcome ='Appeal Not Upheld/Appeal Rejected' THEN CasStaAgg.[Maintain Decision MC]   ELSE Deci.[Final Decision MC] END,
        Appeal_Date                     = CAST(Deci.Appeal_date as date),
        [Time To Initial Decision]	    = DATEDIFF(DAY, RepMas.Moved_To_Investigate_date, Initial_Decision_Date),
        [Time To Final Decision]        = CASE  WHEN Deci.Appeal_Status_Outcome ='Appeal Not Upheld/Appeal Rejected'
                                                        THEN DATEDIFF(DAY, Deci.Appeal_date, [Maintain decision date])
                                                        ELSE DATEDIFF(DAY, Deci.Appeal_date, Deci.Final_Decision_date)
                                                END,
        Deci.Appeal_Processed_By,
        [Appeal Coach]                  = d1.[Line Manager],
        [Appeal Leader]                 = D1.OM ,
        Appeal_Status_Outcome,
        [Days in Appeal]                = dateDIFF(DAY, CasStaAgg.[Pending appeal date], AssDat.[Assigned date]),
        Days_With_DRE3                  = case
                                                        when Deci.Appeal_Status_Outcome = 'Appeal Not Upheld/Appeal Rejected'
                                                        then dateDIFF(DAY,AssDat.[Assigned date], CasStaAgg.[Maintain decision date])
                                                        when Deci.Appeal_Status_Outcome = 'Appeal Upheld/Appeal Accepted'
                                                        then  dateDIFF(DAY,AssDat.[Assigned date], Deci.Final_Decision_date)
                                                        when Deci.Appeal_Status_Outcome NOT IN ('Appeal Upheld/Appeal Accepted','Appeal Not Upheld/Appeal Rejected')
                                                        then  dateDIFF(D,AssDat.[Assigned date],GETdate())
                                                    end,
        Days_With_Original_DRE          = case
                                                        when Deci.Appeal_Status_Outcome = 'Appeal Not Upheld/Appeal Rejected'
                                                    then dateDIFF(DAY,AssDatMin.[Assigned date], CasStaAgg.[Maintain decision date])
                                                    when Appeal_Status_Outcome = 'Appeal Upheld/Appeal Accepted'
                                                    then  dateDIFF(DAY,AssDatMin.[Assigned date], Deci.Final_Decision_date)
                                                    when Appeal_Status_Outcome NOT IN ('Appeal Upheld/Appeal Accepted','Appeal Not Upheld/Appeal Rejected')
                                                    then  dateDIFF(D,AssDatMin.[Assigned date],GETdate())
                                                end,
        CasStaAgg.[Maintain decision date],
        [Maintain Decision WC]          = CasStaAgg.[Maintain Decision WC],
        [Maintain Decision MC]          = CasStaAgg.[Maintain Decision MC],
        [Consumer Appeal Reason]        = CEv.reason,
        [Supplier Appeal Reason]        = PcEv.reason,
        [DRE_Appeal_Response],
        [Is Appeal Allocated]       = case
                                                when Deci.Appeal_date IS NOT NULL AND Deci.Appeal_Status_Outcome = 'Appeal On Going' AND UnAllApp.complaint_id IS NULL
                                                then 'Not Allocated'
                                                when Deci.Appeal_date IS NOT NULL AND Deci.Appeal_Status_Outcome = 'Appeal On Going' AND UnAllApp.complaint_id IS NOT NULL
                                                then 'Allocated'
                                                when Deci.Appeal_date IS NULL
                                                then 'not appealed'
                                                else NULL
                                        end,
        CasStaAgg.[Pending appeal date],
        CasStaAgg.[appeal start date],
        [appeal end date]           = CasStaAgg.[appealend date],
        status,
        CasStaAgg.[check appeal evidence date],
        [Account Type]	            = case
                                                when b.usage_type LIKE '%business' then 'Business'
                                                when b.[usage_type]='residential' then 'Domestic'
                                                else b.usage_type
                                            end

    from cte_decisions                                          Deci
        left join CMS_Prod.Trn.Complaints                       b ON Deci.[case_ID]                    = b.id
        left join CMS_Prod.Trn.companies                        m ON b.company_id                      = m.id
        left join CMS_Prod.Trn.Sectors                          c ON b.sector_id                       = c.id
        left join [Static Dimensions].DBO.System_User_Mappings  d ON Deci.[Initial_Decision_User_ID]   = d.[DRE_CMS_ID]
        left join [Static Dimensions].DBO.System_User_Mappings  d1 ON Deci.Appeal_Processed_By_ID       = d1.DRE_CMS_ID
        left join cte_ReportingMaster                           RepMas ON Deci.case_id                      = RepMas.case_id
        left join cte_CEVIDDENCE                                CEv ON Deci.case_ID                      = CEv.complaint_id
        left join cte_PCEVIDDENCE                               PcEv ON Deci.case_ID                      = PcEv.complaint_id
        left join cte_ASSIGNEDdate                              AssDat ON Deci.case_Reference               = AssDat.reference
        left join cte_ASSIGNEDdateMIN                           AssDatMin ON Deci.case_Reference               = AssDatMin.reference
        left join cte_UNALLOCATEDAPPEALS                        UnAllApp ON Deci.case_ID                      = UnAllApp.complaint_id
        left join cte_caseStatusAgg                             CasStaAgg ON Deci.case_ID                      = CasStaAgg.case_ID

    where
                d.[Line Manager] IS NOT NULL
) as x

    --282,052 has some rows repeated for 3 cases
    --282,049 using latest appeal record per case as cms seem to display only the latest
    --and CASE WHEN Appeal_Status_Outcome ='Appeal Not Upheld/Appeal Rejected' THEN [Maintain decision date] ELSE Deci.Final_Decision_date END>= '2025-11-01'
    --order by Appeal_Processed_By
