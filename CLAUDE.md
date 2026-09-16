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
- Accounts with `Status__c = 'Former'` and a blank `Churn_Explanation__c` are
  un-editable (validation rule) — automation must skip them.
- Account at-risk fields are a projection of the At-Risk Journey child records
  (kept true by the At_Risk_Account_Mirror_Sync flow). Fix the journey, never
  hand-edit the account mirror.
- Long-text fields can't be filtered in SOQL/reports; Tooling API JSON nulls
  collection-typed flow action inputs (Metadata XML is ground truth); report
  Metadata deploys strip blank-value filters (use the Analytics REST API PATCH).
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
