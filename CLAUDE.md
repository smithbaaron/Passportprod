# Working Conventions — Passport Labs Production Org

This repo mirrors metadata built for the Passport Labs production Salesforce org
(passportlabs.my.salesforce.com, alias `prod`). Ground rules for any session
working here:

## Testing ground rules

- **Test-generated emails go to aaron.smith@passportinc.com ONLY**, never to
  real recipients (Cecily, CS reps, shared inboxes), unless Aaron explicitly
  says otherwise. Before a test that fires notification flows, deploy a
  temporary flow version with the recipient swapped to Aaron, test, then
  restore the real recipient version. Do not commit the temporary version —
  the repo keeps the permanent configuration.
- Prefer savepoint/rollback anonymous Apex for data-layer tests (nothing
  persists, emails are discarded). Use visible test records only when a human
  must click through UI (screen flows), and always name them
  `ZZ TEST ... (delete me)` for cleanup.
- Prod discipline: discuss before changing; build → test → verify → clean up
  test records; revert anything temporary. One closing opportunity per Apex
  transaction (the netsuite_conn package hits its own SOQL limit otherwise).

## Org facts that bite

- Active flows cannot be deployed directly: deploy as `<status>Draft</status>`,
  then activate via Tooling PATCH on FlowDefinition
  (`{"Metadata":{"activeVersionNumber":N}}`). Revert = same call with the old
  number. The repo files carry `Active` to reflect intended state.
- `Account.Churn_Explanation` (validation rule) requires a churn explanation only
  when an account is created as, or changed to, Former (narrowed 2026-09-18;
  formula has `OR(ISNEW(), ISCHANGED(Status__c))`). Before that it fired on every
  save of a Former account with a blank explanation, which froze 524 legacy Former
  accounts (489 with no churn date): reps could not create, advance or close opps on
  them (Account roll-ups re-save the parent), at-risk journeys could not be opened
  or closed, and the monthly NetSuite revenue refresh (Celigo, runs as user "Passport
  Operations") had not written any of them since the rule was created on 2025-05-08.
  After the fix the September refresh wrote 377 of them on 2026-09-18 with UNCHANGED
  revenue values, so `Recurring_NS__c` > 0 on a Former account (Ann Arbor $205,899
  despite an Aug 2024 churn) is what NetSuite posted in the prior 12 complete months,
  not a Salesforce freeze: a NetSuite-side question (still billing, or a mis-mapped
  customer). The 147 not written are presumably not NetSuite customers. Those 524
  accounts still have no explanation; a backfill for the 35 dated churns (2023-2025)
  is a separate decision.
- Account at-risk fields are a projection of the At-Risk Journey child records
  (kept true by the At_Risk_Account_Mirror_Sync flow). Fix the journey, never
  hand-edit the account mirror.
- Long-text fields can't be filtered in SOQL/reports; Tooling API JSON nulls
  collection-typed flow action inputs (Metadata XML is ground truth); report
  Metadata deploys strip blank-value filters (use the Analytics REST API PATCH:
  `PATCH /services/data/v64.0/analytics/reports/<id>` with `reportMetadata.reportFilters`
  + `reportBooleanFilter`; a filter `{"column":..,"operator":"equals","value":""}` is
  "is blank"). Report numeric filters do NOT treat blank as 0 (`lessThan 1` skips
  blanks), and SOQL `!= 0` DOES match nulls. Revenue Reconciliation reports
  `Current_Accounts_With_Zero_NS_Revenue` and `Stale_Actual_Revenue_Sum` carry an
  API-added "NS Revenue equals blank" filter that a redeploy from this repo would drop.
- Custom permission `Bypass_At_Risk_Validation` (perm set "At-Risk Validation
  Bypass") skips the at-risk guards; `Bypass_CapStrat_Validation` does the same
  for CapStrat rules. Both are assigned to no one by default.
- Account `At_Risk_Client__c` ("At-Risk Client (RETIRED FIELD)") is retired
  per Aaron (Sep 2026): never read or write it. The live flag is the
  `Is_At_Risk__c` formula (open-journey count > 0). The mirror sync maintains
  only spectrum + date fields (v3+). Blocked Former accounts keep a stale
  checkmark until churn explanations unlock them.
- Administratively-closed churn cases carry
  `Derisked_Resolution__c = 'Client churned - closed administratively'` (with
  `Derisked_Client_Action__c = 'Client Churned'`). This is the filter key to
  exclude the one-time zombie cleanup from any closed-case reporting. The Sep
  2026 pass closed 210 such cases on Former accounts.
- Both at-risk validation rules now honor `Bypass_At_Risk_Validation`:
  `Account.Churn_Explanation` and `At_Risk_Journey__c.Only_Latest_Journey_Can_Be_Open`.
  Assign perm set "At-Risk Validation Bypass" for admin bulk ops, then unassign.
- Bulk-closing at-risk cases requires pausing the legacy `De_Risk_Final` flow
  (FLOW label "FLOW: Email Alert De-Risked", 300R700000SsLU3IAN) first: it
  fires the 10-recipient de-risk email on every close AND writes the account
  (which fails on blocked Former accounts). Restore it after.
- Report folder sharing is LEGACY mode (enhanced folder sharing off; Salesforce has
  removed the Setup toggle; `FolderShare` sObject unsupported). The Reports &
  Dashboards REST API still works for sharing:
  `POST /services/data/v64.0/folders/<id>/shares` with
  `{"shares":[{"accessType":"view","shareType":"organization","shareWithId":"00GG0000003PxGUMA0"}]}`
  (request field is `shareWithId`; the GET response spells it `sharedWithId`).
  Remove with `sf api request rest .../shares/<shareId> --method DELETE --body '{}'`
  (the CLI errors on DELETE without a body). Metadata `folderShares`/`accessType`
  deploys are no-ops on existing folders.
- `Folder.AccessType` does NOT reflect effective sharing (never updates for share
  rows). Read effective access from the REST shares endpoint or the Metadata API
  `folderShares` block (ground truth). `UserRecordAccess` on Folder measures
  object-record read, not analytics-folder visibility - useless for this.
- Report SUBFOLDERS inherit the parent's sharing and reject direct sharing writes
  (errorCode 250 "not allowed on a subfolder"): share the top-level parent. So any
  sensitive folder nested under a public parent is silently open to everyone.
  Sep 2026: Annual Planning, Bookings vs Budget (+RevOrg KPI Reports), Commissions,
  CRO KPI Reports and Due Diligence live under the PublicInternal Revenue Ops
  Reports and are open to all internal users until moved out. FP&A (x2) sit under
  AE Reporting, so AE Reporting must stay restricted until FP&A is moved.
- "All Internal Users" is the system group `00GG0000003PxGUMA0` (DeveloperName
  AllInternalUsers, Type Organization, Name null): auto-maintained, membership
  cannot be edited (INSUFFICIENT_ACCESS_ON_CROSS_REFERENCE_ENTITY). Sep 2026 folder
  open: 37 top-level report folders shared View to it; 61 already inherited.
  Kept restricted: Commissions, Due Diligence, Diligence Reports, Corp Dev Reports,
  Legal Department, Snapshot Reports - Admin Only, FP&A (x2), Bookings vs Budget,
  Annual Planning, CRO KPI Reports.
- NetSuite revenue fields on Account (`NS_Revenue__c`, `Recurring_NS__c`, `One_Time_NS__c`,
  `Parking/Payments/Enforcement/Permit/Transit/Hardware_Other_NS__c`), per Kyle Whittlesey
  (Financial Systems, Aug 2026): summed by NetSuite Class (= product family) per Customer,
  one Customer maps 1:1 to one Account, NO multi-customer roll-ups (parent totals are a
  Salesforce Rollup Helper construct); ALL calculate on a rolling prior 12 COMPLETE months;
  accrual basis (an invoice's revenue posts in its month whether or not paid, so overdue
  balances never reduce it); refreshed by a MONTHLY MANUAL Celigo run, not live (the
  "Passport Operations" user logs in daily but the revenue write lands once a month; Sep
  2026 run = 9/17-9/18). Revenue below opportunity expectations is usually usage-based fees
  vs. estimated opps, not a data error. Product-level (opportunity-product) NetSuite
  revenue is not available from the integration (Celigo support question).
- Lost revenue on churned accounts = `Churn_Recurring_Revenue__c`: the active Workflow
  Rule "Churned Account -- Recurring Rev Capture" copies `Recurring_NS__c` into it when
  `Status__c` changes to Former (a point-in-time snapshot). `Actual_Revenue_Sum__c`
  (Account) is live annualized NetSuite revenue and decays after churn;
  `At_Risk_Journey__c.Actual_Revenue_Sum_atrisk__c` is only a formula mirror of it
  (`Account__r.Actual_Revenue_Sum__c`), not a stored value. The snapshot is blank when
  Recurring NS had already zeroed before the Status flip (bulk/administrative churns):
  27 such churns 2024-2026 as of Sep 2026, plus 213 legacy Former accounts with no
  `Churn_Date__c` at all.
- Report folders cannot be re-parented programmatically: the Reports REST
  `PATCH /folders/<id>` rejects `parentId` (errorCode 102 "Folder parent cannot be
  part of a patch request body") and Folder DML is blocked. Moving a folder is
  UI-only (Reports tab -> folder -> Move). Sharing IS scriptable, and subfolders
  inherit the parent, so the pattern is: set the parent's shares by API, move the
  children in the UI.
- Opportunity Closed Won is gated by several active rules besides the stage gates:
  Ironclad Workflow attached (`Ensure_Ironclad_Workflow_IsPresent`, every Type except
  Renewal / Upsell / Revenue Enhancement), `Why_Passport__c` filled (`Require_Why_Passport`),
  at least one product line (`Stop_close_won_opp_missing_opp_product`), Account billing
  city/state, and Close Date. Salesforce returns every failing rule's message in one save,
  so a savepoint/rollback `Database.update(o, false)` probe lists all blockers for a deal.
- `Stage_Gate_Contract` (Sep 2026) requires `Client_Success_Rep__c` only on
  "New Business - Cross-Sell": net-new deals get their CS rep after close, and the Google
  Drive Deal Folder link is no longer gated. `Stage_Gate_Discovery`, `Stage_Gate_RFP`,
  `Pre_Close_Audit_Check` and `Google_Drive_in_Sales_Team_Section` are inactive in the org.
  The org carries 45 Opportunity validation rules; this repo holds 10 (retrieve
  `CustomObject:Opportunity` for ground truth). `Next_Step_must_be_current` ("Update Next Step
  before changing stages.") fires on every non-Renewal record type, Technology/Services Partner
  deals included; since 2026-09-24 it exempts the `CUSTOM - SF Admin` profile (Rachel Kleman's,
  8 active users incl. Sam Warnecke, Solvd and Zapier) and any profile or role containing
  "Marketing" (`CUSTOM - Marketing User`, role `Marketing`) via `$Profile.Name` / `$UserRole.Name`.
  Older rules exempt admins by `$Profile.Id` (`00e0f00000107LD` = CUSTOM - SF Admin). Rollback
  probe: scratchpad vr_nextstep_probe.apex (runs as Aaron, who is NOT exempt: System
  Administrator / role SF Admin).
- Account roll-up summaries over Opportunity (`Open_Opp_Count__c`, `Closed_Won_Opportunities__c`,
  `Won_Opp_Count__c`, `Amount_Sum__c`, `Total_spaces_sold__c`, `Customer_Acquisition_Date__c`,
  `Implementation_Complete_Opportunities__c`) re-save the Account whenever an opp enters or
  leaves a counted stage, so the Account `Churn_Explanation` rule surfaces on Opportunity saves
  as "Please enter churn explanation" (fields=Churn_Explanation__c) whenever that rule matches;
  any Account validation rule can surface on an Opportunity save this way. The
  `Open_Opp_Count__c` filter carries a stale value "Scoping/Proposal" (no such stage), so
  Proposal, Scoping, SE Technical Review and Internal Review are not counted today; fixing
  it is a separate decision. `Churn_Explanation__c` is on the Client Details section of
  Account Layout and CUSTOM - Sales User has edit on it.
- Opportunity History report type (`OpportunityHistory`; `<scope>` must be `all`): summing an
  Opportunity-level checkbox (Won, Closed) counts each opportunity ONCE per grouping (parent-object
  aggregates de-duplicate), while Record Count and the history-row Amount count every stage entry
  (re-entries included). Per-deal funnel counts are therefore `CLOSED:SUM` and win rate is
  `WON:SUM / CLOSED:SUM`, never `/ RowCount`. Creation rows carry a blank From Stage with Stage
  Change = true. The retired stage "Scoping/Proposal" is still the busiest mid-funnel stage in T12
  history (128 of 379 closed new-business deals), so stage filters should be "not equal to the closed
  stages", not a list of current stages. Sales Velocity Reports `Win_Rate_by_Stage_Reached`,
  `Losses_by_Last_Stage` and `Avg_Sales_Cycle_RFP_vs_Non_RFP` (Sep 2026) follow the org's
  win-rate convention of excluding Lost Reason `Inactive` / `Pipeline Cleanup` (159 of the 379 T12
  closes, none won). The older "RFP vs Non-RFP Win Rate" filters the stale value `RFP - No Bid`
  (real picklist value: `No Bid RFP`). Marcia's "Stage to Won Conversion" / "Stage Conversion
  Report" divide by RowCount and are grouped by From Stage; leave them as they are.
- Report metadata gaps: the Lightning "Row Count" toggle is `hasRecordCount` in the Analytics API
  only (`PATCH /services/data/v64.0/analytics/reports/<id>` body
  `{"reportMetadata":{"hasRecordCount":false}}`); a metadata redeploy resets it to true, so re-PATCH
  the two funnel reports above after any redeploy. Chart deploys reject `legendPosition` and
  `backgroundColor1/2` and cap the chart `title` at 40 characters. `sf project retrieve start
  --output-dir` must point inside the project.
- RFP deals are flagged by `Opportunity.RFP__c` (help text "Is this deal going to RFP?"; matches
  passing through the RFP stage for 69 of 71 T12 closes). `Procurement_Method__c`, `RFP_Required__c`
  and `RFP_Submitted_Date__c` are effectively unused. Sales-cycle fields: `Sales_Duration_Days__c` =
  CloseDate - DATEVALUE(CreatedDate) (same as standard Age once closed); `Sales_Cycle_Months__c` is
  rounded to whole months, so average the days and divide by 30.44 instead.
- Asset contract fields: `Contract_Start_Date__c` and `Contract_End_Date__c` are entered by hand
  (99% filled; assets are created manually, nothing writes them), `Contract_Term_Months__c` is a
  formula between the two, `Contract_Term_Type__c` is Standard / Auto-Renewal / Evergreen. The end
  date is never advanced after an auto-renewal (Sep 2026: 1,254 active Auto-Renewal/Evergreen assets
  had a past end date), so `Renewal_Date__c` (formula, Sep 2026) rolls it forward: Standard = end
  date; Auto-Renewal/Evergreen = end date + renewal periods until on/after TODAY(), period =
  `Renewal_Term_Months__c` if entered, else 12 months (since 2026-09-23; the original initial-term
  default rolled multi-year auto-renewals 3+ years out, and nobody had filled Renewal Term).
  Formula ADDMONTHS keeps "last day of month" as last day (Jun 30 + 2 months = Aug 31). A past
  Renewal Date on an Active asset can only be a Standard contract (265 in Sep 2026). Field-level
  security on new fields is not granted by a metadata deploy, not even to the deploying admin:
  deploy a Profile fragment holding only the `fieldPermissions` entries (the classifier allows
  that; FieldPermissions DML was blocked). The Auto-Create Renewal Opportunity flow (v6, active 2026-09-23) dates the next renewal from the
  closed opp itself when it is a Renewal with a Renewal Date: that date + 12 months, rolled forward in
  12-month steps when that is already past (backlog closes). Assets (Renewal_Date__c lookups, opp-linked
  first, then account) drive only New Business closes and Renewals with no Renewal Date; today + 12
  months is the last resort. Close Date = renewal - 3 months (or today). The title has been
  `<root opp name> - <year> Renewal` since Solvd's v1 (root = first opp in the Original_Opportunity__c
  chain); root names that already end in "2026 Auto-Renewal" therefore get a second suffix, which
  Aaron wants left exactly as is. v2-v5 (Sep 3-21) used asset dates for every close and produced
  renewals 3+ years out (multi-year initial terms). The open flow-created renewals were re-dated to the
  new rule on 2026-09-23 (evening): Aaron ran 47 through dataloader.io (the auto-mode classifier blocks
  mass record updates and flow pauses from this session); 4 more had been hand-corrected by CS that
  night and were left as edited, 6 on multi-year Standard contracts were left for CS, 10 within a week
  of the rule were skipped. Before/after: scratchpad owner_audit/redate_dataloader_rows.json. Rollback harness: scratchpad renew6_A..C.apex (one closing opp per run).
  PARKED (Aaron, 2026-09-24): the +12-month default is a stand-in; nothing in the org records the real
  renewal period (asset `Contract_Term_Months__c` is only Contract End minus Contract Start, i.e. the
  original contract or the whole relationship once someone advances the end date; opp Contract End Date
  and the netsuite_conn term fields are blank on every won deal; asset `Renewal_Term_Months__c` is blank
  everywhere). When Aaron says so: add a Renewal Term (Months) field on the renewal opp, have the flow
  add that many months (fallback: asset Renewal Term, then 12), copy it onto the new renewal, and require
  it at Closed Won like Renewal Type. Asset date hygiene is with Marcia.
- MEDDIC (`MEDDIC__c`, Sep 2026): account-level MEDDIC records, master-detail to Account
  (`MEDDIC_Records__r`, reparentable) with a REQUIRED Opportunity lookup (cascade delete; lookup filter
  keeps the opp on the same account, enforced on API inserts too). Record types: `From_Opportunity`
  (mirror of the six opportunity MEDDIC fields, read-only via `Synced_Records_Are_Read_Only`, which
  rejects any edit that does not change `Last_Synced__c`; System Administrator exempt) and
  `Client_Success` (CS-entered). Two record-triggered flows: `MEDDIC_Sync_on_Opportunity_Create`
  (any of the six fields filled) and `MEDDIC_Sync_from_Opportunity` (update; entry = IsChanged on the
  six fields or AccountId). SCOPE (Marcia, 2026-09-24): MEDDIC applies only to Type "New Business - New
  Customer" and "New Business - Cross-Sell"; both flows carry that as an AND on the entry filter
  (create v3 / update v4, active 2026-09-24), so Renewal, Upsell and Revenue Enhancement deals are never
  mirrored. The 861 mirrors the backfill had created from those types are deleted by Aaron via Data
  Loader (scratchpad MEDDIC_Delete_NonNewBusiness.csv; mass deletes are blocked from this session);
  2 mirrors from the retired Type value "New Business - Net New" were kept as new business. Flow entry FORMULAS cannot reference rich-text fields (Metrics, Identify
  Pain), and the IsChanged entry operator is FALSE on record create, hence the split. Profile
  `fieldPermissions` cannot be deployed for required fields (Source__c, Opportunity__c). Related list
  sits last in the right column of `Account_Record_Page` and on the Account / Account - Prospect
  layouts (not Technology Partner). Mirrored source fields (nine): the six MEDDIC fields plus `Why_Passport__c`,
  `Compelling_Reason_Event_to_Close_in_Q__c` -> `Compelling_Event__c` and `Deal_Competition__c` ->
  `Competition__c` (multi-select copied as semicolon text). Cecily's Stage-4 lifecycle fields live on the
  same object for Client Success records only (Client Objectives, Measurement, Qualitative Success,
  Status incl. `Success_Status__c`, `Last_Reviewed__c`, `Next_Review__c`); the quarterly review reminder
  is NOT built. Backfill DONE 2026-09-24 (evening): 1,989 From Opportunity mirrors inserted for every opp
  with any of the nine fields filled, 41 opps skipped because the live flows had already mirrored them,
  0 failures (scratchpad `meddic_backfill_run.apex`; `meddic_backfill_dry.apex` is the rollback version).
  `Opportunity_Created_Date__c` (stored Date, added 2026-09-24) is stamped from the linked opp's
  CreatedDate by the before-save flow `MEDDIC_Set_Opportunity_Created_Date` (create and every save,
  both record types) so the Account related list sorts in deal order; it is a related-list column on
  both Account layouts and read-only on both MEDDIC layouts. A cross-object formula was avoided because
  related lists cannot sort on one. The
  Account - Prospect layout carried a dead Freshdesk related list (package removed) that a deploy now
  rejects; it was dropped from the layout on 2026-09-22. Deleting an opp
  cascades to ALL its MEDDIC records, CS-entered ones included.
  QA (2026-09-25): the overseas test team works from the Claude Doc "MEDDIC on the Account: Testing Guide"
  (claude.ai/code/artifact/d98ba219-4bf6-40d3-8d05-a6b46182a97f; four pillars W/D/E/B, test log with dropdowns).
  Testers use the existing accounts Admin Account Test Org (0010f00002KTyDcAAL) and Test (0016f00002oEF04AAG):
  every NEW account is pushed to Intercom (`Create_Intercom_Company_on_New_Account`). Opp actions that email
  real people: Type changed from Cross-Sell/Upsell to a New Business type (Cecily + Punith, `Notify_CS_Rep_when_Opp_Type_changes`),
  Inbound ticked (6 leaders), a past Close Date (account owner), owner/CS rep/implementation changes, any close.
  Gaps found by rollback probes (scratchpad meddic_qa_probe1-4.apex), not fixed, for Aaron to decide: the From
  Opportunity layout shows CS Notes (and Account/Opportunity) as editable but `Synced_Records_Are_Read_Only` blocks
  every non-System-Administrator save; both MEDDIC record types are visible to every profile, so anyone can
  hand-create a From Opportunity record, which duplicates the deal's copy (the sync then updates only one);
  `Competition__c` is Text(255) but `Deal_Competition__c` can exceed it (about 23+ values), which faults the sync
  (opp saves, copy stops updating, Aaron gets "MEDDIC sync failed"; longest live value 95 chars);
  `Compelling_Reason_Event_to_Close_in_Q__c` (feeds Compelling Event) is on no Opportunity layout; moving an opp to
  another account moves only its From Opportunity copy, and Client Success records left behind fail their lookup
  filter on the next save; a copy stays but stops syncing when the opp's Type leaves New Customer/Cross-Sell;
  restoring a deleted copy from the Recycle Bin after it was re-created leaves two copies. The 861 non-New-Business
  mirrors (480 Renewal, 195 Revenue Enhancement, 186 Upsell) were still present on 2026-09-25, so test D2 fails
  until Aaron's Data Loader delete runs. No MEDDIC field has history tracking on (MEDDIC History shows creates only).
  Account page list (Cecily, 2026-10-09): the MEDDIC Records list on `Account_Record_Page` is a Dynamic Related List
  (`lst:dynamicRelatedList`, identifier `lst_dynamicRelatedList_MEDDIC`) filtered `Opportunity_Stage__c|NOT_EQUAL|["Closed Lost"]`
  (Closed Won stays; 481 of 2,050 mirrors hidden at the time, no Client Success record affected). Dynamic related list
  facts: `adminFilters` values are `Field|OPERATOR|["value"]` with operators EQUALS / NOT_EQUAL (NOT_EQUALS is rejected
  with "Select a valid filter operator"), filters accept cross-object formula fields, columns are `relatedListFieldAliases`
  (NAME for the name field), sort is `sortFieldAlias` + `sortFieldOrder` Ascending/Descending. The same component already
  drives Active/Inactive Contacts and Won/Lost Opportunities lists on the Account and Technology Account pages. Probe prod
  flexipage XML with `sf project deploy start --dry-run` (no --test-level: NoTestRun is rejected in prod and `deploy validate`
  forces Apex tests). Standard related lists on this page follow the layout's column order; the live page order had
  drifted from the repo (Aaron's App Builder edits) and the repo copy was refreshed from the org on 2026-10-09.
- Report subscriptions (Analytics REST `/analytics/notifications`, source `lightningReportSubscribe`):
  POST creates one for the calling user (even when it returns "An unexpected error occurred" it may
  have created it, and a second POST then says "You already have a notification"); updates are PUT,
  not PATCH; `thresholds` must be omitted (`alwaysTrigger` and `static` are rejected for reports);
  only `daily`/`weekly` schedules are accepted (`{"frequency":"weekly","details":{"time":8,
  "daysOfWeek":["mon"]}}`), every monthly shape is rejected; and the object has no recipients
  property, so recipient lists and monthly frequency are UI-only (Report -> Subscribe). Success
  Reviews Due (`Support_Roundup_Updates/Success_Reviews_Due`, folder "Client Success") is meant to
  be subscribed monthly on the 1st with a Record Count > 0 condition; `Next_Review__c` is a formula
  (Last Reviewed + 3 months, else created + 3 months), so no CSM upkeep is needed for the dates.
- Client Success user template (compared 2026-09-30, scratchpad cs_user_template_comparison.md): all 15 CS
  people are on profile `CUSTOM - CS User` (00e0f00000108JDAAY, Salesforce license; 10 of 95 seats free) with
  permission sets Account Plans, Campaign Influence, Check In Permissions, Files Connect Cloud Access, Ironclad
  Standard User Clone (+ Einstein Search on 14) and PSLs CRM User, Einstein Search, Slack Service User, Standard
  Einstein Activity Capture User; Sales Cloud for Slack is on 8, LEX Pilot is legacy. Every 2026 hire (Madhura
  Banerjee creates them) has role Client Success Rep Team1 (00ER7000002Q3fSMAS), manager Meg Polak (Agents) or
  Tydus Mana (CSM/CSE), Division/Department Client Success, Company Passport Labs, Inc., Marketing User on for
  CSM/CSE. No CS user is in a public group or queue. Drift: Mike Buckley lacks Einstein Search + Slack Service
  User; Sean Calderon (005R700000NsYaXIAV, created 2026-09-01, manager Ben Stewart, role Client Success Rep,
  active SSO user) has no title/division and lacks Account Plans and Check In Permissions. Provisioning harness:
  scratchpad provision_cs_user.sh (create or complete a user to the template; review before running).
  Brett Lipensky (005R700000OP11VIAT, brett.lipensky@passportinc.com) was created 2026-09-30 as a clone of
  Dylan Trapp: CSM title, Team1 role, manager Tydus Mana, Marketing User on, the six shared permission sets plus
  Sales Cloud for Slack, and the four PSLs (`sf data create record -s User` + `sf org assign permset` /
  `permsetlicense`; the CLI accepts user creation from a cloud session).
- FOIA + Bid Intake (Prop Ops, live 2026-10-05 via change set "FOIA and Intake Form", 52 components; runbook +
  checklist from the foia sandbox session are in the session uploads, baseline/before/after copies in scratchpad foia/):
  Case record type `FOIA_Request` (business process = the six statuses, default New Request, compact layout came with the
  RT), 15 Case fields (`Capture_Strategy_Record__c` and `Requestor__c` pre-existed with data and merged cleanly), 4 Case
  validation rules, queue `Prop_Ops_FOIA` (Mackenzie Smith, Makanzie Ekstrom, Savanna Chrostowski; no queue email yet),
  8 flows all active v1 (`Bid_Intake` screen flow + 7 FOIA record/scheduled flows; the two scheduled ones run 07:00 ET
  as Aaron), reports + dashboard in folder `PropOps_FOIA` (View: All Internal Users), a FOIA donut appended to the
  Proposal Ops Dashboard (Marcia's, under Revenue_Ops_Dashboards/ProposalOperations). ACCESS (Aaron, 2026-10-05):
  `FOIA_Request_Submitter` = every active full-license user (85), so anyone can raise a FOIA request;
  `FOIA_Request_Prop_Ops` and `Bid_Intake_Access` = ONLY Mackenzie, Makanzie, Savanna, Aaron, Marcia Barnette, Punith
  Suresh (Michael Danko deliberately excluded); Case OWD is Private, so criteria sharing rule
  `FOIA_Requests_Visible_to_All_Internal_Users` (Read) lets everyone incl. the requestor see queue-owned FOIA cases.
  Shared config was edited by retrieve-append-deploy, never wholesale: StandardValueSets CaseStatus (+Submitted to
  Pursuit, Request for Resubmission; Delivered stays non-Closed) and CaseType (+FOIA Request), Capture Strategy
  `Product_Family__c` (restricted multi-select; LPR reactivated, +Spotblock, Photo Enforcement, Text to Pay, Guest
  Checkout, Other), Case AssignmentRules (FOIA entry at sort 1 of the active "Request Solutions Engineering" rule),
  Profile fragments carrying only `layoutAssignments` for Case-FOIA Request x FOIA_Request on 11 human profiles, six
  layouts (Capture Strategy got a "Bid Intake" section and an action override mirroring the UI API default action set
  plus `Capture_Strategy__c.New_FOIA_Request`; Account x2 and Opp Sales/Admin/Renewal got the action after Edit; global
  actions are referenced WITHOUT the `Global.` prefix). The Home page tile could NOT be deployed: the Flow component
  on `home:desktopTemplate` is `flowruntime:interview` (properties flowLayout=oneColumn, flowName), not
  `flowRuntimeForFlexipage`, which the API rejects in every region; Aaron placed it in App Builder (sidebar, visibility
  `{!$Permission.CustomPermission.Bid_Intake} EQUAL true`), and the picker lists only ACTIVE flows, so Bid_Intake was
  activated first. Record-type-gated quick actions stay hidden until the user holds the record type (perm set), and
  describe hides new fields until FLS arrives the same way: verify existence with Tooling CustomField. Deliverability
  is not readable by API. Smoke test (Bid Intake + FOIA from the Capstrat, status moves, login-as a Sales user) and
  TEST-record cleanup were still pending at the end of 2026-10-05; the negative check (no related record) passed by
  rollback probe (scratchpad foia/smoke_negative.apex).
  QA guide for Punith's team (2026-10-06): Claude Doc "FOIA Tracking & Bid Intake: Testing Guide"
  (claude.ai/code/artifact/5c829739-a24c-4a8a-9c61-c83e9aacc59e; rebuilt 2026-10-08 on the MEDDIC guide's four pillars
  W/D/E/B: 13 walk-through, 6 data, 6 exception, 10 breakability tests, 36-row log with Result + Severity dropdowns;
  one intake and three FOIA cases for the whole team, intake user / standard user / observer roles, ZZ TEST naming, no
  new Accounts; W5 sets the intake Capstrat's Account Name by hand because Bid Intake writes only the text field
  Intake_Account_Name__c; E3/E4 back-date Submitted Date / Expected Submission Date to trigger the scheduled reminders;
  B3/B4 go through Cases tab > New to reach the validation rules the quick action's required fields hide). Flow facts it relies on: `FOIA_Populate_Related_Records` stamps Type = "FOIA Request" and
  fills Account/Opportunity from the Capstrat (Capstrat wins) or the Opportunity; `FOIA_Stamp_Dates` defaults
  Requestor on create, stamps Submitted Date on the FIRST Submitted to Pursuit, clears Resubmitted Date entering
  Request for Resubmission and stamps it on refile, stamps Delivered Date once; `FOIA_Sync_To_Capstrat` sets
  FOIA_Requested__c/+Date on create and FOIA_Received_Date__c on the Delivered transition; the new-request email and
  the Monday unfiled sweep go to rfp@passportinc.com, the daily overdue email to the Requestor; status changes post
  to the case feed ("FOIA <n>: <old> -> <new> (<subject>)", plus "Documents received" on Delivered). Flow XML copies
  in scratchpad foia/flows/.
- `Estimated_Bid_Release_Required` (Opportunity validation rule, Aaron, 2026-05-05) asks for `Est_Bid_Release_Date__c`
  when Stage changes to RFP. Since 2026-10-05 it exempts the Renewal record type (Aaron's call after discussing keeping
  it): the Renewal stage order is Internal Review, Discovery, RFP, Contract, Closed, so the path's "Mark Stage as
  Complete" from Discovery walks every renewal through RFP and reps typed placeholder dates to pass (Dylan Trapp,
  21 renewals on 2026-09-26, scratchpad dylan_placeholder_bid_dates_before.csv; 19 are closed and were left alone
  because re-saving closed-won opps fires the Celigo trigger and ~33 flows). Related facts: the active flow
  `RFP_Checkbox_Required` sets `RFP__c = true` on any stage change into RFP, so those renewals are also flagged as RFP
  deals (all 40 renewal RFP-stage entries in T12 carry the flag; only ~6 were real rebids, e.g. Lowell, Sound Transit,
  SP Plus Dallas, Great Falls, Cincinnati); exempting renewals there too is an open decision. The Auto-Create Renewal
  flow copies `Est_Bid_Release_Date__c` onto the next renewal, so placeholder dates propagate. Rollback probe:
  scratchpad vr_est_bid_probe.apex. Renewals that are not bidding should move Discovery -> Contract/Closed Won by
  picking the stage, not Mark Stage as Complete.
- User audit reporting (Aaron, 2026-10-06, first subject Ashwin Chinivar): report folder + dashboard folder
  `User_Audit_Ashwin_Chinivar` ("User Audit - Ashwin Chinivar"), shared View to Marcia Barnette only (Aaron owns;
  `folderShares` in ReportFolder/DashboardFolder metadata DID apply on these NEW folders), nine tabular reports filtered
  on the user's name with Current CY time frames (Account/Opportunity/Case/MEDDIC field history via the standard
  `*AuditHistory` types, Reports built or edited via `ReportList`, Accounts/Assets/Opportunities created or last edited),
  and a 9-tile metric dashboard running as Aaron. Change the user filter to audit anyone else. Custom report type
  `Assets_with_Asset_History` (metadata fullName without `__c`; join `<relationship>AssetHistory</relationship>`, tables
  `Asset` / `Asset.AssetHistory`) fills the gap that Asset history has no standard report type, but Old Value / New Value
  are NOT exposed for standard-object history in custom report types (deploy says "Could not find field OldValue"), so
  values come from SOQL on `AssetHistory`. Report metadata on a custom report type names columns `Table$Field`
  (`Asset$Name`, `Asset.AssetHistory$CreatedDate`, lookups as `Asset.AssetHistory$CreatedBy`) and MUST carry
  `<scope>organization</scope>` or it silently runs as "my records" (0 rows); standard-type reports on
  `AssetWithProduct` reject `<scope>`; report `<name>` max 40 chars. `sf project deploy validate` runs local Apex tests
  and fails on the org's pre-existing broken `pkb_Controller*` classes (KnowledgeArticleVersion): use `deploy start`
  for non-Apex metadata. Audit limits: SetupAuditTrail and LoginHistory are API-queryable for ~180 days / ~6 months
  only and have no report type (download from Setup for anything older); field history covers tracked fields only
  (lookup changes write TWO history rows, EntityId + Text, so SOQL counts are 2x the report's); LastModifiedBy shows
  only the latest editor; no Event Monitoring (no report-run/export/Data Loader visibility). Ashwin's 2026 footprint:
  254 `Client_Success_Rep_2__c` reassignments on 2026-04-15, ~470 Asset Status/InstallDate edits spread Jan-Oct,
  9 reports, 2 opps, 2 assets, 2 MEDDIC records, no metadata authored. Exports in scratchpad ashwin/.
  Dashboard lessons (2026-10-06): a Metric/chart component on a TABULAR report fails at run time with error 209
  ("cannot be used as the source for this component") even though the deploy succeeds, so every audit report is now
  a Summary grouped by its date column with `<dateGranularity>Month</dateGranularity>` (drop that column from
  `<columns>` and drop the report-level `<sortColumn>`, which may not name the grouped column). The dashboard carries
  a "Month (2026)" filter (12 `between` options, dates as M/d/yyyy) mapped per component via
  `<dashboardFilterColumns>`; filter option Ids are regenerated on every dashboard redeploy. Analytics API: GET
  `/analytics/dashboards/<id>?filter1=<optionId>` returns cached results only; PUT the same URL with `{}` to refresh.
  Report month buckets are in the running user's timezone, SOQL CALENDAR_MONTH is UTC, so counts can differ by a few
  late-night rows.
- SOAP API login() retirement (Salesforce notice to Marcia 2026-10-06; retired Summer '27 for API v31-64, and
  Winter '27 requires the new user permission `PermissionsUseAnyApiAuth` "Use Any API Auth" or login() returns
  INSUFFICIENT_ACCESS): LoginHistory shows ONE real SOAP login() client, the Celigo NetSuite integration running as
  user "Passport Operations" (ops@gopassport.com, profile CUSTOM - SysAdmin Integrations, SOAP Partner API v35.0,
  daily ~09:00 UTC, 147 successful logins Apr-Oct 2026). Fivetran tried SOAP twice on 2026-08-21 and failed; its
  real traffic is OAuth ("Fivetran Data Loader"). Every other integration is OAuth (Remote Access 2.0) or SSO;
  LoginType "Application" rows are browser username/password logins, not API. As of 2026-10-06 nobody in the org
  holds Use Any API Auth. Plan: (1) assign it to Passport Operations before Winter '27 lands (a small permission set
  is the clean way), (2) have the Celigo admin switch the integrator.io Salesforce connection to OAuth (connected app
  `Integrator_io` exists since 2018) before Summer '27. Evidence in scratchpad soap/.
- Dispute Chargeback Fee (Sep 2026, case 00105850, Courtney Louiselle / Karen in Finance): the flat
  per-dispute fee the client pays lives in the REUSED Opportunity field `Charge_Back_Fee__c` (relabeled
  "Dispute Chargeback Fee"; 0 = client pays none; it existed since 2018 on no layout with four $0
  values that were left alone to avoid re-saving old closed-won deals). On the Sales, Admin,
  SD/Implementation and Renewal layouts next to Finance Notes; all 24 profiles already had access.
  Validation rule `Dispute_Fee_Required_on_Payments_Deals` stops Standard-record-type deals whose
  `Product_Family_RU__c` (Rollup Helper text; matched the Payments line items on all 416 Payments deals
  won in the prior 12 months) contains "Payments" from entering Contract or Closed Won with the fee
  blank; renewals are exempt. The SALES Closed Won Notification templates (HTML `SALES_Closed_Won_Notification`,
  text `MB_Test_Closed_Won_Text`, both unfiled$public) carry the fee for the PR ticket that Payment
  Operations configures settlement from. The order form is the Ironclad "2026 Passport Order Form"
  workflow launched from the opportunity; its field mapping is configured in Ironclad, so mapping the
  fee there is an Ironclad-admin task, not metadata. Rollback harness: scratchpad vr_dispute_fee3.apex
  (test deals need Incumbent__c and, for renewals, Renewal_Typ__c).
