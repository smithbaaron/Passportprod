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
