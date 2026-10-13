#!/usr/bin/env python3
"""Build the Passport prod Salesforce data library workbook from the scratchpad pulls."""
import json, os, re, glob, collections, datetime, sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

D = "/tmp/claude-0/-home-user-Passportprod/6492453e-d707-5a6e-b62e-7229034b9640/scratchpad/datalib"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{D}/Passport_Prod_Data_Library.xlsx"
ASOF = "2026-10-13"
FONT = "Arial"

def J(name, key="records"):
    p = f"{D}/raw/{name}.json"
    if not os.path.exists(p): return []
    d = json.load(open(p))
    r = d.get("result", {})
    return r.get(key, []) if isinstance(r, dict) else r

def DQ(name):
    p = f"{D}/dq/{name}.json"
    if not os.path.exists(p): return []
    return json.load(open(p)).get("result", {}).get("records", []) or []

counts = json.load(open(f"{D}/raw/record_counts.json"))
meta = json.load(open(f"{D}/raw/object_metadata.json"))
flows_meta = json.load(open(f"{D}/raw/flow_metadata.json"))
wf_meta = json.load(open(f"{D}/raw/workflow_metadata.json"))
sharing = json.load(open(f"{D}/raw/sharing_rules.json"))
refs = json.load(open(f"{D}/raw/field_refs.json"))
settings = json.load(open(f"{D}/raw/settings.json"))
profile_objs = json.load(open(f"{D}/raw/profile_objects.json"))
describes = {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(f"{D}/describe/*.json")}
profiles = {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(f"{D}/profile/*.json")}
entity = {e["QualifiedApiName"]: e for e in J("entity_defs")}
custom_objects = {c["DeveloperName"] + "__c" if not c.get("NamespacePrefix") else f"{c['NamespacePrefix']}__{c['DeveloperName']}__c": c for c in J("custom_objects")}
custom_fields = {}
for c in J("custom_fields"):
    custom_fields[(c["TableEnumOrId"], (c["NamespacePrefix"] + "__" if c.get("NamespacePrefix") else "") + c["DeveloperName"] + "__c")] = c
fdv = {f["ApiName"]: f for f in J("flows")}
org = (J("org") or [{}])[0]
limits = {l["name"]: l for l in J("limits", key=None) or []} if os.path.exists(f"{D}/raw/limits.json") else {}
if not limits:
    try: limits = {l["name"]: l for l in json.load(open(f"{D}/raw/limits.json"))["result"]}
    except Exception: limits = {}

# ---------- styling helpers ----------
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
BODY_FONT = Font(name=FONT, size=10)
TITLE_FONT = Font(name=FONT, bold=True, size=14)
NOTE_FONT = Font(name=FONT, italic=True, size=9, color="555555")
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")

def write_table(ws, headers, rows, start_row=1, widths=None, wrap_cols=(), name=None, number_formats=None):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=start_row, column=j, value=h); c.font = HDR_FONT; c.fill = HDR_FILL; c.alignment = Alignment(vertical="center", wrap_text=True)
    for i, r in enumerate(rows, start_row + 1):
        for j, v in enumerate(r, 1):
            if isinstance(v, (list, tuple, set, dict)): v = json.dumps(v, default=str) if isinstance(v, dict) else "; ".join(str(x) for x in v)
            if isinstance(v, str) and len(v) > 32000: v = v[:32000] + "…"
            c = ws.cell(row=i, column=j, value=v); c.font = BODY_FONT
            c.alignment = WRAP if (j - 1) in wrap_cols else TOP
            if number_formats and headers[j - 1] in number_formats: c.number_format = number_formats[headers[j - 1]]
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    last = get_column_letter(len(headers))
    if rows:
        ws.auto_filter.ref = f"A{start_row}:{last}{start_row + len(rows)}"
    for j, h in enumerate(headers, 1):
        w = (widths or {}).get(h)
        if w is None:
            sample = [len(str(r[j - 1])) for r in rows[:300] if j - 1 < len(r) and r[j - 1] is not None]
            w = min(max([len(h)] + sample) + 2, 60) if sample else len(h) + 2
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[start_row].height = 30
    return start_row + len(rows) + 1

def kv_block(ws, title, pairs, row, note=None):
    ws.cell(row=row, column=1, value=title).font = Font(name=FONT, bold=True, size=11); row += 1
    if note:
        ws.cell(row=row, column=1, value=note).font = NOTE_FONT; row += 1
    for k, v in pairs:
        ws.cell(row=row, column=1, value=k).font = Font(name=FONT, size=10, bold=True)
        c = ws.cell(row=row, column=2, value=v); c.font = BODY_FONT; c.alignment = WRAP
        row += 1
    return row + 1

def pct(a, b):
    return round(a / b, 4) if (a is not None and b) else None

def ns_of(api):
    parts = api.split("__")
    return parts[0] if len(parts) == 3 else None

wb = Workbook()

# ================= Read Me =================
ws = wb.active; ws.title = "Read Me"
ws.column_dimensions["A"].width = 28; ws.column_dimensions["B"].width = 110
ws["A1"] = "Passport Labs - Production Salesforce Org Data Library"; ws["A1"].font = TITLE_FONT
ws["A2"] = f"As of {ASOF} | Org passportlabs.my.salesforce.com | Built from the Metadata, Tooling, REST and SOQL APIs"; ws["A2"].font = NOTE_FONT
row = 4
row = kv_block(ws, "Purpose", [("What this is", "A field-level inventory of the production org (schema, data volumes, fill rates, picklist usage, automation, integrations, users and sharing) prepared for a potential merge of two acquired companies' orgs into this one."),
    ("How to use it", "Start at Org Summary, then Objects. The Fields tab is the mapping worksheet: filter by Object, sort by Fill % to see which fields carry data, and read the Referenced By columns before changing or retiring a field. Picklist Values shows defined vs actually used values. Merge Considerations lists the risks the data surfaced.")], row)
row = kv_block(ws, "Tabs", [
    ("Org Summary", "Edition, limits, storage, feature flags, headline counts."),
    ("Objects", "One row per object that holds records (336), with sharing model, record types, automation and field counts. Profiled = field-level stats were collected."),
    ("Fields", "One row per field on the 98 profiled objects (standard + custom), with type, picklist definition, fill rate, boolean true rate, distinct values in use, and every flow / Apex / validation rule / formula / workflow that references it."),
    ("Picklist Values", "Every defined picklist value (active or inactive) with the number of records using it, plus values found in data that are no longer defined."),
    ("Record Types", "Record types per object with business process and which picklist values they expose."),
    ("Validation Rules", "All validation rules with formula, message and the custom fields they touch."),
    ("Flows", "Every flow definition (own and managed) with trigger object, status, version and the custom fields, emails and hard-coded Ids inside it."),
    ("Workflows Triggers Approvals", "Classic workflow rules and their actions, Apex triggers, approval processes, duplicate and assignment rules."),
    ("Scheduled Jobs", "Apex and flow schedules currently queued."),
    ("Integrations", "Installed packages, connected apps with 90-day login counts, named credentials, remote sites, auth providers."),
    ("Users Access", "Active users, profiles, roles, permission sets, licenses, queues, org-wide defaults and sharing rules."),
    ("Data Volumes", "Record counts for every object with data, growth by year for the core objects, storage."),
    ("Data Quality", "Distribution and hygiene checks on Accounts, Contacts, Leads, Opportunities, Assets, Cases, Campaigns, Activities."),
    ("Reports UI", "Reports by folder and last run, dashboards, list views, email templates, apps, Lightning pages, custom code counts."),
    ("Merge Considerations", "Findings that affect an org merge, each with the evidence count and where to look.")], row)
row = kv_block(ws, "Caveats", [
    ("Record counts", "From the recordCount API (approximate for very large objects) and SOQL COUNT for profiled objects. Fill % and True % are computed at build time from the two count columns beside them; the workbook has no live formulas."),
    ("Sampled objects", "Objects over 400,000 rows (Task, Opportunity Pipeline Snapshot) were profiled on the last 365 days of records only; the Fields tab marks them Sampled = Yes."),
    ("Long text", "Long text area and rich text fields cannot be counted by SOQL; their Fill % is blank. Address and geolocation compound fields are blank too (their component fields are counted)."),
    ("Picklist usage", "Collected for objects up to 300,000 rows; top 60 values per field. State/country code, locale, language, time zone and currency picklists are left off the Picklist Values tab because they are platform lists."),
    ("Managed packages", "Fields and objects with a namespace prefix belong to an installed package and cannot be changed here; they are included so the merge team can see what the packages hold."),
    ("Knowledge", "Knowledge article objects (FAQ__kav) were not retrievable with the API user's permissions and are excluded.")], row)

# ================= Org Summary =================
ws = wb.create_sheet("Org Summary")
ws.column_dimensions["A"].width = 46; ws.column_dimensions["B"].width = 70
ws["A1"] = "Org Summary"; ws["A1"].font = TITLE_FONT
row = 3
lic = J("user_licenses"); users_active = J("users_active")
def pname(u): return (u.get("Profile") or {}).get("Name")
def plic(u): return ((u.get("Profile") or {}).get("UserLicense") or {}).get("Name")
active_by_lic = collections.Counter(plic(u) for u in users_active)
own_objs = [o for o in meta if o.endswith("__c") and o.count("__") == 1]
managed_objs = [o for o in meta if o.endswith("__c") and o.count("__") == 2]
all_fields = [(o, f) for o, m in meta.items() for f in m["fields"]]
own_fields = [x for x in all_fields if x[1].count("__") == 1]
flows_all = J("flows")
row = kv_block(ws, "Organization", [
    ("Name", org.get("Name")), ("Edition / type", org.get("OrganizationType")), ("Instance", org.get("InstanceName")),
    ("Sandbox", org.get("IsSandbox")), ("Org created", (org.get("CreatedDate") or "")[:10]),
    ("Default locale / language / time zone", f"{org.get('DefaultLocaleSidKey')} / {org.get('LanguageLocaleKey')} / {org.get('TimeZoneSidKey')}"),
    ("Fiscal year start month", org.get("FiscalYearStartMonth")),
    ("Multi-currency", settings["summary"].get("Currency", {}).get("enableMultiCurrency")),
    ("State/Country picklists", "Enabled" if settings["summary"].get("Address") else "Not detected"),
    ("Territory Management 2.0", settings["summary"].get("Territory2", {}).get("enableTerritoryManagement2")),
    ("Account teams / Opportunity teams", f"{settings['summary'].get('Account', {}).get('enableAccountTeams')} / {settings['summary'].get('Opportunity', {}).get('enableOpportunityTeam')}"),
    ("Forecasting enabled", settings["summary"].get("Forecasting", {}).get("enableForecasts")),
    ("Quotes / Orders / Entitlements", f"{settings['summary'].get('Quote', {}).get('enableQuote')} / {settings['summary'].get('Order', {}).get('enableOrders')} / {settings['summary'].get('Entitlement', {}).get('enableEntitlements')}"),
    ("Experience Cloud (communities)", settings["summary"].get("Communities", {}).get("enableNetworksEnabled")),
    ("Einstein Activity Capture / Gmail / Outlook integration", f"{settings['summary'].get('EAC', {}).get('enableActivityCapture')} / {settings['summary'].get('EmailIntegration', {}).get('enableGmailIntegration')} / {settings['summary'].get('EmailIntegration', {}).get('enableOutlookIntegration')}"),
    ("External sharing model", settings["summary"].get("Sharing", {}).get("enableExternalSharingModel")),
    ("Session timeout", settings["summary"].get("Security", {}).get("sessionTimeout")),
], row)
def lim(n):
    l = limits.get(n); return f"{l['max'] - l['remaining']:,} used of {l['max']:,}" if l else None
row = kv_block(ws, "Limits and storage", [
    ("Data storage (MB)", lim("DataStorageMB")), ("File storage (MB)", lim("FileStorageMB")),
    ("Daily API requests (24h window at pull time)", lim("DailyApiRequests")),
    ("Legacy Attachments", f"{DQ('attach_size')[0]['n']:,} files, {DQ('attach_size')[0]['bytes']/1e9:.1f} GB" if DQ("attach_size") else None),
    ("Files (ContentDocument)", f"{counts.get('ContentDocument', 0):,} documents, {counts.get('ContentVersion', 0):,} versions"),
], row)
row = kv_block(ws, "Headline counts", [
    ("Objects with records", sum(1 for v in counts.values() if v > 0)),
    ("Custom objects (own / managed package)", f"{len(own_objs)} / {len(managed_objs)}"),
    ("Fields in retrieved metadata (own / managed)", f"{len(own_fields)} / {len(all_fields) - len(own_fields)}"),
    ("Fields profiled (98 objects)", sum(len(d["fields"]) for d in describes.values())),
    ("Record types", len(J("record_types"))),
    ("Validation rules (active / total)", f"{sum(1 for m in meta.values() for v in m['validationRules'] if v['active']=='true')} / {sum(len(m['validationRules']) for m in meta.values())}"),
    ("Flows active (own / managed)", f"{sum(1 for f in flows_all if f['IsActive'] and not f['NamespacePrefix'])} / {sum(1 for f in flows_all if f['IsActive'] and f['NamespacePrefix'])}"),
    ("Record-triggered flows active (own)", sum(1 for f in flows_meta.values() if f["status"] == "Active" and f["object"])),
    ("Workflow rules (active / total)", f"{sum(1 for w in wf_meta.values() for r in w['rules'] if r['active']=='true')} / {sum(len(w['rules']) for w in wf_meta.values())}"),
    ("Apex triggers (own / managed)", f"{sum(1 for t in J('apex_triggers') if not t['NamespacePrefix'])} / {sum(1 for t in J('apex_triggers') if t['NamespacePrefix'])}"),
    ("Apex classes (own / managed)", f"{sum(1 for t in J('apex_classes') if not t['NamespacePrefix'])} / {sum(1 for t in J('apex_classes') if t['NamespacePrefix'])}"),
    ("Approval processes", len(J("approval_processes"))),
    ("Installed packages", len(J("packages"))),
    ("Connected apps", len(J("connected_apps"))),
    ("Reports / dashboards / list views / email templates", f"{len(J('reports'))} / {len(J('dashboards'))} / {len(J('list_views'))} / {len(J('email_templates'))}"),
    ("Lightning pages / LWC / Aura / Visualforce / custom apps", f"{len(J('lightning_pages'))} / {len(J('lwc'))} / {len(J('aura'))} / {len(J('vf_pages'))} / {len(J('custom_apps'))}"),
    ("Active users", len(users_active)),
    ("Active users by license", ", ".join(f"{k}: {v}" for k, v in active_by_lic.most_common())),
    ("Inactive users", (J("users_inactive_count") or [{}])[0].get("expr0")),
    ("Profiles / roles / permission sets", f"{len(J('profiles'))} / {len(J('roles'))} / {len(J('permsets'))}"),
], row)
row = kv_block(ws, "Licenses", [(l["Name"], f"{l['UsedLicenses']} used of {l['TotalLicenses']} ({l['Status']})") for l in lic], row)

# ================= Objects =================
ws = wb.create_sheet("Objects")
flows_by_obj = collections.Counter(f["object"] for f in flows_meta.values() if f["status"] == "Active" and f["object"])
wf_by_obj = {o: sum(1 for r in w["rules"] if r["active"] == "true") for o, w in wf_meta.items()}
trg_by_obj = collections.Counter(t["TableEnumOrId"] for t in J("apex_triggers") if t["Status"] == "Active")
rt_by_obj = collections.Counter(r["SobjectType"] for r in J("record_types"))
lv_by_obj = collections.Counter(l["SobjectType"] for l in J("list_views"))
rows = []
for o, n in sorted(counts.items(), key=lambda x: -x[1]):
    if n <= 0: continue
    m = meta.get(o, {}); d = describes.get(o); p = profiles.get(o); e = entity.get(o, {})
    fields_meta = m.get("fields", {})
    nf = len(d["fields"]) if d else len(fields_meta)
    ncust = sum(1 for f in d["fields"] if f["custom"]) if d else sum(1 for f in fields_meta if f.endswith("__c"))
    nformula = sum(1 for f in (d["fields"] if d else []) if f["calculated"])
    nlook = sum(1 for f in (d["fields"] if d else []) if f["type"] == "reference")
    low = None
    if p and p.get("total_in_scope"):
        low = sum(1 for f, c in p["fill"].items() if c is not None and c / p["total_in_scope"] < 0.05)
    co = custom_objects.get(o, {})
    rows.append([o, e.get("Label") or m.get("label") or (d or {}).get("label"), ns_of(o) or ("" if o.endswith("__c") else "standard"),
        "Yes" if o.endswith("__c") else "No", n, "Yes" if p else "No", "Yes" if p and p.get("sampled_last_365d") else "",
        e.get("InternalSharingModel") or m.get("sharingModel"), e.get("ExternalSharingModel") or m.get("externalSharingModel"),
        rt_by_obj.get(o, 0), sum(1 for v in m.get("validationRules", []) if v["active"] == "true"), len(m.get("validationRules", [])),
        nf, ncust, nformula, nlook, low, flows_by_obj.get(o, 0), wf_by_obj.get(o, 0), trg_by_obj.get(o, 0),
        m.get("enableHistory"), lv_by_obj.get(o, 0), m.get("webLinks"), m.get("fieldSets"),
        (co.get("CreatedDate") or "")[:10], (co.get("CreatedBy") or {}).get("Name") if co else None, m.get("description") or co.get("Description")])
hdr = ["Object API Name", "Label", "Namespace", "Custom", "Record Count", "Profiled", "Sampled (last 365d)", "OWD Internal", "OWD External", "Record Types", "Active VRs", "Total VRs", "Fields", "Custom Fields", "Formula Fields", "Lookups", "Fields <5% Filled", "Active Record-Triggered Flows", "Active Workflow Rules", "Active Triggers", "History Tracking", "List Views", "Buttons/Links", "Field Sets", "Object Created", "Created By", "Description"]
write_table(ws, hdr, rows, wrap_cols=(26,), widths={"Description": 60, "Object API Name": 40, "Label": 32}, number_formats={"Record Count": "#,##0"})

# ================= Fields =================
ws = wb.create_sheet("Fields")
rows = []
cf_tool = custom_fields
for o in profile_objs:
    d = describes.get(o)
    if not d: continue
    p = profiles.get(o, {}); m = meta.get(o, {"fields": {}})
    total = p.get("total_in_scope") if p else None
    for f in d["fields"]:
        fn = f["name"]; fm = m["fields"].get(fn, {})
        fill = (p.get("fill") or {}).get(fn) if p else None
        tr = (p.get("bool_true") or {}).get(fn) if p else None
        pv = (p.get("picklist_values") or {}).get(fn) if p else None
        if fill is None and pv and f["type"] in ("multipicklist", "picklist"):
            fill = sum(c for k, c in pv.items() if k not in ("None", "null", ""))
        defined = fm.get("values") or [{"v": x["value"], "active": x["active"], "default": x["defaultValue"]} for x in f.get("picklistValues", [])]
        r = refs.get(fn, {}) if fn.endswith("__c") else {}
        objkey = o if not o.endswith("__c") else (custom_objects.get(o, {}).get("Id") or o)
        ct = cf_tool.get((o, fn)) or cf_tool.get((custom_objects.get(o, {}).get("Id", "-"), fn))
        rows.append([o, fn, f["label"], f["type"], f.get("length") or None, f.get("precision") or None, f.get("scale") or None,
            "Yes" if f["custom"] else "No", ns_of(fn) or "", "Yes" if (not f["nillable"] and f["createable"]) or fm.get("required") == "true" else "No",
            "Yes" if f["unique"] else "", "Yes" if f["externalId"] else "", "Yes" if f["calculated"] else "",
            (fm.get("formula") or "")[:500] or None, (f"{fm.get('summaryOperation')} of {fm.get('summarizedField')}" if fm.get("summaryOperation") else None),
            ", ".join(f.get("referenceTo") or []) or None, f.get("relationshipName"), fm.get("deleteConstraint"), "Yes" if fm.get("lookupFilter") else "",
            len(defined) or None, sum(1 for v in defined if v.get("active")) or None, fm.get("restricted") or (("Yes" if f.get("restrictedPicklist") else "No") if f["type"] in ("picklist", "multipicklist") else None),
            fm.get("controllingField") or f.get("controllerName"), fm.get("valueSetName"), fm.get("defaultValue") or f.get("defaultValueFormula"),
            fm.get("trackHistory"), fm.get("encrypted"),
            "Yes" if f["createable"] else "No", "Yes" if f["updateable"] else "No", "Yes" if f["filterable"] else "No",
            total, fill, None, tr, (None if tr is None or not total else None),
            len(pv) if pv else None, ("; ".join(f"{k} ({v:,})" for k, v in list(pv.items())[:8]) if pv else None),
            "Yes" if p and p.get("sampled_last_365d") else "",
            len(r.get("flow", [])), len(r.get("apex", [])), len(r.get("validation_rule", [])), len(r.get("formula_field", [])) + len(r.get("rollup_summary", [])), len(r.get("workflow_field_update", [])),
            "; ".join(r.get("flow", [])[:12]) or None, "; ".join(r.get("apex", [])[:8]) or None, "; ".join(r.get("validation_rule", [])[:8]) or None, "; ".join((r.get("formula_field", []) + r.get("rollup_summary", []))[:8]) or None,
            (ct or {}).get("CreatedDate", "")[:10] or None, ((ct or {}).get("CreatedBy") or {}).get("Name") if ct else None,
            fm.get("description") or None, fm.get("help") or f.get("inlineHelpText") or None])
hdr = ["Object", "Field API Name", "Label", "Type", "Length", "Precision", "Scale", "Custom", "Namespace", "Required", "Unique", "External Id", "Formula/Calculated", "Formula Text", "Roll-Up", "References", "Relationship Name", "Delete Constraint", "Lookup Filter",
       "Picklist Values Defined", "Picklist Values Active", "Restricted", "Controlling Field", "Global Value Set", "Default", "History Tracked", "Encrypted", "Createable", "Updateable", "Filterable",
       "Records In Scope", "Filled Count", "Fill %", "True Count (boolean)", "True %", "Distinct Values In Use", "Top Values In Use", "Sampled",
       "Flows Ref", "Apex Ref", "VR Ref", "Formula/Rollup Ref", "Workflow FU Ref", "Flows", "Apex", "Validation Rules", "Formulas/Rollups", "Field Created", "Field Created By", "Description", "Help Text"]
end = write_table(ws, hdr, rows, wrap_cols=(13, 36, 43, 44, 45, 46, 49, 50), widths={"Formula Text": 50, "Top Values In Use": 50, "Flows": 40, "Apex": 30, "Validation Rules": 30, "Formulas/Rollups": 30, "Description": 40, "Help Text": 40, "Object": 30, "Field API Name": 34, "Label": 28},
                  number_formats={"Records In Scope": "#,##0", "Filled Count": "#,##0", "True Count (boolean)": "#,##0", "Fill %": "0.0%", "True %": "0.0%"})
# Fill % and True % as values computed from the adjacent counts (static snapshot; see Read Me)
ci = {h: i + 1 for i, h in enumerate(hdr)}
for rr in range(2, end):
    tot = ws.cell(row=rr, column=ci["Records In Scope"]).value
    fc = ws.cell(row=rr, column=ci["Filled Count"]).value
    tc = ws.cell(row=rr, column=ci["True Count (boolean)"]).value
    if isinstance(tot, (int, float)) and tot > 0:
        if isinstance(fc, (int, float)):
            c = ws.cell(row=rr, column=ci["Fill %"], value=round(fc / tot, 4)); c.number_format = "0.0%"; c.font = BODY_FONT
        if isinstance(tc, (int, float)):
            c = ws.cell(row=rr, column=ci["True %"], value=round(tc / tot, 4)); c.number_format = "0.0%"; c.font = BODY_FONT

# ================= Picklist Values =================
ws = wb.create_sheet("Picklist Values")
rt_pick = collections.defaultdict(list)  # (obj, field, value) -> [rt]
for o, m in meta.items():
    for rt in m["recordTypes"]:
        for pk, vals in rt["picklistValues"].items():
            for v in vals: rt_pick[(o, pk, v)].append(rt["name"])
rows = []
for o in profile_objs:
    d = describes.get(o)
    if not d: continue
    p = profiles.get(o, {}); m = meta.get(o, {"fields": {}})
    for f in d["fields"]:
        if f["type"] not in ("picklist", "multipicklist"): continue
        fn = f["name"]; fm = m["fields"].get(fn, {})
        if fn.endswith(("CountryCode", "StateCode")) or fn in ("TimeZoneSidKey", "LocaleSidKey", "LanguageLocaleKey", "EmailEncodingKey", "DefaultCurrencyIsoCode", "CurrencyIsoCode"): continue
        used = (p.get("picklist_values") or {}).get(fn, {}) if p else {}
        defined = fm.get("values") or [{"v": x["value"], "active": x["active"], "default": x["defaultValue"], "label": x["label"]} for x in f.get("picklistValues", [])]
        seen = set()
        for v in defined:
            val = v["v"]; seen.add(val)
            cnt = used.get(val)
            if cnt is None and f["type"] == "multipicklist":
                cnt = sum(c for k, c in used.items() if val in str(k).split(";"))
            rows.append([o, fn, f["label"], f["type"], val, "Active" if v.get("active", True) else "Inactive", "Yes" if v.get("default") else "", cnt, "; ".join(rt_pick.get((o, fn, val), [])) or None, fm.get("valueSetName"), ""])
        for val, cnt in used.items():
            if val in seen or val in ("None", "null") or (f["type"] == "multipicklist" and ";" in str(val)): continue
            rows.append([o, fn, f["label"], f["type"], val, "NOT DEFINED (in data only)", "", cnt, None, fm.get("valueSetName"), "Value exists on records but is not in the picklist definition"])
hdr = ["Object", "Field API Name", "Field Label", "Type", "Value", "Status", "Default", "Records Using Value", "Record Types Exposing Value", "Global Value Set", "Note"]
write_table(ws, hdr, rows, widths={"Value": 40, "Record Types Exposing Value": 40, "Note": 45}, number_formats={"Records Using Value": "#,##0"})

# ================= Record Types =================
ws = wb.create_sheet("Record Types")
rows = []
rtmeta = {(o, rt["name"]): rt for o, m in meta.items() for rt in m["recordTypes"]}
for r in J("record_types"):
    rm = rtmeta.get((r["SobjectType"], r["DeveloperName"]), {})
    rows.append([r["SobjectType"], r["DeveloperName"], r["Name"], "Yes" if r["IsActive"] else "No", rm.get("businessProcess"), r.get("NamespacePrefix"), len(rm.get("picklistValues", {})), "; ".join(f"{k}: {len(v)} values" for k, v in rm.get("picklistValues", {}).items()) or None, r.get("Description") or rm.get("description"), r["Id"]])
write_table(ws, ["Object", "Developer Name", "Label", "Active", "Business Process", "Namespace", "Picklists Overridden", "Picklist Value Counts", "Description", "Id"], rows, widths={"Picklist Value Counts": 60, "Description": 50}, wrap_cols=(7, 8))

# ================= Validation Rules =================
ws = wb.create_sheet("Validation Rules")
rows = []
for o, m in meta.items():
    for v in m["validationRules"]:
        fml = v["formula"] or ""
        rows.append([o, v["name"], "Yes" if v["active"] == "true" else "No", v["field"], v["message"], v["description"], fml, "; ".join(sorted(set(re.findall(r"\b([A-Za-z0-9_]+__c)\b", fml)))) or None,
            "Yes" if re.search(r"\b0[0-9A-Za-z]{14,17}\b", fml) else "", "Yes" if "$Profile" in fml or "$UserRole" in fml or "$User." in fml else "", "Yes" if "$Permission" in fml else ""])
write_table(ws, ["Object", "Rule", "Active", "Error Field", "Error Message", "Description", "Formula", "Custom Fields Referenced", "Hard-coded Id", "Profile/Role/User Dependent", "Custom Permission Bypass"], rows, wrap_cols=(4, 5, 6, 7), widths={"Error Message": 50, "Description": 45, "Formula": 70, "Custom Fields Referenced": 40})

# ================= Flows =================
ws = wb.create_sheet("Flows")
rows = []
for f in sorted(flows_all, key=lambda x: (x["NamespacePrefix"] or "", not x["IsActive"], x["ApiName"])):
    fm = flows_meta.get(f["ApiName"], {})
    rows.append([f["ApiName"], f["Label"], f["NamespacePrefix"] or "", f["ProcessType"], f["TriggerType"], f.get("RecordTriggerType"), fm.get("object") or f.get("TriggerObjectOrEventLabel"), "Yes" if f["IsActive"] else "No",
        f.get("VersionNumber"), (f.get("LastModifiedDate") or "")[:10], f.get("LastModifiedBy"), f.get("Builder"), len(fm.get("customRefs", [])), "; ".join(fm.get("customRefs", [])[:40]) or None,
        "; ".join(fm.get("emails", [])) or None, "; ".join(fm.get("hardcodedIds", [])) or None, f.get("Description") or fm.get("description")])
write_table(ws, ["API Name", "Label", "Namespace", "Process Type", "Trigger Type", "Record Trigger", "Object", "Active", "Version", "Last Modified", "Modified By", "Builder", "Custom Fields Referenced (n)", "Custom Fields Referenced", "Email Addresses In Flow", "Hard-coded Ids", "Description"], rows, wrap_cols=(13, 14, 15, 16), widths={"Custom Fields Referenced": 60, "Email Addresses In Flow": 40, "Hard-coded Ids": 30, "Description": 50})

# ================= Workflows, Triggers, Approvals =================
ws = wb.create_sheet("Workflows Triggers Approvals")
row = 1
ws.cell(row=row, column=1, value="Workflow rules").font = Font(name=FONT, bold=True, size=12); row += 1
rows = []
for o, w in wf_meta.items():
    for r in w["rules"]:
        rows.append([o, r["name"], "Yes" if r["active"] == "true" else "No", r["triggerType"], "; ".join(f"{t}:{n}" for t, n in r["actions"]) or None, r["description"]])
row = write_table(ws, ["Object", "Rule", "Active", "Trigger", "Actions (type:name)", "Description"], rows, start_row=row, wrap_cols=(4, 5), widths={"Actions (type:name)": 60, "Description": 50}) + 1
ws.cell(row=row, column=1, value="Workflow email alerts").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[o, a["name"], "; ".join(x for x in a["recipients"] if x), "; ".join(a["ccEmails"]), a["template"]] for o, w in wf_meta.items() for a in w["alerts"]]
row = write_table(ws, ["Object", "Alert", "Recipients", "CC Emails", "Template"], rows, start_row=row, wrap_cols=(2, 3), widths={"Recipients": 60, "CC Emails": 40}) + 1
ws.cell(row=row, column=1, value="Workflow field updates").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[o, u["name"], u["field"], u["operation"]] for o, w in wf_meta.items() for u in w["fieldUpdates"]]
row = write_table(ws, ["Object", "Field Update", "Field", "Operation"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Apex triggers").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[t["TableEnumOrId"], t["Name"], t["Status"], t["NamespacePrefix"] or "", t["ApiVersion"], ", ".join(k.replace("Usage", "") for k in ("UsageBeforeInsert", "UsageAfterInsert", "UsageBeforeUpdate", "UsageAfterUpdate", "UsageBeforeDelete", "UsageAfterDelete") if t.get(k)), t["LengthWithoutComments"]] for t in sorted(J("apex_triggers"), key=lambda x: (x["NamespacePrefix"] or "", x["TableEnumOrId"]))]
row = write_table(ws, ["Object", "Trigger", "Status", "Namespace", "API Version", "Events", "Length (chars)"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Approval processes").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[a["TableEnumOrId"], a["Name"], a["DeveloperName"], a["State"], a["Type"], a.get("Description")] for a in J("approval_processes")]
row = write_table(ws, ["Object", "Name", "Developer Name", "State", "Type", "Description"], rows, start_row=row, wrap_cols=(5,), widths={"Description": 60}) + 1
ws.cell(row=row, column=1, value="Duplicate rules").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[d["SobjectType"], d["DeveloperName"], d["MasterLabel"], "Yes" if d["IsActive"] else "No"] for d in J("duplicate_rules")]
row = write_table(ws, ["Object", "Developer Name", "Label", "Active"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Assignment rules").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[a["SobjectType"], a["Name"], "Yes" if a["Active"] else "No"] for a in J("assignment_rules")]
row = write_table(ws, ["Object", "Rule", "Active"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Sharing rules").font = Font(name=FONT, bold=True, size=12); row += 1
rows = []
for o, s in sharing.items():
    for c in s["criteria"]: rows.append([o, "Criteria", c["name"], c["access"]])
    for c in s["owner"]: rows.append([o, "Owner", c["name"], c["access"]])
row = write_table(ws, ["Object", "Kind", "Rule", "Access"], rows, start_row=row) + 1
ws.freeze_panes = None

# ================= Scheduled Jobs =================
ws = wb.create_sheet("Scheduled Jobs")
rows = [[j["CronJobDetail"]["Name"], j["CronJobDetail"]["JobType"], j["State"], (j.get("NextFireTime") or "")[:16], j["CronExpression"], (j.get("CreatedBy") or {}).get("Name")] for j in J("scheduled_jobs")]
jt = {"7": "Scheduled Apex", "9": "Batch Job", "8": "Scheduled Flow", "3": "Dashboard Refresh", "4": "Analytic Snapshot", "A": "Report Run", "0": "Data Export", "1": "Reporting Snapshot"}
rows = [[r[0], jt.get(r[1], r[1]), r[2], r[3], r[4], r[5]] for r in rows]
write_table(ws, ["Job", "Type", "State", "Next Fire (UTC)", "Cron", "Created By"], rows, widths={"Job": 60})

# ================= Integrations =================
ws = wb.create_sheet("Integrations")
row = 1
ws.cell(row=row, column=1, value="Installed packages").font = Font(name=FONT, bold=True, size=12); row += 1
pk_objs = collections.Counter(ns_of(o) for o in counts if ns_of(o))
pk_fields = collections.Counter(ns_of(f) for o, f in all_fields if ns_of(f))
pk_flows = collections.Counter(f["NamespacePrefix"] for f in flows_all if f["NamespacePrefix"])
rows = [[p["SubscriberPackage"]["Name"], p["SubscriberPackage"]["NamespacePrefix"] or "", p["SubscriberPackageVersion"]["Name"], f"{p['SubscriberPackageVersion']['MajorVersion']}.{p['SubscriberPackageVersion']['MinorVersion']}", pk_objs.get(p["SubscriberPackage"]["NamespacePrefix"], 0), pk_fields.get(p["SubscriberPackage"]["NamespacePrefix"], 0), pk_flows.get(p["SubscriberPackage"]["NamespacePrefix"], 0)] for p in J("packages")]
row = write_table(ws, ["Package", "Namespace", "Version Name", "Version", "Objects With Records", "Fields In Metadata", "Flows"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Connected apps and login sources (last 90 days)").font = Font(name=FONT, bold=True, size=12); row += 1
logins = {}
for r in J("login_apps_90d"): logins.setdefault(r["Application"], []).append(f"{r['LoginType']}{'/' + r['ApiType'] if r.get('ApiType') else ''}: {r['n']:,}")
seen = set(); rows = []
for a in sorted(J("connected_apps"), key=lambda x: x["Name"]):
    seen.add(a["Name"]); rows.append([a["Name"], "Connected app", (a["CreatedDate"] or "")[:10], (a.get("CreatedBy") or {}).get("Name"), "; ".join(logins.get(a["Name"], [])) or "no logins in 90 days"])
for app, v in logins.items():
    if app not in seen: rows.append([app, "Login source (not a local connected app)", None, None, "; ".join(v)])
row = write_table(ws, ["Name", "Kind", "Created", "Created By", "Logins Last 90 Days (type: count)"], rows, start_row=row, widths={"Logins Last 90 Days (type: count)": 60}) + 1
ws.cell(row=row, column=1, value="Named credentials, remote sites, auth providers").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [["Named credential", n["DeveloperName"], n["Endpoint"], n.get("PrincipalType")] for n in J("named_creds")] + [["Remote site", r["SiteName"], r["EndpointUrl"], "Active" if r["IsActive"] else "Inactive"] for r in J("remote_sites")] + [["Auth provider", a["DeveloperName"], a["ProviderType"], None] for a in J("auth_providers")]
row = write_table(ws, ["Kind", "Name", "Endpoint / Type", "Detail"], rows, start_row=row, widths={"Endpoint / Type": 60}) + 1
ws.freeze_panes = None

# ================= Users & Access =================
ws = wb.create_sheet("Users Access")
row = 1
ws.cell(row=row, column=1, value="Active users").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[u["Name"], u["Username"], pname(u), plic(u), (u.get("UserRole") or {}).get("Name"), u.get("Title"), u.get("Department"), u.get("Division"), (u.get("LastLoginDate") or "")[:10], (u.get("CreatedDate") or "")[:10], u["UserType"]] for u in users_active]
row = write_table(ws, ["Name", "Username", "Profile", "License", "Role", "Title", "Department", "Division", "Last Login", "Created", "User Type"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Profiles").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[p["Name"], (p.get("UserLicense") or {}).get("Name"), p["UserType"], (p.get("Users") or {}).get("totalSize", 0) if p.get("Users") else 0] for p in J("profiles")]
row = write_table(ws, ["Profile", "License", "User Type", "Active Users"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Roles").font = Font(name=FONT, bold=True, size=12); row += 1
roles = {r["Id"]: r for r in J("roles")}
rows = [[r["Name"], r["DeveloperName"], roles.get(r.get("ParentRoleId"), {}).get("Name")] for r in J("roles")]
row = write_table(ws, ["Role", "Developer Name", "Parent Role"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Permission sets (with assignment counts)").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[p["Label"], p["Name"], p.get("NamespacePrefix") or "", (p.get("License") or {}).get("Name"), (p.get("Assignments") or {}).get("totalSize", 0) if p.get("Assignments") else 0] for p in J("permsets")]
row = write_table(ws, ["Permission Set", "API Name", "Namespace", "License", "Assignments"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Permission set licenses").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[p["MasterLabel"], p["DeveloperName"], p["TotalLicenses"], p["UsedLicenses"], p["Status"]] for p in J("psls")]
row = write_table(ws, ["License", "Developer Name", "Total", "Used", "Status"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Queues and public groups").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[g["Name"], g["DeveloperName"], g["Type"], g.get("Email"), "; ".join(x["SobjectType"] for x in (g.get("QueueSobjects") or {}).get("records", [])) if g.get("QueueSobjects") else None] for g in J("queues")]
row = write_table(ws, ["Name", "Developer Name", "Type", "Email", "Objects"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Org-wide defaults (customizable objects)").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[e["QualifiedApiName"], e["Label"], e.get("InternalSharingModel"), e.get("ExternalSharingModel"), counts.get(e["QualifiedApiName"], 0), len(sharing.get(e["QualifiedApiName"], {}).get("criteria", [])) + len(sharing.get(e["QualifiedApiName"], {}).get("owner", []))] for e in sorted(J("entity_defs"), key=lambda x: -counts.get(x["QualifiedApiName"], 0)) if e.get("InternalSharingModel")]
row = write_table(ws, ["Object", "Label", "OWD Internal", "OWD External", "Records", "Sharing Rules"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Custom permissions").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[c["DeveloperName"], c["MasterLabel"], c.get("NamespacePrefix") or ""] for c in J("custom_perms")]
row = write_table(ws, ["Developer Name", "Label", "Namespace"], rows, start_row=row) + 1
ws.freeze_panes = None

# ================= Data Volumes =================
ws = wb.create_sheet("Data Volumes")
row = 1
ws.cell(row=row, column=1, value="Record counts, every object with data").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[o, n, ns_of(o) or ("" if o.endswith("__c") else "standard"), "Yes" if o in profiles else "No"] for o, n in sorted(counts.items(), key=lambda x: -x[1]) if n > 0]
row = write_table(ws, ["Object", "Records", "Namespace", "Profiled"], rows, start_row=row, number_formats={"Records": "#,##0"}) + 1
ws.cell(row=row, column=1, value="Records created per year, core objects").font = Font(name=FONT, bold=True, size=12); row += 1
yr = {}
for nm, lab in [("acct_created_year", "Account"), ("contact_created_year", "Contact"), ("lead_created_year", "Lead"), ("opp_created_year", "Opportunity"), ("case_created_year", "Case"), ("task_year", "Task"), ("email_year", "EmailMessage"), ("snapshot_year", "Opportunity_Pipeline_Snapshot__c")]:
    for r in DQ(nm): yr.setdefault(int(r["y"]), {})[lab] = r["n"]
labs = ["Account", "Contact", "Lead", "Opportunity", "Case", "Task", "EmailMessage", "Opportunity_Pipeline_Snapshot__c"]
rows = [[str(y)] + [yr[y].get(l) for l in labs] for y in sorted(yr)]
row = write_table(ws, ["Year"] + labs, rows, start_row=row, number_formats={l: "#,##0" for l in labs}) + 1
ws.freeze_panes = None

# ================= Data Quality =================
ws = wb.create_sheet("Data Quality")
row = 1
def dq_table(title, name, cols, labels, fmt=None):
    global row
    recs = DQ(name)
    if not recs: return
    ws.cell(row=row, column=1, value=title).font = Font(name=FONT, bold=True, size=12); row += 1
    rows = [[r.get(c) if not isinstance(r.get(c), dict) else r.get(c, {}).get("Name") for c in cols] for r in recs]
    row = write_table(ws, labels, rows, start_row=row, number_formats=fmt or {"Count": "#,##0", "Amount": "#,##0"}) + 1
def dq_single(title, pairs):
    global row
    row = kv_block(ws, title, pairs, row)
def one(name, key="n"):
    r = DQ(name); return r[0].get(key) if r else None
dq_single("Hygiene checks", [
    ("Accounts owned by inactive users", one("acct_owner_inactive")),
    ("Accounts with a parent account", one("acct_parent")),
    ("Account names shared by more than one account", len(DQ("acct_dup_names"))),
    ("Contacts without an account", one("contact_no_acct")),
    ("Contacts owned by inactive users", one("contact_owner_inactive")),
    ("Contact email addresses shared by 2+ contacts (top 200 groups shown in query)", f"{len(DQ('contact_dup_email'))} groups, {sum(r['n'] for r in DQ('contact_dup_email')):,} contacts"),
    ("Opportunities owned by inactive users (all / open)", f"{one('opp_owner_inactive'):,} / {one('opp_open_owner_inactive'):,}"),
    ("Open opportunities with no product lines", one("opp_open_no_products")),
    ("Latest-version files total size", f"{(one('files_size','bytes') or 0)/1e6:.1f} MB across {one('files_size')} versions (ContentVersion sum is limited by API visibility)"),
    ("Legacy Attachments total size", f"{(one('attach_size','bytes') or 0)/1e9:.1f} GB across {one('attach_size'):,} attachments"),
])
dq_table("Accounts by Status", "acct_by_status", ["Status__c", "n"], ["Status", "Count"])
dq_table("Accounts by Type", "acct_by_type", ["Type", "n"], ["Type", "Count"])
dq_table("Accounts by record type", "acct_by_rt", ["Name", "n"], ["Record Type", "Count"])
dq_table("Accounts by billing country", "acct_country", ["BillingCountry", "n"], ["Billing Country", "Count"])
dq_table("Top account owners", "owners_top", ["Name", "IsActive", "n"], ["Owner", "Active", "Accounts"], {"Accounts": "#,##0"})
dq_table("Contacts by status", "contact_status", ["Contact_Status__c", "n"], ["Status", "Count"])
dq_table("Leads by status", "lead_status", ["Status", "IsConverted", "n"], ["Status", "Converted", "Count"])
dq_table("Opportunities by record type and stage", "opp_by_rt_stage", ["rt", "StageName", "n", "amt"], ["Record Type", "Stage", "Count", "Amount"])
dq_table("Won opportunities by type and close year", "opp_by_type_year", ["Type", "y", "n", "amt"], ["Type", "Close Year", "Count", "Amount"])
dq_table("Products by family and active flag", "products_active", ["Family", "IsActive", "n"], ["Family", "Active", "Count"])
dq_table("Assets by status and contract term type", "asset_status", ["Status", "Contract_Term_Type__c", "n"], ["Status", "Term Type", "Count"])
dq_table("Cases by record type and status", "case_by_rt_status", ["rt", "Status", "n"], ["Record Type", "Status", "Count"])
dq_table("Campaigns by type", "campaign_type", ["Type", "IsActive", "n"], ["Type", "Active", "Count"])
dq_table("Tasks by subtype", "task_subtype", ["TaskSubtype", "n"], ["Subtype", "Count"])
dq_table("Users by license and status", "users_by_license", ["lic", "IsActive", "n"], ["License", "Active", "Count"])
dq_table("Duplicate contact emails (top 200)", "contact_dup_email", ["Email", "n"], ["Email", "Contacts"], {"Contacts": "#,##0"})
ws.freeze_panes = None

# ================= Reports & UI =================
ws = wb.create_sheet("Reports UI")
row = 1
reps = J("reports"); cutoff = "2025-10-13"
byf = collections.defaultdict(lambda: [0, 0, 0])
for r in reps:
    f = r.get("FolderName") or "(private)"; byf[f][0] += 1
    if (r.get("LastRunDate") or "") >= cutoff: byf[f][1] += 1
    if not r.get("LastRunDate"): byf[f][2] += 1
ws.cell(row=row, column=1, value="Reports by folder").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[f, v[0], v[1], v[2]] for f, v in sorted(byf.items(), key=lambda x: -x[1][0])]
row = write_table(ws, ["Folder", "Reports", "Run In Last 12 Months", "Never Run"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Dashboards").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[d["Title"], d.get("FolderName"), (d.get("RunningUser") or {}).get("Name"), (d.get("LastModifiedDate") or "")[:10]] for d in J("dashboards")]
row = write_table(ws, ["Dashboard", "Folder", "Running User", "Last Modified"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="List views by object").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[o, n] for o, n in collections.Counter(l["SobjectType"] for l in J("list_views")).most_common()]
row = write_table(ws, ["Object", "List Views"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Email templates by folder").font = Font(name=FONT, bold=True, size=12); row += 1
et = collections.defaultdict(lambda: [0, 0, 0])
for t in J("email_templates"):
    f = t.get("FolderName") or "(private)"; et[f][0] += 1; et[f][1] += 1 if t.get("IsActive") else 0; et[f][2] += 1 if (t.get("LastUsedDate") or "") >= cutoff else 0
rows = [[f, v[0], v[1], v[2]] for f, v in sorted(et.items(), key=lambda x: -x[1][0])]
row = write_table(ws, ["Folder", "Templates", "Active", "Used In Last 12 Months"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Custom apps").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[a["Label"], a["DeveloperName"], a.get("NamespacePrefix") or "", a.get("UiType")] for a in J("custom_apps")]
row = write_table(ws, ["App", "Developer Name", "Namespace", "UI Type"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Lightning record pages").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [[p["DeveloperName"], p["Type"], (p.get("EntityDefinition") or {}).get("QualifiedApiName")] for p in J("lightning_pages")]
row = write_table(ws, ["Page", "Type", "Object"], rows, start_row=row) + 1
ws.cell(row=row, column=1, value="Custom code").font = Font(name=FONT, bold=True, size=12); row += 1
rows = [["Lightning Web Components (own / managed)", sum(1 for x in J("lwc") if not x.get("NamespacePrefix")), sum(1 for x in J("lwc") if x.get("NamespacePrefix"))],
        ["Aura components (own / managed)", sum(1 for x in J("aura") if not x.get("NamespacePrefix")), sum(1 for x in J("aura") if x.get("NamespacePrefix"))],
        ["Visualforce pages (own / managed)", sum(1 for x in J("vf_pages") if not x.get("NamespacePrefix")), sum(1 for x in J("vf_pages") if x.get("NamespacePrefix"))],
        ["Apex classes (own / managed)", sum(1 for x in J("apex_classes") if not x.get("NamespacePrefix")), sum(1 for x in J("apex_classes") if x.get("NamespacePrefix"))],
        ["Static resources (own / managed)", sum(1 for x in J("static_resources") if not x.get("NamespacePrefix")), sum(1 for x in J("static_resources") if x.get("NamespacePrefix"))],
        ["Custom labels", len(J("custom_labels")), None]]
row = write_table(ws, ["Component", "Own", "Managed"], rows, start_row=row) + 1
ws.freeze_panes = None

# ================= Merge Considerations =================
ws = wb.create_sheet("Merge Considerations")
rows = []
def add(area, finding, evidence, where, sev):
    rows.append([area, finding, evidence, where, sev])
pk = J("packages")
add("Packages", "23 managed packages installed; several are legacy or superseded (Helpshift, Freshdesk, SalesforceIQ Inbox, HubSpot, Public Knowledge, Opportunity Push Counter, Field Trip, Field Spy). Each adds objects/fields that cannot be edited and must be installed in any target org or dropped.", f"{len(pk)} packages; {len(managed_objs)} managed objects in metadata; {len(all_fields)-len(own_fields):,} managed fields", "Integrations tab", "High")
add("Volume", "Three objects dominate storage and will dominate migration time: Opportunity Pipeline Snapshot (1.49M rows, written daily since 2024), Task (1.29M, mostly Einstein Activity Capture email rows) and the TaskRelation/EmailMessageRelation join tables.", f"Opportunity_Pipeline_Snapshot__c {counts.get('Opportunity_Pipeline_Snapshot__c',0):,}; Task {counts.get('Task',0):,}; TaskRelation {counts.get('TaskRelation',0):,}; EmailMessage {counts.get('EmailMessage',0):,}", "Data Volumes tab", "High")
add("Volume", "Legacy Attachments still hold most file storage; they do not migrate as Files without conversion.", f"{one('attach_size'):,} attachments, {(one('attach_size','bytes') or 0)/1e9:.1f} GB", "Data Quality tab", "Medium")
add("Ownership", "Large share of records owned by inactive users; a merge normally requires re-owning or a placeholder user.", f"Contacts {one('contact_owner_inactive'):,}; Opportunities {one('opp_owner_inactive'):,} (open {one('opp_open_owner_inactive'):,}); Accounts {one('acct_owner_inactive'):,}; inactive users {(J('users_inactive_count') or [{}])[0].get('expr0')}", "Data Quality tab", "Medium")
add("Duplicates", "Contact email duplicates are common (shared mailboxes and the same person on several accounts); account names are unique but matching to acquired orgs will need address/domain keys.", f"{len(DQ('contact_dup_email'))}+ duplicate email groups; Account duplicate names: {len(DQ('acct_dup_names'))}", "Data Quality tab", "Medium")
nhard = sum(1 for f in flows_meta.values() if f["status"] == "Active" and f["hardcodedIds"]) ; nvr = sum(1 for m in meta.values() for v in m["validationRules"] if v["active"] == "true" and re.search(r"\b0[0-9A-Za-z]{14,17}\b", v["formula"] or ""))
add("Automation", "Hard-coded record Ids (users, queues, record types, profiles) inside active flows and validation rules break when metadata is recreated in another org.", f"{nhard} active flows and {nvr} active validation rules contain 15/18-character Ids", "Flows and Validation Rules tabs", "High")
add("Automation", "Automation is split across three generations: classic workflow rules, record-triggered flows and Apex triggers on the same objects (Opportunity, Account, Case). Order-of-execution conflicts are likely when adding another org's automation.", f"Active workflow rules {sum(1 for w in wf_meta.values() for r in w['rules'] if r['active']=='true')}; active record-triggered flows {sum(1 for f in flows_meta.values() if f['status']=='Active' and f['object'])}; active own triggers {sum(1 for t in J('apex_triggers') if t['Status']=='Active' and not t['NamespacePrefix'])}", "Workflows Triggers Approvals, Flows", "High")
add("Automation", "Emails are sent to named people and shared inboxes from flows and workflow alerts; recipients must be re-mapped if users or domains change.", f"{sum(1 for f in flows_meta.values() if f['status']=='Active' and f['emails'])} active flows carry literal email addresses; {sum(len(w['alerts']) for w in wf_meta.values())} workflow alerts", "Flows tab (Email Addresses column)", "Medium")
add("Integrations", "Live integrations that authenticate to this org and would need re-pointing: NetSuite via Celigo (SOAP login, user Passport Operations), HubSpot, Gong, Zapier, Fivetran, Ironclad, Atlassian, Pursuit, Einstein Activity Capture, Salesforce Inbox/Insights, AdWords.", "See Integrations tab login counts (90 days)", "Integrations tab", "High")
add("Integrations", "SOAP API login() retirement (Summer '27) affects the Celigo NetSuite connection; Winter '27 requires the Use Any API Auth permission on the integration user.", "1 SOAP client in LoginHistory", "Integrations tab", "Medium")
add("Schema", "Picklist sprawl: values present in data that are no longer defined, and inactive values still in use, will not load into a target org without mapping.", f"{sum(1 for r in wb['Picklist Values'].iter_rows(min_row=2, values_only=True) if r[5] and str(r[5]).startswith('NOT DEFINED'))} undefined-in-data values; {sum(1 for r in wb['Picklist Values'].iter_rows(min_row=2, values_only=True) if r[5]=='Inactive' and r[7])} inactive values still on records", "Picklist Values tab", "Medium")
lowfill = sum(1 for r in wb["Fields"].iter_rows(min_row=2, values_only=True) if r[7] == "Yes" and r[31] is not None and r[30] and r[31] / r[30] < 0.01)
add("Schema", "Many custom fields are effectively unused (under 1% filled); candidates to drop rather than map.", f"{lowfill} custom fields on profiled objects are <1% filled", "Fields tab, sort by Fill %", "Medium")
add("Schema", "Record types drive different page layouts, picklists and validation on Opportunity (4), Account (3), Case (several); the acquired orgs' processes must be mapped to these or added.", f"{len(J('record_types'))} record types across {len(rt_by_obj)} objects", "Record Types tab", "Medium")
add("Schema", "Key business logic lives in formula and roll-up fields (NetSuite revenue, renewal dates, at-risk projection). Formulas reference fields that must exist with the same API names after a merge.", f"{sum(1 for o,f in all_fields if meta[o]['fields'][f].get('formula'))} formula fields; {sum(1 for o,f in all_fields if meta[o]['fields'][f].get('summaryOperation'))} roll-up summaries; plus Rollup Helper and DLRS packages", "Fields tab (Formula Text, Roll-Up)", "Medium")
add("Security", "Org-wide defaults are mixed (Private on Case and several custom objects, Public on others) and Experience Cloud is enabled with an external sharing model; sharing must be reconciled before loading external data.", f"{sum(1 for e in J('entity_defs') if e.get('InternalSharingModel')=='Private')} objects Private internally; communities enabled", "Users Access tab (OWD section)", "Medium")
add("Security", "Access is managed through 38 profiles plus 166 permission sets, many legacy; consolidating to permission-set groups before a merge reduces mapping work.", f"{len(J('profiles'))} profiles, {len(J('permsets'))} permission sets, {len(J('psls'))} permission set licenses", "Users Access tab", "Low")
add("Features", "Territory Management 2.0, Forecasting, Quotes, Orders, Entitlements and Communities are enabled; some are lightly used (Contract: 1 record) and may be settings only.", "See Org Summary feature flags and Data Volumes", "Org Summary", "Low")
add("Reporting", "Nearly 3,000 reports, many never run; a merge is the moment to retire them.", f"{len(reps)} reports, {sum(1 for r in reps if not r.get('LastRunDate'))} never run, {sum(1 for r in reps if (r.get('LastRunDate') or '') >= cutoff)} run in the last 12 months", "Reports UI tab", "Low")
add("Knowledge", "Salesforce Knowledge (FAQ articles) exists but the API user cannot read it; article data and the Public Knowledge package need a separate review.", "pkb_ka__c 1 record; FAQ__kav not retrievable", "n/a", "Low")
write_table(ws, ["Area", "Finding", "Evidence", "Where To Look", "Severity"], rows, wrap_cols=(1, 2), widths={"Finding": 90, "Evidence": 60, "Where To Look": 30})

# fonts on key/value sheets
for name in ("Read Me", "Org Summary"):
    for r in wb[name].iter_rows():
        for c in r:
            if c.value is not None and c.font.name != FONT: c.font = Font(name=FONT, size=c.font.size or 10, bold=c.font.bold, italic=c.font.italic, color=c.font.color)
wb.save(OUT)
print("saved", OUT, "| sheets:", wb.sheetnames)
for n in wb.sheetnames: print(f"  {n}: {wb[n].max_row} rows x {wb[n].max_column} cols")
