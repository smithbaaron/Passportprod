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
  The org carries 45 Opportunity validation rules; this repo holds 8 (retrieve
  `CustomObject:Opportunity` for ground truth).
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
  renewals 3+ years out (multi-year initial terms); 51 open flow-created renewals were re-dated on
  2026-09-23 (scratchpad owner_audit/redate_exec.json holds before/after), 6 on multi-year Standard
  contracts were left for CS. Rollback harness: scratchpad renew6_A..C.apex (one closing opp per run).
- MEDDIC (`MEDDIC__c`, Sep 2026): account-level MEDDIC records, master-detail to Account
  (`MEDDIC_Records__r`, reparentable) with a REQUIRED Opportunity lookup (cascade delete; lookup filter
  keeps the opp on the same account, enforced on API inserts too). Record types: `From_Opportunity`
  (mirror of the six opportunity MEDDIC fields, read-only via `Synced_Records_Are_Read_Only`, which
  rejects any edit that does not change `Last_Synced__c`; System Administrator exempt) and
  `Client_Success` (CS-entered). Two record-triggered flows: `MEDDIC_Sync_on_Opportunity_Create`
  (any of the six fields filled) and `MEDDIC_Sync_from_Opportunity` (update; entry = IsChanged on the
  six fields or AccountId). Flow entry FORMULAS cannot reference rich-text fields (Metrics, Identify
  Pain), and the IsChanged entry operator is FALSE on record create, hence the split. Profile
  `fieldPermissions` cannot be deployed for required fields (Source__c, Opportunity__c). Related list
  sits last in the right column of `Account_Record_Page` and on the Account / Account - Prospect
  layouts (not Technology Partner). Mirrored source fields (nine): the six MEDDIC fields plus `Why_Passport__c`,
  `Compelling_Reason_Event_to_Close_in_Q__c` -> `Compelling_Event__c` and `Deal_Competition__c` ->
  `Competition__c` (multi-select copied as semicolon text). Cecily's Stage-4 lifecycle fields live on the
  same object for Client Success records only (Client Objectives, Measurement, Qualitative Success,
  Status incl. `Success_Status__c`, `Last_Reviewed__c`, `Next_Review__c`); the quarterly review reminder
  is NOT built. Backfill = one mirror per opp with any of the nine fields filled (1,994 opps / 1,103
  accounts as of 2026-09-22): scratchpad `meddic_backfill_dry.apex` (rollback) is the template. The
  Account - Prospect layout carried a dead Freshdesk related list (package removed) that a deploy now
  rejects; it was dropped from the layout on 2026-09-22. Deleting an opp
  cascades to ALL its MEDDIC records, CS-entered ones included.
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
