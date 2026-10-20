<!-- Markdown copy of the Claude Doc "Price Increase Automation: Sandbox Build Handoff" (https://claude.ai/code/artifact/47573c9d-7fb0-43ef-b22b-dfac2b739dc6), exported 2026-10-20 at rev 13. The doc is the living version; this copy is for sessions that cannot reach it. -->

# Price Increase Automation: Sandbox Build Handoff

2026-10-20 · @Aaron

## Where the project stands

The direction is set and the build is ready to start in the PIA sandbox (Developer sandbox, description "Price Increase Automation", created 2026-10-20, still provisioning when this was written). This document carries everything the build session needs; nothing else from the earlier chats is required.

- **What it is.** Move Cecily's spreadsheet of contractual fee increases and price-lock clauses into Salesforce, so notice dates, the increase itself and the resulting Revenue Enhancement opportunity are tracked and timed by the system.
- **Chosen design.** Option A from the Options doc: a Price Escalation custom object under the Account, one record per escalator clause, with a button that creates the Revenue Enhancement deal and flows that remind, roll forward and close the loop. Option B (four fields on the Asset) was rejected because the clause shapes do not fit it.
- **Feasibility.** Confirmed in production on 2026-10-14 with read-only queries and two savepoint-and-rollback Apex probes; nothing was left behind. The VP / Controller's challenge ("are you sure this can be done in Salesforce?") was answered on 2026-10-16: yes, standard configuration, about a week to configure.
- **Business decisions so far.** Cecily (Client Success lead, 2026-10-16): start with the button, move to automatic creation later once client exceptions can be built in. Who enters the terms at contract approval is with Marcia Barnette to decide (Punith at close versus the CS rep).
- **People.** Aaron Smith (RevOps, builds and owns), Cecily (Client Success, requirement owner and first user), Marcia Barnette (RevOps lead, decides the entry owner), Punith Suresh (Proposal Ops, logs contracts and may enter the terms), the VP / Controller (Finance sponsor; the Finance ticket consumer), the CS reps (create and close the deals today).
- **What the new session is expected to produce.** The object, its fields and page, a permission set, the Create Increase Opp action, three flows, reports and list views, all built in PIA, tested with ZZ TEST data, then packaged for production with Cecily's rows (about 50) loaded last.

## Business requirement

Cecily keeps a spreadsheet of accounts whose contracts allow a periodic fee increase or carry a price lock. It started with 12 fully worked rows and, in the 7 October export, had grown to about 50 across three later batches researched in Ironclad, most of them on Passport's standard escalation template (2 to 7 percent a year, a CPI increase capped at 7 percent during renewal terms, and a proportional increase when the client raises its own rates), several marked "pending contract signature". Nothing in Salesforce records a contract's escalator terms, its notice period or its next increase date, so the increases are tracked and timed by hand.

**What the sheet holds per row.** Account, CS rep, whether a price lock applies, the products covered, the clause text verbatim, the contract effective date, the 2027 increase date (one year on from the last), the notice date (60 days before the increase unless the contract says otherwise; one contract says 120), the planned percentage (5 percent is the 2027 planning assumption) and the revenue impact for 2026 and 2027.

**Her process today, five manual steps.** Read the Ironclad approval; add the row; compute the two dates; send the notice to the client and raise the Finance ticket; ask the CS rep to create the Revenue Enhancement opportunity.

**Clause shapes the model has to hold.** The 12 rows are wider than a single percentage: a 2 to 7 percent band at each anniversary; a fixed 5 percent step; a per-transaction step schedule by year (Year 1 $0.06, Year 2 $0.08, up to Year 5 $0.16); a dollar cap per increase ($0.05) with a lifetime ceiling ($0.40) and 120 days' notice; a semi-annual step ($0.15 to $0.17 on 3/2/27, then $0.20 six months later); CPI-linked increases during renewal terms; escalations that start in Year 6 and Year 11 of a contract; and per-product escalators that differ within one contract (Sound Transit alone has five). Whatever is built has to hold more than one escalator per account and more than one step per escalator.

**What the automation must do.**

1. Hold the terms as records, one per escalator clause, with the products covered and the clause text.
2. Compute the next increase date and the notice-due date, and remind the CS rep and Cecily before notice is due.
3. Create the Revenue Enhancement opportunity from the record with one click, pre-filled in the convention the team already uses, and link it back.
4. When that opportunity closes won, mark the increase effective and roll the next increase date forward so the cycle restarts.
5. Allow a client to be excluded from automatic increases, with a reason, so that the later automatic version can skip them.
6. Report on increases by month, notices due this quarter and impact by product, and give each CS rep a list view in place of the sheet.

**What already exists in the org that the build reuses.** Revenue Enhancement is an existing Opportunity Type on the Standard record type: 129 such deals were created in the last 12 months, 108 won, in batches (45 in May, 24 in November), almost all closed by Client Success. The naming convention is "\<Account> - 5% Increase Rev Enhancement - \<year>", Lead Source Client Success, forecast Pipeline, Amount equal to the increase, CS rep filled. An existing flow emails Client Success when a Revenue Enhancement deal is closed by CS. The Ironclad order-form workflow already captures two yes/no properties, feeAdjustmentsYn and customFeesYn, which could one day feed the entry step.

## Decisions made and questions open

| # | Question | Status | Answer or owner |
| --- | --- | --- | --- |
| 1 | Button or automatic creation of the Revenue Enhancement deal? | Decided (Cecily, 2026-10-16) | Start with the button. Move to automatic later, once client exceptions are built in. Build the exclusion flag now so the switch is a flow change, not a rebuild. |
| 2 | Who enters the escalator terms at contract approval? | Open (Marcia Barnette) | Punith reads every order form at close and is the natural entry point; the CS rep would then see the terms without entering them. If Marcia picks the CS rep, require the terms at the CS handoff rather than at Closed Won, so the gate sits where the person is. The answer decides whose layout gets the entry form. |
| 3 | Where does the Finance ticket live? | Open (VP / Controller) | If Jira or email, the record holds a reference only. If it should be raised automatically from the status change, that is a separate small piece (Zapier or an email alert to the Finance queue). |
| 4 | The planning percentage | Open (Cecily) | One org setting Cecily can change each year, inherited by every record without its own cap. 5 percent assumed for 2027. |
| 5 | Where the exclusion lives | Decided (promised to Cecily) | A checkbox on the escalation record, "Exclude from automatic increases", with a reason field. The button and the later scheduled flow both respect it. |
| 6 | What Cecily was told the entry point looks like | Decided (wording) | In plain language she was told "a small Price Terms section" on the deal record. The build is the Price Escalation related list, shown on the Account and on the closed deal, so her mental model holds either way. |
| 7 | Which Revenue Enhancement Type value the created deal carries | Open (RevOps) | The picklist already has MPP Fee Increase, CMP Fee Increase, Termination Fee, USPS, Cardholder Security, Other, and is blank on most deals. Either stamp the matching Fee Increase value from the products covered or add one value, Contractual Escalator. |
| 8 | Ask Arrive whether they run something similar | Open (Cecily's suggestion) | Their field list would be a free review of this one; no access to Arrive's org yet. |

One sentence to confirm with Cecily before building the reminder: the reminder goes to the account's CS rep as a task and to Cecily as a weekly digest; nobody else is on it unless she says so.

## Design: data model

One custom object, **Price Escalation** (`Price_Escalation__c`), master-detail to Account, one record per escalator clause. A contract with different escalators per product gets one record per product. The record name is set by the create flow as "\<Account> | \<products> | \<type>" so list views read without opening records.

| Field | Type | Purpose and notes |
| --- | --- | --- |
| Account | Master-detail | Owner of the clause; gives the related list on the Account page |
| Source Contract | Lookup to Ironclad Contract | Where the clause came from; optional until the Ironclad backfill lands. Keep an Ironclad Record ID text (IC-5593 style) beside it |
| Source Opportunity | Lookup to Opportunity | The closed deal whose order form set the terms; optional |
| Asset | Lookup | The product line it prices; optional |
| Products Covered | Multi-select picklist | MPP, CMP, DPP, Payments / Merchant Processing, LPR / MLPR, Permits, Managed Services / Enforcement, Hardware, Card Present / Gateway Fee. No global value set exists for product family; create this list from Cecily's sheet, not from Product2 Family |
| Price Lock | Checkbox | The contract caps or fixes increases |
| Escalation Type | Picklist | Standard template (2 to 7 percent plus CPI cap), Price-lock band, Fixed percent, Fixed amount per transaction, Step schedule, CPI-linked, Proportional to end-user rate, Fixed for term (no increase) |
| Planned Increase % | Percent | Defaults from the org setting (5 for 2027); the figure the created deal uses |
| Cap % | Percent | The 7 percent of a band |
| Cap Amount per Increase | Currency | The $0.05 |
| Lifetime Ceiling | Currency | The $0.40 |
| Clause Text | Long text | Verbatim verbiage column |
| Fee Adjustments | Long text | Pass-through and direct-cost language, kept separately so it is not mistaken for an escalator |
| Contract Effective Date | Date | Anchor for anniversaries |
| Increase Interval (months) | Number, default 12 | 6 for the semi-annual contract |
| Next Increase Date | Date | Hand-entered once, rolled forward by the close flow |
| Last Increase Date | Date | Stamped by the close flow |
| Notice Days | Number, default 60 | 120 where the contract says 120 |
| Notice Due | Formula (date) | Next Increase Date minus Notice Days |
| Reminder Sent | Date | Stamped by the weekly flow so a record is reminded once per cycle |
| Status | Picklist | Not started, Notice due, Notice sent, Opp created, Effective, Skipped |
| Exclude from Automatic Increases | Checkbox | Promised to Cecily; the button warns and the later scheduled creation skips |
| Exclusion Reason | Picklist + text | Contract fixed for term, Client relationship, Pending renegotiation, Other (with a note) |
| Steps | Long text (phase 1) | The Year 1 to Year 5 schedules and the Year 6 / Year 11 clauses. If Cecily wants step-level reminders later, promote to a child object Price Escalation Step (Effective Date, New Rate, Percent, Description) |
| Estimated Revenue Impact | Currency | Her 2026 and 2027 impact columns; one value per cycle, so keep Impact Year beside it |
| Revenue Enhancement Opp | Lookup to Opportunity | The deal created for the current cycle |
| Finance Ticket | Text | Reference raised outside Salesforce (decision 3) |
| Notes | Long text | Her Notes column (entity-name clarifications, master-agreement caveats) |

**On the Opportunity.** One new lookup, Price Escalation (`Price_Escalation__c`), so the close flow can find its record and the deal page shows where it came from. Four Opportunity fields with similar names already exist and are nearly empty (Price Due 41 rows, Price 34, Initial Ticket Price and Escalation 10, Price Negotiations 7, Price Done 14 ticks); do not reuse them, and consider retiring them in the field cleanup.

**Org setting.** One custom metadata type or hierarchy custom setting, Price Escalation Settings: Default Planned Increase % (5), Default Notice Days (60), Reminder Window Days (14), Default Interval (12), Digest Recipient (Cecily's address in production, Aaron's in the sandbox).

**Access.** Permission set Price Escalation User with create, read, edit on the object and all fields for CUSTOM - CS User, CUSTOM - SF Admin, Revenue Operations and Proposal Operations (Punith); read for CUSTOM - Sales User. Field-level security is not granted by a metadata deploy, so deploy the permission set, not profile fragments, and remember the two required lookups cannot carry profile field permissions.

**Pages.** A record page for the object; a Price Escalations related list on the Account record page and on the Opportunity record page. If the Account list is built as a dynamic related list, set the New action explicitly or the list shows no buttons (the MEDDIC list lost its New button for a week this way).

**Validation rules.** Next Increase Date required unless Status is Skipped or Escalation Type is Fixed for term; Notice Days above 0; Exclusion Reason required when excluded; Planned Increase % or a cap required for the percent types; Increase Interval above 0.

## Design: automation

Three flows and one action in phase 1; the automatic version in phase 2 reuses the same create logic, so build the deal creation as an autolaunched subflow from the start.

**1. Create Increase Opp (quick action on Price Escalation, screen flow calling the subflow).**

- If Exclude from Automatic Increases is ticked, show the reason and stop unless the user confirms an override.
- Show the planned percent and estimated amount for edit, then create the Opportunity: record type Standard Opportunity; Type Revenue Enhancement; Name "\<Account> - \<pct>% Increase Rev Enhancement - \<year of Next Increase Date>"; Account; Stage Discovery; Close Date = Next Increase Date; Lead Source Client Success; Forecast Category Pipeline; Next Step "Send \<Notice Days>-day notice" (the Next Step rule fires on every stage change for non-Renewal deals, so it must be filled from the start); Owner and Client Success Rep = the Account's Client Success Rep, falling back to the Account owner; Revenue Enhancement Type = the value settled in decision 7; Price Escalation = this record; Description = the clause summary.
- Add one Opportunity Product line for the escalated product from the standard price book (quantity 1, sales price = the estimated increase, description "\<pct>% escalation on \<product>"). Without a line the deal cannot close won; with it Amount and Product Family roll up. Products and price-book entries are data, so the sandbox needs at least one of each.
- Set Status = Opp created and the Revenue Enhancement Opp lookup. Side effects already proven harmless: the Slack new-opportunity post is limited to New Customer and Cross-Sell; the MEDDIC mirror and the CS Type-change email do not fire for this Type.

**2. Weekly reminder (scheduled flow, Monday 07:00 Eastern, runs as the admin like the FOIA sweeps).** Records where Notice Due is within the reminder window, Status is Not started or Effective, Reminder Sent is blank for this cycle, and the record is not excluded. For each: create a Task for the Account's Client Success Rep (fallback Account owner) due on Notice Due, subject "Price increase notice due \<date>: \<Account> (\<products>)", related to the escalation record. The Task rule Require_WhoID demands a Contact on every task, so the flow picks the Account's billing contact, then any contact, and skips the task (email only) when there is none. Stamp Reminder Sent, set Status = Notice due, and send one digest email to the setting's recipient listing every record touched. Cecily sets Status = Notice sent by hand when the letter goes out.

**3. Close the loop (record-triggered flow on Opportunity, after save).** Entry: Type = Revenue Enhancement, Price Escalation not blank, stage changed to Closed Won. Actions on the escalation record: Last Increase Date = Close Date; Next Increase Date = Next Increase Date plus Increase Interval months (ADDMONTHS keeps month-end dates); Reminder Sent cleared; Status = Effective; keep the Revenue Enhancement Opp lookup until the next cycle's deal replaces it. One escalation per deal; if one deal covers several escalators, create one deal per escalator rather than a junction.

**Phase 2, automatic creation.** A second branch in the weekly flow calls the same subflow for records inside the window that are not excluded, instead of waiting for the button. Cecily asked for this once exceptions exist; the exclusion flag is the exception mechanism. Expected volume is roughly 100 deals a year, which is why it stays off until the reps have lived with the button.

**Not automated.** The notice letter itself, the Finance ticket (decision 3) and the entry of the terms at contract approval (decision 2). Ironclad already carries feeAdjustmentsYn, customFeesYn and priceLockYn properties; mapping them into Salesforce is Ironclad-side configuration and would remove the manual entry later.

**Reporting.** Reports: increases by month (by Next Increase Date), notices due this quarter, impact by product, exclusions. List views on the object per CS rep. A dashboard is optional. The master-detail gives the "Accounts with Price Escalations" report type for free.

## Org facts and rules the build must respect

All read from production on 2026-10-14 to 2026-10-20.

**Who does what today.** Revenue Enhancement deals sit on the Standard Opportunity record type (all 131 created in the last 12 months) and are a Client Success process: CS users closed 113 of the 116 won in the last 12 months, Minimum Access users the other 3. Sales owns New Customer and Cross-Sell. The Account's rep field is `Client_Success_Rep_2__c`; the Opportunity's is `Client_Success_Rep__c`.

**Rules a Revenue Enhancement deal meets on the way to Closed Won.**

- Create: no deal may be created already closed (`Users_cannot_create_a_Closed_Opp`). The Next Step rule (`Next_Step_must_be_current`) fires on every stage change for non-Renewal record types, so the flow must set Next Step on create. Lead Source is locked only for marketing-converted deals.
- Stage gates (`Stage_Gate_*`, `Stage_Discovery_Fields`, `Required_Incumbent`) apply to New Customer and Cross-Sell only (each formula tests Type, checked 2026-10-20); they do not touch this Type. Avoid the RFP stage: `Estimated_Bid_Release_Required` fires on entering it.
- Closed Won: Why Passport (`Require_Why_Passport`), at least one Opportunity Product (`Stop_close_won_opp_missing_opp_product`), Billing City and State on the Account, a Close Date. The Ironclad Workflow rule exempts Revenue Enhancement. `Dispute_Fee_Required_on_Payments_Deals` fires at Contract and Closed Won on Standard-record-type deals whose Product Family roll-up contains Payments: an escalation line on a Payments product needs Dispute Chargeback Fee filled (copy it from the source deal).
- Closed Lost needs a Lost Reason and Lost Details. Closed deals are locked for non-admin profiles once the forecast lock flag is set.

**Automation that fires around the deal.**

- On create: the Slack new-opportunity post is limited to New Customer and Cross-Sell; the MEDDIC mirror flows and the CS Type-change email skip this Type. The workflow rule "New CS Rep Assignment for Opps" and the flow "Opportunity – Send Email on Owner or CS Rep Change" may email the CS rep when the rep field is filled; in the sandbox that mail goes nowhere (user addresses carry .invalid), in production it is the same email a hand-made deal sends today.
- On Closed Won: the Closed Won master flow routes New Business, Cross-Sell and Upsell only, so no announcement; the flow "EMAIL ALERT: Notify CS that an RevEn opp has been Closed-By-CS" fires; the Slack deals-won post fires; the Account workflow sets Status to Current and the roll-ups re-save the Account (which can surface the Account's own validation rules, for example the churn explanation on a Former account). The NetSuite connector (Celigo) trigger runs on closed-won deals; manual Revenue Enhancement deals already go through it, so nothing new, but it hits its own SOQL limit if more than one deal closes in one transaction. Close one deal per transaction in any data load.
- The Auto-Create Renewal flow does NOT fire for this Type: its entry formula is Closed Won AND Type in (New Business - New Customer, Renewal). No renewal is spawned by a price-increase close. Verified in the flow definition on 2026-10-20.

**Tasks.** The Task rule `Require_WhoID` rejects any task without a Contact. Every reminder task needs a WhoId.

**Picklists.** `Revenue_Enhancement_Type__c` values in use (all time): USPS 59, Cardholder Security 49, MPP Fee Increase 10, CMP Fee Increase 5, Termination Fee 5, Other 3; blank on 911 of the 1,042 Revenue Enhancement deals overall and on 123 of the 131 created in the last 12 months. No global value set exists for product family; the Capture Strategy object has its own restricted multi-select.

**Deploying.** Active flows cannot be deployed directly: deploy as Draft, then activate by Tooling PATCH on FlowDefinition (`{"Metadata":{"activeVersionNumber":N}}`). Field-level security does not arrive with a metadata deploy; a permission set carries it. `sf project deploy validate` runs local Apex tests and fails on the org's broken legacy `pkb_Controller*` classes, so use `deploy start` (with `--dry-run` to validate) for non-Apex metadata.

**Testing discipline (repo CLAUDE.md).** Test emails go to aaron.smith@passportinc.com only. Prefer savepoint-and-rollback anonymous Apex for data-layer tests. Visible test records are named "ZZ TEST ... (delete me)" and cleaned up. Discuss before changing production; build, test, verify, clean up, revert anything temporary.

## Feasibility evidence already in hand

On 2026-10-14 every step of the design was walked against production without creating anything: read-only queries plus two savepoint-and-rollback Apex probes that built the records the automation would build and then discarded them. Test account: Admin Account Test Org (`0010f00002KTyDcAAL`), the standing test account that the MEDDIC and FOIA test guides also use.

| Step | What the org has | Probe result |
| --- | --- | --- |
| Custom object under Account with lookups to Asset, Ironclad Contract and Opportunity | All four accept lookups; 30 own custom objects exist (Tooling count, 2026-10-20), well inside the limit | Standard metadata, nothing to test |
| Products covered picklist | No global value set for product family | Build the list from Cecily's product column |
| Task to the CS rep | Account carries Client Success Rep and Secondary CS Rep; seven scheduled flows already run | Task insert failed without a Contact ("You must populate the Name field", the Require_WhoID rule), succeeded with one |
| Email digest | Flow email alerts in daily use; 0 of 5,000 single-email sends used | Not exercised; standard |
| Pre-filled Revenue Enhancement deal | 131 created in the last 12 months (70 by admins, 58 by CS, 3 by Minimum Access users), all on the Standard record type, in the naming convention | Insert with Name, Account, Standard record type, Type, Stage Discovery, Close Date, Lead Source, Forecast Pipeline, Next Step, CS Rep succeeded with no validation error; Incumbent not required |
| Deal to Contract and Closed Won | 30 active Opportunity validation rules | Contract passed. Closed Won failed only on "add a product before closing as won"; with one Opportunity Product line (Citation Management from the standard price book, quantity 1, sales price = the increase) Closed Won passed, Amount rolled up and Product Family rolled up |
| Roll Next Increase Date forward after close | Record-triggered flow pattern on Opportunity already proven by the CS closed-by-CS email flow | Standard |
| Side effects of creating the deal | Slack post only for New Customer and Cross-Sell; MEDDIC and CS Type-change flows skip this Type | None beyond what a manual deal does today |

Limits during the probes stayed far inside governor limits (a handful of queries and DML statements). Email delivery and the user-facing layout were not exercised. The two scripts are in the repo under `docs/price-increase/` as `pricelock_probe.apex` (minimal insert, stage moves, task without contact) and `pricelock_probe2.apex` (line item, stage moves, task with contact); both end with `Database.rollback`. Reuse them in the sandbox as the first regression test, pointing the Account Id at a seeded ZZ TEST account (a Developer sandbox carries no data).

## Sandbox plan

**The sandbox.** PIA, a Developer sandbox described "Price Increase Automation", requested 2026-10-20 at 20:58 UTC and still processing when this was written. Other sandboxes on the org: FOIA (Developer, refreshed 2026-08-19, the FOIA build), Partial (refreshed 2026-04-14, stale sample data), and several Developer sandboxes used by Punith and Solvd. A Developer sandbox copies metadata and custom settings only: no accounts, contacts, products, price-book entries or deals, and every user's email gets .invalid appended, so no flow can email a real person by accident.

**Connecting the new session.** The cloud session authenticates with an SFDX auth URL kept as an environment secret; the repo's `scripts/session-setup.sh` logs into production from `SFDX_AUTH_URL`. For the sandbox:

1. On a machine with the Salesforce CLI, once the sandbox is active: `sf org login web --instance-url https://test.salesforce.com --alias pia` (the My Domain form is `https://passportlabs--pia.sandbox.my.salesforce.com`). The sandbox username is `aaron.smith@passportinc.com.pia`; SSO settings copy over, and a password reset from the sandbox login page works if SSO does not.
2. `sf org display --target-org pia --verbose --json` and copy the `sfdxAuthUrl` value into a new environment secret, for example `SFDX_AUTH_URL_PIA`. Never paste it into chat or commit it.
3. In the new session: `printf '%s' "$SFDX_AUTH_URL_PIA" | sf org login sfdx-url --sfdx-url-stdin --alias pia`, then every command uses `-o pia`. Keep production out of that session, or read-only, until the deploy step.

**Before building anything in PIA.**

- Deactivate the flows that call outside systems, or expect fault emails on every test record: Create Intercom Company on New Account (named credential callout), the four record-triggered Slack flows (new opportunities, opportunity changes, deals won, Capture Strategy created) and the three scheduled Slack digests. Celigo, HubSpot, Gong and Fivetran are simply not connected to a sandbox.
- Email Deliverability (Setup, Email Administration): System email only is the sandbox default; switch to All email only while testing the digest, with Aaron's address as the digest recipient.
- Seed test data: two or three "ZZ TEST ... (delete me)" Accounts (Status Current, Type Customer, Billing City and State filled, Client Success Rep set to a sandbox user), one Contact each (the task rule needs it), one Account with no contact (the fallback case), a Closed Won deal on one of them, and at least two active Products with standard price-book entries (Citation Management, an MPP transaction fee) because products are data and will not exist.
- Assign the new permission set to the sandbox test users; add a CUSTOM - CS User test user if one is needed to test access.

**Cecily's rows.** Load them in production only, after the build is accepted, as the first real data. The source is the 7 October export, kept in the repo as `docs/price-increase/cecily_price_lock_sheet_2026-10-07.pdf` with its text extraction beside it: about 50 rows across four batches, most on the standard 2 to 7 percent template with 5 percent planned and notice 60 days before the increase, several marked pending contract signature, a few with entity-name caveats in her Notes column. Her Google Sheet remains the source of truth, so re-export it before the load. In the sandbox, load three or four of them by hand to test the awkward shapes: the $0.05 per increase with $0.40 ceiling and 120 days' notice, the Year 1 to Year 5 step schedule, the semi-annual $0.15 to $0.17 to $0.20 step, and the Sound Transit multi-product Year 6 / Year 11 clause.

**Deploying back to production.** Build in source format under `force-app/main/default` in the repo (objects, fields, validation rules, flows, quick action, permission set, custom metadata, record page changes), commit on a feature branch, deploy to PIA with `sf project deploy start -o pia`, and later to production with `sf project deploy start -o prod --dry-run` then without it: flows as Draft, activated by Tooling PATCH; permission set assigned with `sf org assign permset`; related lists on the Account and Opportunity record pages. The FOIA build went in as a change set instead; either works, the repo route leaves the metadata versioned.

## Build checklist and acceptance tests

**Build order.**

1. Settle decisions 2 and 7, or proceed on the defaults: Punith enters the terms at contract logging, and the created deal carries Revenue Enhancement Type = the matching Fee Increase value, with a new value Contractual Escalator added for products without one.
2. Sandbox ready: auth, outside-system flows deactivated, deliverability set, seed data and a test CS user in place.
3. Custom metadata Price Escalation Settings with the five defaults.
4. Object Price Escalation: fields, validation rules, record page, compact layout, list views; Price Escalation lookup on Opportunity; related lists on the Account and Opportunity record pages.
5. Permission set Price Escalation User; assign in the sandbox.
6. Autolaunched subflow Create Revenue Enhancement Deal (inputs: escalation Id, percent, amount, product); quick action Create Increase Opp with its screen flow calling it.
7. Scheduled flow Price Escalation Weekly Reminder (Monday 07:00 Eastern).
8. Record-triggered flow Price Escalation Close Loop on Opportunity.
9. Reports (increases by month, notices due this quarter, impact by product, exclusions) in a Client Success report folder; list views per CS rep.
10. Run the acceptance tests below; fix; re-run.
11. Package: commit, dry-run deploy to production, deploy, activate flows, assign the permission set to the CS, RevOps and Proposal Ops users, load Cecily's rows, walk Cecily through one cycle on a real record.
12. Update the Process & Data Dictionary (Process 5 "Price increases" paragraph and Process 6) and the repo's CLAUDE.md with what was built.

**Acceptance tests.**

| # | Test | Expected |
| --- | --- | --- |
| T1 | Create one escalation of each Escalation Type, including the $0.05 / $0.40 cap, the Year 1 to 5 steps and the 6-month interval | Saves; Notice Due computes; validation rules reject a blank Next Increase Date, Notice Days 0, an excluded record without a reason |
| T2 | Click Create Increase Opp on an excluded record | Warning with the reason; nothing created unless overridden |
| T3 | Click Create Increase Opp on a normal record | Deal created with every field in the convention, one product line, Amount rolled up, CS rep set, Next Step filled, status Opp created and the lookup filled; no Slack or MEDDIC side effects |
| T4 | Move that deal Discovery to Contract to Closed Won | Only Why Passport is asked for (plus Dispute Chargeback Fee when the line is a Payments product); no stage-gate or Ironclad prompt |
| T5 | Close won with a 12-month and a 6-month interval, one with a month-end date | Last Increase Date stamped, Next Increase Date rolled by the interval with month-end preserved, Reminder Sent cleared, Status Effective |
| T6 | Set a record's Notice Due inside the window and run the weekly flow | Task to the CS rep with the billing contact, due on Notice Due; one digest email to the configured recipient; Reminder Sent stamped; Status Notice due |
| T7 | Run the weekly flow again | No second task, no second email |
| T8 | A record outside the window, an excluded record, a Skipped record | Untouched |
| T9 | An account with no Contact | Email only, no task, no flow fault |
| T10 | Close a Revenue Enhancement deal won | No Renewal opportunity is created (the renewal flow filters on Type) |
| T11 | Log in as the CS test user, then as a Sales test user | CS creates and edits; Sales reads only; the action is hidden from Sales |
| T12 | Run the two probe scripts against the sandbox | Both succeed and roll back |
| T13 | Deploy dry-run to production | Passes with no Apex tests required |

## Reference

**Documents.**

- Design and feasibility: [Price Lock & Fee Increase Tracking: Options A and B](https://claude.ai/code/artifact/f4dc2ceb-5910-4ac2-8a57-c8cdef746f4d) (Options A and B, side-by-side, the four decisions, and the 2026-10-14 feasibility check with the probe table).
- Org reference: [Passport Salesforce: Process & Data Dictionary](https://claude.ai/code/artifact/0f8a6845-e8d3-4599-afc9-76551b0f053c), Process 3 (opportunity lifecycle and close rules), Process 5 (renewals; the price-increase paragraph to update), Process 6 (Client Success), Automation and Integrations. The same content is in the 44-tab workbook `docs/data-library/Passport_Salesforce_Data_Dictionary_2026-10-19.xlsx` in the repo.

**Files in the ****re****po** (`docs/price-increase/`, committed 2026-10-20 on the branch below):

- `Price_Increase_Automation_Handoff_2026-10-20.md`: a markdown copy of this document as handed off.
- `pricelock_probe.apex` and `pricelock_probe2.apex`: the rollback probes.
- `cecily_price_lock_sheet_2026-10-07.pdf` and `cecily_price_lock_sheet_2026-10-07.txt`: Cecily's sheet as exported on 7 October (all batches, the Ironclad research notes and the methodology page).

**Repo.** `smithbaaron/Passportprod`, branch `claude/brave-noether-f9c9ey`; conventions in `CLAUDE.md`; production login via `scripts/session-setup.sh` and the `SFDX_AUTH_URL` secret; source metadata under `force-app/main/default`.

**What was said to whom.**

- To the VP / Controller (Aaron, 2026-10-16, email): yes, it can be done in Salesforce; all standard configuration, no more than a week to configure; two questions before building in a sandbox (with approval): who enters the increase terms, Punith at close or the CS rep; and should the price-increase deal be created automatically or by a button.
- Cecily's reply (2026-10-16): asked where the terms would be entered and whether that is a new place in Salesforce; deferred Punith versus CS rep to Marcia; on the second question, start with the button and likely move to automated once a few client exceptions can be built in.
- Aaron's reply to Cecily: yes, a new place, a small Price Terms section with price-lock end date, increase percentage, how often it steps up and the next increase date; Punith reads every order form at close so he is the natural person, Marcia's call; the button first, with an "exclude from automatic increases" checkbox and reason built from day one so the later switch is a flow change.
- To Marcia (Slack, plain language): put Cecily's sheet into Salesforce as records on the account with the dates, so reminders and the increase deals come from the system instead of the sheet.

**Org identifiers worth having.** Standing test account in production: Admin Account Test Org `0010f00002KTyDcAAL` (also Test `0016f00002oEF04AAG`). Account CS rep field `Client_Success_Rep_2__c`; Opportunity CS rep field `Client_Success_Rep__c`. Opportunity record type developer names: Standard_Opportunity, Renewal. Renewal flow API name `Auto_Create_Renewal_Opportunity_on_Closed_Wonn` (sic). Task rule `Require_WhoID`. Payments dispute-fee rule `Dispute_Fee_Required_on_Payments_Deals`. Closed-by-CS email flow label "EMAIL ALERT: Notify CS that an RevEn opp has been Closed-By-CS".

**Related but separate.** The Ironclad Contract date backfill (Effective and Expiration dates empty on 3,569 of 3,576 rows on 2026-10-20; keyed export from Ironclad still needed) would let Source Contract be filled properly later. The Renewal Term (months) field on renewal deals is parked and unrelated to this build. Revenue Enhancement Type is blank on most deals; stamping it from this flow is a free data-quality win.
