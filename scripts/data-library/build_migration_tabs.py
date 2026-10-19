#!/usr/bin/env python3
"""Add migration-readiness tabs to the Passport data-library workbook.

Reads the 2026-10-13 workbook (Fields / Objects tabs) plus JSON pulls made on
2026-10-19 and writes a new workbook with these extra tabs:

  Field Disposition   proposed Keep / Review / Retire per field, with reasons
  Object Scope        what moves per object (all, subset, archive, drop)
  Control Totals      record counts and sums to reconcile after a migration
  Keys Crosswalk      external identifiers per system and their coverage
  Account Duplicates  internal duplicate groups found by normalised name + state
  Reports Used 365d   reports that actually ran in the last year
  Cleanup Backlog     prioritised pre-migration cleanup items

Usage: build_migration_tabs.py <in.xlsx> <out.xlsx> <inputs_dir>
inputs_dir holds control_totals.json, account_scan.json, layout_fields.json,
reports_used_365.json, dashboards.json (produced by sf data query runs).
"""
import json, re, sys, os, datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

IN, OUT, D = sys.argv[1], sys.argv[2], sys.argv[3]

def load(name, default=None):
    p = os.path.join(D, name)
    return json.load(open(p)) if os.path.exists(p) else default

ctl = load("control_totals.json", {})
scan = load("account_scan.json", {})
layout_fields = load("layout_fields.json", {})
reports = (load("reports_used_365.json", {}) or {}).get("result", {}).get("records", [])
dashboards = (load("dashboards.json", {}) or {}).get("result", {}).get("records", [])

wb = openpyxl.load_workbook(IN)
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=10)
BODY_FONT = Font(name="Arial", size=10)
WRAP = Alignment(wrap_text=True, vertical="top")

def sheet(title, header, rows, widths=None, wrap_cols=()):
    if title in wb.sheetnames:
        del wb[title]
    ws = wb.create_sheet(title)
    ws.append(header)
    for c in ws[1]:
        c.fill, c.font = HDR_FILL, HDR_FONT
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = BODY_FONT
            if c.column in wrap_cols:
                c.alignment = WRAP
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return ws

def rows_of(name):
    ws = wb[name]
    it = ws.iter_rows(values_only=True)
    hdr = next(it)
    return [dict(zip(hdr, r)) for r in it]

# ---------------------------------------------------------------- owners
def owner_for(obj):
    if obj in ("Capture_Strategy__c", "rfpio__RfpioDetails__c", "rfpio__RfpioIntakeDetails__c"):
        return "Proposal Ops"
    if obj in ("Asset", "At_Risk_Journey__c", "MEDDIC__c", "Implementation_At_Risk_Journey__c",
               "Implementation_Status_Tracker__c"):
        return "Client Success"
    if obj in ("Campaign", "CampaignMember", "Lead"):
        return "Marketing + RevOps"
    if obj in ("Account", "Contact", "Opportunity", "OpportunityLineItem", "Product2", "Case"):
        return "RevOps + Sales"
    return "RevOps"

SYSTEM_FIELDS = {"Id", "IsDeleted", "CreatedDate", "CreatedById", "LastModifiedDate", "LastModifiedById",
                 "SystemModstamp", "LastActivityDate", "LastViewedDate", "LastReferencedDate", "OwnerId",
                 "Name", "RecordTypeId", "MasterRecordId", "CurrencyIsoCode", "PhotoUrl", "Jigsaw",
                 "JigsawCompanyId", "JigsawContactId", "CleanStatus", "IsPartner", "IsCustomerPortal"}

# ---------------------------------------------------------------- field disposition
fields = rows_of("Fields")
disp_rows = []
summary = {}
for f in fields:
    obj, api = f["Object"], f["Field API Name"]
    custom = f["Custom"] == "Yes"
    ns = f["Namespace"]
    refs = {k: (f[k] or 0) for k in ("Flows Ref", "Apex Ref", "VR Ref", "Formula/Rollup Ref", "Workflow FU Ref")}
    nrefs = sum(refs.values())
    fill = f["Fill %"]
    fillpct = None if fill is None else round(float(fill) * 100, 1)
    scope = f["Records In Scope"] or 0
    on_layout = api in set(layout_fields.get(obj, []))
    formula = (f["Formula/Calculated"] == "Yes")
    required = (f["Required"] == "Yes")
    reasons = []
    if nrefs:
        reasons.append("referenced by " + ", ".join(f"{v} {k.replace(' Ref','').lower()}" for k, v in refs.items() if v))
    if on_layout:
        reasons.append("on a core page layout")
    if fillpct is not None:
        reasons.append(f"{fillpct}% filled" + (" (sampled)" if f["Sampled"] == "Yes" else ""))
    elif scope:
        reasons.append("no values found")
    if ns:
        disp = f"Package ({ns})"
        reasons.insert(0, "managed-package field; follows the package decision")
    elif not custom:
        if api in SYSTEM_FIELDS:
            disp = "Standard (system)"
        elif nrefs or on_layout or (fillpct or 0) > 0:
            disp = "Keep (standard)"
        else:
            disp = "Standard, unused"
    else:
        if nrefs or required:
            disp = "Keep"
            if required:
                reasons.insert(0, "required field")
        elif formula:
            disp = "Keep" if on_layout else "Review (formula not on layouts)"
        elif fillpct is None:
            disp = "Review (on layout, empty)" if on_layout else "Retire candidate"
        elif fillpct >= 25:
            disp = "Keep (data)"
        elif fillpct >= 5:
            disp = "Keep (data)" if on_layout else "Review"
        elif fillpct >= 1:
            disp = "Review (low fill)"
        else:
            disp = "Review (on layout, empty)" if on_layout else "Retire candidate"
    summary[disp] = summary.get(disp, 0) + 1
    disp_rows.append([obj, api, f["Label"], f["Type"], "Yes" if custom else "No", ns, fillpct, f["Filled Count"],
                      scope, nrefs, refs["Flows Ref"], refs["VR Ref"], refs["Formula/Rollup Ref"], refs["Apex Ref"],
                      refs["Workflow FU Ref"], "Yes" if on_layout else "", "Yes" if formula else "",
                      "Yes" if required else "", f["History Tracked"], f["Field Created"], disp,
                      "; ".join(reasons), owner_for(obj), "", ""])

order = {"Retire candidate": 0, "Review (on layout, empty)": 1, "Review (low fill)": 2, "Review": 3,
         "Review (formula not on layouts)": 4, "Keep": 5, "Keep (data)": 6, "Keep (standard)": 7,
         "Standard, unused": 8, "Standard (system)": 9}
disp_rows.sort(key=lambda r: (order.get(r[20], 5 if r[20].startswith("Package") else 9), r[0], r[1]))
sheet("Field Disposition",
      ["Object", "Field API Name", "Label", "Type", "Custom", "Namespace", "Fill %", "Filled Count",
       "Records In Scope", "Automation Refs (total)", "Flows", "Validation Rules", "Formulas/Rollups", "Apex",
       "Workflow Field Updates", "On Core Layout", "Formula", "Required", "History Tracked", "Field Created",
       "Proposed Disposition", "Reason", "Suggested Owner", "Decision", "Note"],
      disp_rows,
      widths=[28, 36, 30, 12, 8, 14, 8, 11, 12, 10, 7, 9, 9, 7, 9, 9, 8, 8, 9, 12, 26, 60, 16, 14, 30],
      wrap_cols=(22,))

# ---------------------------------------------------------------- object scope
objs = rows_of("Objects")
EXPLICIT = {
 "Account": ("Migrate subset", "All Current and Former accounts and all partners; Prospects only if created or active in the last 3 years (about 2,500 of 5,824). Merge the 30 internal duplicate groups first."),
 "Contact": ("Migrate subset", "Contacts on migrated accounts; 436 contacts with no account are reviewed, not migrated."),
 "Lead": ("Migrate subset", "Open, MQL, Working and Connected leads (about 3,300) plus leads converted in the last 3 years for attribution; drop older Disqualified and Recycled (about 13,000)."),
 "Opportunity": ("Migrate subset", "All open and all won deals (revenue and renewal chain), lost deals from the last 3 years; decide on the 398 Sales Quota records (quota capture only)."),
 "OpportunityLineItem": ("Migrate with parent", "With their opportunities; 34,800 lines, $848M total price."),
 "OpportunityContactRole": ("Migrate with parent", "12,732 roles; follow the opportunity."),
 "OpportunityTeamMember": ("Migrate with parent", "1,046 rows; re-create for open deals only."),
 "AccountPartner": ("Migrate with parent", "852 partner links; re-create with accounts."),
 "OpportunityPartner": ("Migrate with parent", "Mirror of AccountPartner on deals."),
 "Partner": ("Migrate with parent", "System mirror of partner links."),
 "Asset": ("Migrate all", "Installed base and churn history: Active 2,980, In Implementation 379, Terminated 1,434, Migrated Customer 530, Expired 355."),
 "Product2": ("Migrate subset", "About 180 active products plus any inactive product still referenced by a migrated line or asset."),
 "PricebookEntry": ("Migrate subset", "Entries for migrated products."),
 "Pricebook2": ("Re-create", "2 price books."),
 "Capture_Strategy__c": ("Migrate all", "1,664 bids; the bid history Arrive's team asked about."),
 "Case": ("Migrate subset", "All FOIA Request cases; Solutions Engineering and Change Request cases from the last 3 years; the rest archived."),
 "MEDDIC__c": ("Migrate all", "2,058 records; account-level qualification history."),
 "At_Risk_Journey__c": ("Migrate all", "1,050 journeys; churn history."),
 "Implementation_At_Risk_Journey__c": ("Migrate all", "164 rows."),
 "Implementation_Status_Tracker__c": ("Decide", "5,222 status-tracker rows from workflow field updates since 2019; probably archive, keep last 2 years if implementation reporting needs them."),
 "Case_Status_Tracker__c": ("Archive", "5,068 case status rows; reporting only."),
 "Deal_Desk_Approval__c": ("Archive", "29 rows; approval process obsolete."),
 "Travel_Approval_Request__c": ("Decide", "44 rows; active approval process, low volume."),
 "Case_Study__c": ("Decide", "46 rows; marketing content references."),
 "Campaign_Attendee__c": ("Archive", "35 rows."),
 "GetFeedback_Survey_Responses__c": ("Archive", "269 survey responses; retired tool."),
 "Cities__c": ("Decide", "1,685 reference rows; check what reads it before dropping."),
 "CDI_Client_Data__c": ("Drop", "216 rows from the CDI acquisition; legacy."),
 "Opportunity_Pipeline_Snapshot__c": ("Drop", "1.49M daily snapshot rows since 2023 (about 540k a year); the warehouse holds them. Keep at most the last 12 months if forecasting reports need them."),
 "Campaign": ("Migrate all", "654 campaigns."),
 "CampaignMember": ("Migrate subset", "298,067 members; last 3 years of campaigns."),
 "CampaignInfluence": ("Re-calculate", "160,773 rows; influence is recalculated by the model in the target."),
 "CampaignMemberStatus": ("Migrate with parent", "Status values per campaign."),
 "Task": ("Migrate subset", "1.29M records of which only 207,703 are visible to normal queries; about 1.09M are archived activities older than a year and need an ALL ROWS / archived export. Migrate the last 24 months (about 185,000, 94% written by HubSpot and automatic email capture)."),
 "Event": ("Migrate subset", "18,667 events; last 24 months."),
 "EmailMessage": ("Decide", "244,000 emails (130k in 2025, 84k in 2026), mostly captured by the Gmail integration; migrate last 24 months on migrated records or leave in the warehouse."),
 "EmailMessageRelation": ("Migrate with parent", "Follows EmailMessage."),
 "Attachment": ("Convert", "12,058 legacy Attachments, 13.6 GB; convert to Files for records migrated in the last 3 years, archive the rest to storage."),
 "ContentDocument": ("Migrate subset", "31,500 files and notes; migrate those linked to migrated records."),
 "ContentVersion": ("Migrate with parent", "Latest version only (70,500 versions on 31,500 documents)."),
 "ContentDocumentLink": ("Migrate with parent", "Re-created with the files."),
 "ContentNote": ("Migrate with parent", "Enhanced notes; follow their records."),
 "Note": ("Convert", "3,096 classic notes; convert to ContentNote on migrated records."),
 "Document": ("Decide", "7,069 classic Documents (email images, logos); mostly legacy."),
 "OpportunityHistory": ("Export to warehouse", "107,276 stage-history rows cannot be inserted into a target org; funnel and win-rate reports depend on them. Confirm Fivetran covers the object, else export before cutover."),
 "OpportunityFieldHistory": ("Export to warehouse", "26,630 rows; cannot be migrated."),
 "AccountHistory": ("Export to warehouse", "26,996 rows; cannot be migrated."),
 "ContactHistory": ("Export to warehouse", "31,312 rows; cannot be migrated."),
 "LeadHistory": ("Export to warehouse", "10,509 rows; cannot be migrated."),
 "AssetHistory": ("Export to warehouse", "7,391 rows; cannot be migrated."),
 "CaseHistory2": ("Export to warehouse", "19,900 rows; cannot be migrated."),
 "Opportunity__hd": ("Export to warehouse", "Historical trending snapshots; cannot be migrated."),
 "ForecastingItem__hd": ("Export to warehouse", "Forecast trending; cannot be migrated."),
 "FeedItem": ("Not migrated", "100,900 Chatter posts; export if legal hold needs them."),
 "FeedComment": ("Not migrated", "Chatter comments."),
 "FeedTrackedChange": ("Not migrated", "Feed tracking of field changes."),
 "ironclad__Ironclad_Workflow__c": ("Migrate all", "2,329 workflow records keep the deal-to-contract link; whether Ironclad can re-push them into another org is to be confirmed with the Ironclad administrator."),
 "ironclad__Ironclad_Contract__c": ("Migrate after backfill", "3,573 repository rows; load Ironclad IDs and dates first, then migrate or let Ironclad re-push."),
 "ironclad__Ironclad_Approval__c": ("Re-sync", "9,007 rows; Ironclad re-pushes."),
 "ironclad__Ironclad_Signature__c": ("Re-sync", "4,638 rows; Ironclad re-pushes."),
 "ironclad__Workflow_View_Timestamp__c": ("Drop", "Package housekeeping."),
 "ironclad__Error_Log__c": ("Drop", "Package log."),
 "netsuite_conn__NetSuite_Financial__c": ("Re-sync", "5,324 rows written by Celigo; re-sync from NetSuite."),
 "User": ("Re-create", "545 users, 98 active. Active users are re-created; records owned by the 379 inactive users (10,817 opportunities, 10,792 contacts) are reassigned before extraction."),
 "rfpio__RfpioDetails__c": ("Drop", "Responsive (RFPIO) is retired; 37 rows."),
 "rfpio__RfpioIntakeDetails__c": ("Drop", "Responsive intake, replaced by Bid Intake; 150 rows."),
}
PACKAGE_NOTE = {"rh2": "Rollup Helper configuration; re-create rollups in the target",
                "dlrs": "DLRS rollup definitions and logs; re-create",
                "sonar": "Field Spy analysis data; admin tool, no migration",
                "fpro": "FieldPro usage data; admin tool, no migration",
                "Field_Trip": "Field Trip analysis; admin tool, no migration",
                "Gong": "Gong writes these; re-sync",
                "OIQ": "Sales Insights; re-sync or drop",
                "integrator_da": "Celigo connection settings; reconfigure",
                "netsuite_conn": "NetSuite connector settings; reconfigure",
                "Helpshift": "retired support tool; drop",
                "freshdesk": "retired; drop",
                "HubSpot_Inc": "HubSpot package objects; reinstall",
                "relateiq": "SalesforceIQ; retired",
                "ironclad": "Ironclad; re-sync"}
scope_rows = []
scope_summary = {}
for o in objs:
    api = o["Object API Name"]; n = o["Record Count"] or 0; ns = o["Namespace"]
    if api in EXPLICIT:
        scope, why = EXPLICIT[api]
    elif ns and ns != "standard":
        scope, why = "Package data", PACKAGE_NOTE.get(ns, f"{ns} package object; reinstall the package, do not migrate rows")
    elif ns == "standard":
        if re.search(r"History|__hd$", api):
            scope, why = "Export to warehouse", "History objects cannot be inserted into a target org."
        else:
            scope, why = "Platform / configuration", "Metadata, usage metrics, permissions or feed data; re-created by configuration in the target, not migrated as records."
    else:
        scope, why = "Decide", f"Own custom object with {n:,} rows; not yet assessed."
    scope_summary[scope] = scope_summary.get(scope, 0) + 1
    scope_rows.append([api, o["Label"], ns, n, o["Active Record-Triggered Flows"], o["Active Workflow Rules"],
                       o["Active VRs"], o["History Tracking"], scope, why, "", ""])
sorder = {"Migrate all": 0, "Migrate subset": 1, "Migrate with parent": 2, "Migrate after backfill": 3, "Convert": 4,
          "Re-create": 5, "Re-sync": 6, "Re-calculate": 7, "Decide": 8, "Archive": 9, "Export to warehouse": 10,
          "Drop": 11, "Not migrated": 12, "Package data": 13, "Platform / configuration": 14}
scope_rows.sort(key=lambda r: (sorder.get(r[8], 8), -(r[3] or 0)))
sheet("Object Scope",
      ["Object API Name", "Label", "Namespace", "Record Count", "Active Flows", "Active Workflow Rules", "Active VRs",
       "History Tracking", "Proposed Scope", "Rationale", "Decision", "Owner"],
      scope_rows, widths=[40, 30, 14, 13, 8, 10, 8, 9, 22, 90, 14, 16], wrap_cols=(10,))

# ---------------------------------------------------------------- control totals
ct_rows = []
def add(area, measure, dim, count, amount=None, query=""):
    ct_rows.append([area, measure, dim, count, amount, query, datetime.date.today().isoformat()])
for r in ctl.get("accounts_by_status_type", []):
    add("Account", "Accounts by Status and Type", f"{r['s']} / {r['t']}", r["n"], None, "SELECT Status__c, Type, COUNT(Id) FROM Account GROUP BY Status__c, Type")
for r in ctl.get("contacts_by_account_status", []):
    add("Contact", "Contacts by account status", str(r["s"]), r["n"], None, "SELECT Account.Status__c, COUNT(Id) FROM Contact GROUP BY Account.Status__c")
for r in ctl.get("leads_by_status", []):
    add("Lead", "Leads by Status", f"{r['s']} (converted={r['c']})", r["n"], None, "SELECT Status, IsConverted, COUNT(Id) FROM Lead GROUP BY Status, IsConverted")
for r in ctl.get("opps_by_year_state", []):
    add("Opportunity", "Opportunities by close year", f"{r['y']} / {'won' if r['w'] else ('lost' if r['c'] else 'open')}", r["n"], round(r["amt"] or 0, 2), "SELECT CALENDAR_YEAR(CloseDate), IsClosed, IsWon, COUNT(Id), SUM(Amount) FROM Opportunity GROUP BY CALENDAR_YEAR(CloseDate), IsClosed, IsWon")
for r in ctl.get("opps_by_rt", []):
    add("Opportunity", "Opportunities by record type", r["r"], r["n"], None, "SELECT RecordType.DeveloperName, COUNT(Id) FROM Opportunity GROUP BY RecordType.DeveloperName")
for r in ctl.get("oli_total", []):
    add("Opportunity Product", "Lines and total price", "all", r["n"], round(r["amt"] or 0, 2), "SELECT COUNT(Id), SUM(TotalPrice) FROM OpportunityLineItem")
for r in ctl.get("assets_by_status", []):
    add("Asset", "Assets by Status", str(r["s"]), r["n"], None, "SELECT Status, COUNT(Id) FROM Asset GROUP BY Status")
for r in ctl.get("capstrat_by_stage", []):
    add("Capture Strategy", "Bids by stage", str(r["s"]), r["n"], None, "SELECT CapStrat_Stage__c, COUNT(Id) FROM Capture_Strategy__c GROUP BY CapStrat_Stage__c")
for r in ctl.get("cases_by_rt", []):
    add("Case", "Cases by record type", f"{r['r']} (closed={r['c']})", r["n"], None, "SELECT RecordType.DeveloperName, IsClosed, COUNT(Id) FROM Case GROUP BY RecordType.DeveloperName, IsClosed")
for r in ctl.get("meddic_by_rt", []):
    add("MEDDIC", "MEDDIC by record type", r["r"], r["n"], None, "SELECT RecordType.DeveloperName, COUNT(Id) FROM MEDDIC__c GROUP BY RecordType.DeveloperName")
for r in ctl.get("arj_open", []):
    add("At-Risk Journey", "Journeys open / closed", "open" if r["o"] else "closed", r["n"], None, "SELECT At_Risk_Journey_is_Open__c, COUNT(Id) FROM At_Risk_Journey__c GROUP BY At_Risk_Journey_is_Open__c")
for r in ctl.get("revenue_current", []):
    add("Account", "NetSuite revenue on current customers", "sum Recurring NS / NS Revenue", r["n"], f"{round(r['rec'] or 0):,} / {round(r['ns'] or 0):,}", "SELECT SUM(Recurring_NS__c), SUM(NS_Revenue__c), COUNT(Id) FROM Account WHERE Status__c = 'Current' AND Type = 'Customer'")
for key, label, q in (("tasks_by_year", "Tasks by created year (visible, non-archived)", "SELECT CALENDAR_YEAR(CreatedDate), COUNT(Id) FROM Task GROUP BY CALENDAR_YEAR(CreatedDate)"),
                      ("events_by_year", "Events by created year", "SELECT CALENDAR_YEAR(CreatedDate), COUNT(Id) FROM Event GROUP BY CALENDAR_YEAR(CreatedDate)"),
                      ("emails_by_year", "Email messages by year", "SELECT CALENDAR_YEAR(CreatedDate), COUNT(Id) FROM EmailMessage GROUP BY CALENDAR_YEAR(CreatedDate)"),
                      ("leads_by_year", "Leads by created year", "SELECT CALENDAR_YEAR(CreatedDate), COUNT(Id) FROM Lead GROUP BY CALENDAR_YEAR(CreatedDate)"),
                      ("pipeline_snapshot_years", "Pipeline snapshots by year", "SELECT CALENDAR_YEAR(CreatedDate), COUNT(Id) FROM Opportunity_Pipeline_Snapshot__c GROUP BY CALENDAR_YEAR(CreatedDate)"),
                      ("impl_tracker_years", "Implementation status tracker rows by year", "SELECT CALENDAR_YEAR(CreatedDate), COUNT(Id) FROM Implementation_Status_Tracker__c GROUP BY CALENDAR_YEAR(CreatedDate)")):
    for r in ctl.get(key, []):
        add("Activity / volume", label, str(r["y"]), r["n"], None, q)
for key, label, q in (("attachments", "Attachments (count, bytes)", "SELECT COUNT(Id), SUM(BodyLength) FROM Attachment"),
                      ("files", "Files, latest versions (count, bytes)", "SELECT COUNT(Id), SUM(ContentSize) FROM ContentVersion WHERE IsLatest = true"),
                      ("notes", "Classic notes", "SELECT COUNT(Id) FROM Note"),
                      ("campaign_members", "Campaign members", "SELECT COUNT(Id) FROM CampaignMember"),
                      ("ocr", "Opportunity contact roles", "SELECT COUNT(Id) FROM OpportunityContactRole"),
                      ("cities", "Cities reference rows", "SELECT COUNT(Id) FROM Cities__c")):
    for r in ctl.get(key, []):
        add("Files / misc", label, "all", r["n"], r.get("b"), q)
for key, label in (("opp_history", "OpportunityHistory"), ("opp_field_history", "OpportunityFieldHistory"), ("account_history", "AccountHistory"),
                   ("contact_history", "ContactHistory"), ("lead_history", "LeadHistory"), ("asset_history", "AssetHistory")):
    for r in ctl.get(key, []):
        add("History (cannot be migrated)", label, "rows", r["n"], None, f"SELECT COUNT(Id) FROM {label}")
for key, label, q in (("opp_owner_inactive", "Opportunities by owner active flag", "SELECT Owner.IsActive, COUNT(Id) FROM Opportunity GROUP BY Owner.IsActive"),
                      ("contact_owner_inactive", "Contacts by owner active flag", "SELECT Owner.IsActive, COUNT(Id) FROM Contact GROUP BY Owner.IsActive")):
    for r in ctl.get(key, []):
        add("Ownership", label, "active owner" if r["a"] else "INACTIVE owner", r["n"], None, q)
sheet("Control Totals", ["Area", "Measure", "Dimension", "Count", "Amount / Bytes", "SOQL", "As Of"], ct_rows,
      widths=[22, 40, 34, 12, 20, 90, 11])

# ---------------------------------------------------------------- keys crosswalk
cov = scan.get("coverage", {})
def c(st, k):
    v = cov.get(st, {})
    return f"{v.get(k, 0):,} / {v.get('n', 0):,}" if v else ""
keys = [
 ["NetSuite", "Account", "netsuite_conn__NetSuite_Id__c", "Yes", "Yes", c("Current", "NetSuite"), c("Former", "NetSuite"), c("Prospect", "NetSuite"), "Customer identity for billing and revenue; one NetSuite customer per Account. Primary key for matching financial data; Arrive runs a different ERP so this does not match their accounts."],
 ["NetSuite", "Contact", "netsuite_conn__NetSuite_Id__c", "Yes", "Yes", "", "", "", "Billing contacts pushed to NetSuite."],
 ["NetSuite", "Product2", "netsuite_conn__NetSuite_Id__c", "Yes", "Yes", "", "", "", "Item identity; maps products to NetSuite items and classes (= product family)."],
 ["NetSuite", "Asset / Opportunity Product", "netsuite_conn__NetSuite_Item_Key_Id__c, NetSuite_Item_Id_Import__c", "Yes (key)", "No", "", "", "", "Item key on assets and lines."],
 ["NetSuite", "Opportunity", "netsuite_conn__Current_Sales_Order_Id__c, Current_Opportunity_Id__c, NetSuite_Project_Id__c", "Yes", "Yes", "", "", "", "Sales order and project IDs stamped by Celigo on closed-won deals."],
 ["HubSpot", "Account", "Hubspot_Account_Id__c", "Yes", "No", c("Current", "HubSpot"), c("Former", "HubSpot"), c("Prospect", "HubSpot"), "HubSpot company ID; filled on every account by the HubSpot sync. Both companies run HubSpot, so this is the one shared system key, but the two portals have different IDs."],
 ["HubSpot", "Contact / Lead", "HubSpot_Score__c, HubSpot_Original_Source__c, HubSpot_Lifecycle_Stage__c, drill-downs", "No", "No", "", "", "", "Attributes only; the HubSpot record ID is held in HubSpot's own sync mapping, not in a Salesforce field."],
 ["Passport (internal)", "Account", "Passport_ID__c", "Yes", "No", c("Current", "PassportID"), c("Former", "PassportID"), c("Prospect", "PassportID"), "Auto-number on every account; Passport's own stable account key."],
 ["Passport OpsMan", "Account", "Operator_ID__c, Parent_Operator_ID__c", "Yes", "No", c("Current", "Operator"), c("Former", "Operator"), c("Prospect", "Operator"), "Operator ID in Passport's operations platform (OpsMan); the link from a CRM account to the live client configuration."],
 ["Intercom", "Account", "Intercom_Company_ID__c", "No", "Yes", c("Current", "Intercom"), c("Former", "Intercom"), c("Prospect", "Intercom"), "Intercom company ID. The Account push to Intercom uses the Salesforce ID as the external key on the Intercom side, so this field is almost empty; recover from Intercom if needed."],
 ["Pursuit", "Account / Contact", "pursuit_id__c", "Yes", "Yes", c("Current", "Pursuit"), c("Former", "Pursuit"), c("Prospect", "Pursuit"), "Account scoring vendor's ID; prospects mostly."],
 ["Ironclad", "Ironclad Workflow", "ironclad__Workflow_ID__c", "Yes", "Yes", "2,329 rows", "", "", "Contract workflow ID; the only live contract key. Ironclad Contract rows have no Ironclad ID (backfill planned)."],
 ["Gong", "Account / Opportunity / Contact", "Gong__Gong_Count__c and Engage fields", "No", "No", "", "", "", "Activity counts only; Gong keys its own records to the Salesforce ID."],
 ["Legacy: Freshdesk", "Account / Contact", "FDACCOUNTID__c, FDCONTACTID__c", "Yes", "No", "", "", "", "Retired support desk; drop."],
 ["Legacy: Base CRM", "Lead", "Base_Entity_ID__c, Base_Opportunity_ID__c, Base_Contact_ID__c", "Yes", "No", "", "", "", "IDs from the 2014 CRM migration; drop."],
 ["Legacy: CDI / NuPark acquisitions", "Account / Contact / Opportunity / Product2", "NuPark_Account_ID__c, NuPark_Opp_ID__c, CDI_SFDC_Contact_Id__c, CDI_SFDC_Opp_Id__c, CDI_SFDC_Product2_Id__c, Contact_Migration_ID__c", "No", "No", "", "", "", "Keys from Passport's two earlier acquisitions; the precedent for how a merged org keeps source IDs. Keep as read-only history or drop."],
 ["Web / ads", "Lead / Contact / Opportunity", "GCLID__c, UnbouncePageID__c", "No", "No", "", "", "", "Google click IDs for ad attribution."],
 ["Portal", "Contact", "Portal_User_ID__c", "Yes", "No", "", "", "", "Client portal user ID."],
 ["Proposed merge match key", "Account", "normalised agency name + billing state + country (+ website domain)", "n/a", "n/a", c("Current", "BillingState"), c("Former", "BillingState"), c("Prospect", "BillingState"), "No shared system key exists between Passport and Arrive. Name + state + country is filled on nearly every account; website is on about 80% of customers. Run the same normalisation on both sides and review matches by hand for customers."],
 ["Proposed merge match key", "Contact", "email address", "n/a", "n/a", "", "", "", "Standard; HubSpot already de-duplicates on it."],
 ["Proposed merge match key", "Product", "product family + name", "n/a", "n/a", "", "", "", "Map Arrive SKUs to Passport families (Parking, Enforcement, Permits, Payments, Equipment/Svcs, Platform) before line-level mapping."],
]
sheet("Keys Crosswalk", ["System", "Object", "Field(s)", "External Id", "Unique", "Coverage: Current (filled / total)", "Coverage: Former", "Coverage: Prospect", "Role in a merge"],
      keys, widths=[24, 26, 48, 10, 8, 20, 18, 18, 90], wrap_cols=(3, 9))

# ---------------------------------------------------------------- account duplicates
dup_rows = []
for i, grp in enumerate(scan.get("dups_current", []), 1):
    for a in grp:
        dup_rows.append([i, a["Name"], a["Id"], a["Status"], a["Type"], a["RT"], a["State"], "Yes" if a["NS"] else "", "", ""])
hdr_note = [["", f"Scan of {scan.get('coverage', {}).get('Current', {}).get('n', 0) + scan.get('coverage', {}).get('Former', {}).get('n', 0) + scan.get('coverage', {}).get('Prospect', {}).get('n', 0):,} accounts by normalised name + billing state: {scan.get('dup_groups_name_state', 0)} groups / {scan.get('dup_accounts_name_state', 0)} accounts; {scan.get('dup_groups_with_current', 0)} groups include a Current customer (listed below). Exact-name duplicates: {scan.get('exact_name_groups', 0)}. Some groups are legitimately separate entities (Town vs Village, City vs County); review, do not auto-merge.", "", "", "", "", "", "", "", ""]]
sheet("Account Duplicates", ["Group", "Account Name", "Id", "Status", "Type", "Record Type", "Billing State", "Has NetSuite Id", "Decision", "Note"],
      hdr_note + dup_rows, widths=[7, 44, 20, 10, 18, 18, 16, 12, 14, 30], wrap_cols=(2,))

# ---------------------------------------------------------------- reports used
rep_rows = [[r["Name"], r["FolderName"], r["Format"], (r.get("LastRunDate") or "")[:10], (r.get("LastModifiedDate") or "")[:10],
             (r.get("CreatedDate") or "")[:10], (r.get("Owner") or {}).get("Name"), (r.get("LastModifiedBy") or {}).get("Name"), r["Id"]] for r in reports]
rep_rows.sort(key=lambda r: (r[1] or "", r[0] or ""))
sheet("Reports Used 365d", ["Report", "Folder", "Format", "Last Run", "Last Modified", "Created", "Owner", "Last Modified By", "Id"],
      rep_rows, widths=[50, 34, 10, 11, 12, 11, 22, 22, 20])
ws = wb["Reports Used 365d"]
ws.insert_rows(1)
ws["A1"] = "2,935 reports in the org: 855 ran in the last 365 days (listed), 474 in the last 90 days, 1,973 last ran more than a year ago, 107 never ran. 64 dashboards (see Reports UI tab). 248 email templates, 1 used in the last year."
ws["A1"].font = Font(name="Arial", italic=True, size=10)
ws.freeze_panes = "A3"

# ---------------------------------------------------------------- cleanup backlog
backlog = [
 ["Procurement Method backfill on won deals (752 of 805 wins blank)", "Proposal Ops / Marcia", "M", "High", "Yes", "In progress", "Needed for cooperative-contract counts and the RFP vs direct comparison with Arrive."],
 ["Reassign records owned by 379 inactive users (10,817 opps, 10,792 contacts)", "RevOps", "M", "High", "Yes", "Not started", "Ownership must land on active users or an integration user before extraction."],
 ["Move 312 open deals out of retired stages (Scoping/Proposal, Not Started)", "RevOps + CS", "S", "Medium", "Yes", "Not started", "Gates do not apply in retired stages; stage mapping breaks on them."],
 ["Field retirement pass on the Retire candidates in the Field Disposition tab", "RevOps", "L", "High", "Yes", "Not started", "Fewer fields to map; confirm with owners, then remove from layouts first, delete after 90 days."],
 ["Picklist cleanup: 270 values in data but undefined; CapStrat Stage 24 values, 8 in use", "RevOps + Proposal Ops", "M", "Medium", "Yes", "Not started", "Value crosswalk is simpler with a clean source list."],
 ["Account duplicate review (30 groups, 8 with current customers)", "RevOps + CS", "S", "Medium", "Yes", "Not started", "See Account Duplicates tab; some are legitimate separate entities."],
 ["Archive stale prospects (3,294 with no activity, created more than 3 years ago)", "Sales + Marketing", "S", "Medium", "Yes", "Not started", "Reduces the account match workload by half."],
 ["Lead cleanup: about 13,000 Disqualified / Recycled leads older than 3 years", "Marketing", "S", "Low", "Yes", "Not started", "HubSpot remains the system of record for them."],
 ["Attachments to Files (12,058 legacy attachments, 13.6 GB)", "RevOps + IT", "M", "Medium", "Yes", "Not started", "Attachments are not supported in Lightning migrations; convert for recent records, archive the rest."],
 ["Pipeline snapshot retention (1.49M rows, 540k a year)", "RevOps", "S", "Low", "Yes", "Not started", "Confirm the warehouse copy, then purge older than 12 months."],
 ["Confirm Fivetran covers every history object; export the gaps before cutover", "Data / RevOps", "S", "High", "Yes", "Not started", "OpportunityHistory (107k rows) drives all funnel reporting and cannot be migrated."],
 ["Remove hard-coded IDs and named recipients (13 validation rules, 14 flows)", "RevOps", "M", "Medium", "Yes", "Not started", "Replace with custom permissions, public groups or custom metadata."],
 ["Uninstall retired packages (Helpshift, Freshdesk, Responsive, SalesforceIQ, Periscope)", "RevOps", "M", "Medium", "Yes", "Not started", "Removes their fields from the mapping; check for reports built on package fields first."],
 ["Report cleanup: archive 1,973 stale and 107 never-run reports; keep the 855 used", "RevOps", "S", "Low", "Yes", "Not started", "Migrate about 150 to 300 reports, not 2,900."],
 ["Churn date and reason on 394 legacy Former accounts", "Client Success", "M", "Medium", "No", "Not started", "Retention reporting; not a migration blocker."],
 ["Ironclad Contract ID and date backfill, then re-link hand-made rows", "RevOps / Proposal Ops", "L", "Medium", "No", "Blocked", "Needs Ironclad admin access and a keyed export."],
 ["Renewal Term (months) on the renewal deal and in the renewal flow", "RevOps + CS", "S", "Medium", "No", "Parked", "Replaces the 12-month assumption."],
 ["Asset contract date hygiene (end dates not advanced on auto-renewals)", "Client Success / Marcia", "M", "Medium", "No", "Not started", "Renewal Date formula covers it for now."],
 ["Celigo connection to OAuth; Use Any API Auth for the integration user", "RevOps / Finance systems", "S", "High", "No", "Not started", "Salesforce deadline (Winter '27 permission, Summer '27 SOAP retirement), independent of the merge."],
 ["Email template cleanup (248 templates, 1 used in the last year)", "RevOps", "S", "Low", "No", "Not started", "Keep the closed-won and FOIA templates; archive the rest."],
 ["Revenue Enhancement Type blank on 164 of 175 recent Revenue Enhancement deals", "Client Success + RevOps", "S", "Low", "No", "Not started", "The picklist already carries CMP Fee Increase, MPP Fee Increase, Termination Fee and USPS; the price-increase work can reuse it instead of adding a field."],
]
sheet("Cleanup Backlog", ["Item", "Owner", "Effort (S/M/L)", "Impact", "Blocks Migration", "Status", "Note"],
      backlog, widths=[70, 24, 10, 10, 12, 14, 70], wrap_cols=(1, 7))

# ---------------------------------------------------------------- read me note
rm = wb["Read Me"]
rm.append([])
rm.append([f"Migration-readiness tabs added {datetime.date.today().isoformat()}: Field Disposition, Object Scope, Control Totals, Keys Crosswalk, Account Duplicates, Reports Used 365d, Cleanup Backlog. Dispositions and scopes are proposals from rules (automation references, fill rate, layout presence); the Decision columns are for owners to fill."])
rm.append(["Field Disposition summary: " + "; ".join(f"{k}: {v}" for k, v in sorted(summary.items(), key=lambda kv: -kv[1]))])
rm.append(["Object Scope summary: " + "; ".join(f"{k}: {v}" for k, v in sorted(scope_summary.items(), key=lambda kv: -kv[1]))])

wb.save(OUT)
print("saved", OUT)
print("field disposition:", summary)
print("object scope:", scope_summary)
