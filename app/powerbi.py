"""Power BI dataset (EX-1): one set of queries behind the JSON "Web" feed and the downloadable star-schema package.

Package = Fact_Invoices.csv, Dim_Customers.csv, Dim_Detectors.csv, Fact_Findings_AJEs.csv + measures.dax. Money is
integer paise in every column (the DAX measures divide by 100). Read-only audit handles. Client text is untrusted: any
cell starting with = + - @ is prefixed with ' so Excel / Power BI never evaluates it as a formula.
"""
import csv
import io
import json
import zipfile

from app import config, db, findings

FORMULA_PREFIXES = ("=", "+", "-", "@")

# Detector reference table (one source of truth; the overview page reads it through /api/audit/overview).
# severity = the highest severity the detector emits.
DETECTORS = {
    "D0": ("Register vs SoR", "SA 500 / SA 230", 5),
    "D1": ("Related parties", "SA 550 / Ind AS 24", 5),
    "D2": ("RP period shift", "SA 550 / s.188", 4),
    "D3": ("Cut-off / control", "Ind AS 115 / SA 240", 5),
    "D4": ("Movement void", "CGST Rule 138", 5),
    "D5": ("Period concentration", "SA 520 / SA 240", 3),
    "D6": ("Statutory portal", "CGST Rules 46/48", 5),
    "D7": ("Manual journals", "SA 240 para 32", 5),
    "D8": ("Evidence reliability", "SA 500 / SA 240", 5),
    "D9": ("Credit notes", "Ind AS 115 / CGST s.34", 5),
    "D10": ("Circular loops", "Companies Act s.143(12)", 4),
    "D11": ("Changes after testing", "SA 230", 4),
    "D12": ("Record integrity", "SA 230 / SA 265", 5),
    "D13": ("Sequence breaks", "CGST Rule 46(b)", 4),
    "D14": ("Client data injection", "OWASP LLM01 / SA 240", 3),
    "D15": ("Purchase to pay", "SA 500 / SA 330", 5),
}


def detector_rows():
    return [{"detector_id": k, "name": n, "standard": s, "severity": sev} for k, (n, s, sev) in DETECTORS.items()]


def safe(v):
    """Formula-injection guard for spreadsheet cells (strings only; numbers stay numbers)."""
    if isinstance(v, str) and v.startswith(FORMULA_PREFIXES):
        return "'" + v
    return v


def _latest(a, otype, col):
    return {r[0]: r[1] for r in a.execute(
        f"SELECT object_id, {col} FROM risk_snapshots WHERE object_type = ? AND rowid IN"
        f" (SELECT MAX(rowid) FROM risk_snapshots WHERE object_type = ? GROUP BY object_id)", (otype, otype))}


def tables(engagement_id=None, role="audit_staff"):
    """-> {invoices, customers, detectors, findings, engagement}: the four tables, money in integer paise."""
    from app import analytics
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("erp", role) as e, db.borrow("audit", role) as a:
        eng = a.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone()
        eng = dict(eng) if eng else {}
        risk = _latest(a, "INVOICE", "R")
        ent = _latest(a, "PARTY", "E")
        sampled = {}
        for r in a.execute("SELECT s.doc_id, s.tested_at, s.conclusion_proposed FROM samples s JOIN sample_runs r ON"
                           " r.id = s.run_id WHERE r.engagement_id = ? ORDER BY s.tested_at", (eid,)):
            sampled[r[0]] = (r[2] or "TESTED") if r[1] else "SELECTED"
        undisclosed = {r[0] for r in a.execute("SELECT DISTINCT object_id FROM risk_hits WHERE engagement_id = ? AND"
                                               " object_type = 'party' AND detector IN ('D1', 'D2')", (eid,))}
        fs = [dict(r) for r in a.execute("SELECT * FROM findings WHERE engagement_id = ? ORDER BY id", (eid,))]
        invoices = [dict(r) for r in e.execute(
            "SELECT i.id, i.invoice_no, i.invoice_date, i.party_id, i.round_off_paise,"
            " COALESCE(SUM(l.taxable_paise), 0) AS taxable_paise,"
            " COALESCE(SUM(l.igst_paise + l.cgst_paise + l.sgst_paise), 0) AS tax_paise"
            " FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id = i.id WHERE i.status = 'ISSUED'"
            " GROUP BY i.id ORDER BY i.invoice_date, i.invoice_no")]
        related = analytics._self_related(e) | undisclosed
        used = {i["party_id"] for i in invoices}
        parties = [dict(r) for r in e.execute("SELECT id, name, state_code, tags FROM parties ORDER BY id")]
    inv_no = {i["id"]: i["invoice_no"] for i in invoices}
    fact_inv = [{"invoice_no": i["invoice_no"], "invoice_date": i["invoice_date"], "party_id": i["party_id"],
                 "taxable_paise": i["taxable_paise"], "tax_paise": i["tax_paise"],
                 "total_paise": i["taxable_paise"] + i["tax_paise"] + (i["round_off_paise"] or 0),
                 "risk_score": round((risk.get(i["id"]) or 0) / 1000), "sample_status": sampled.get(i["id"], "NOT_SAMPLED")}
                for i in invoices]
    customers = [{"party_id": p["id"], "name": p["name"], "state_code": p["state_code"] or "",
                  "is_related_party": 1 if p["id"] in related else 0, "entity_risk_E": round((ent.get(p["id"]) or 0) / 1000)}
                 for p in parties if p["id"] in used or "CUSTOMER" in (p["tags"] or "")]
    fact_f = []
    for f in fs:
        refs = json.loads(f["doc_refs_json"] or "[]")
        no = next((inv_no[r] for r in refs if r in inv_no), None)
        lines = json.loads(f["proposed_aje_json"]) if f["proposed_aje_json"] else []
        base = {"finding_id": f["id"], "invoice_no": no, "category": f["category"], "status": f["status"],
                "impact_paise": int(f["gross_impact_paise"] or 0)}
        if not lines:
            fact_f.append({**base, "aje_account": None, "aje_debit_paise": 0, "aje_credit_paise": 0})
        for l in lines:
            fact_f.append({**base, "aje_account": l.get("account_code"), "aje_debit_paise": int(l.get("dr_paise") or 0),
                           "aje_credit_paise": int(l.get("cr_paise") or 0)})
    return {"engagement": {"id": eid, "entity": config.ENTITY_NAME, "period_start": eng.get("period_start"),
                           "period_end": eng.get("period_end"), "materiality_paise": eng.get("materiality_paise")},
            "invoices": fact_inv, "customers": customers, "detectors": detector_rows(), "findings": fact_f}


def feed(engagement_id=None, role="audit_staff"):
    """The JSON "Web" source for Power BI (also /api/integrations/powerbi)."""
    t = tables(engagement_id, role)
    return {"dataset_name": f"AuditPilot_AI_{t['engagement']['id']}", "generated_at": config.now(),
            "entity": t["engagement"]["entity"], "money_unit": "paise", **t}


COLUMNS = {
    "Fact_Invoices.csv": ("invoices", ["invoice_no", "invoice_date", "party_id", "taxable_paise", "tax_paise", "total_paise",
                                       "risk_score", "sample_status"]),
    "Dim_Customers.csv": ("customers", ["party_id", "name", "state_code", "is_related_party", "entity_risk_E"]),
    "Dim_Detectors.csv": ("detectors", ["detector_id", "name", "standard", "severity"]),
    "Fact_Findings_AJEs.csv": ("findings", ["finding_id", "invoice_no", "category", "status", "impact_paise", "aje_account",
                                            "aje_debit_paise", "aje_credit_paise"]),
}


def _csv(rows, cols):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r.get(c) is None else safe(r.get(c)) for c in cols])
    return buf.getvalue()


def dax(materiality_paise):
    cutoff = findings.CATEGORY["D3"].replace('"', '""')
    return f"""// AuditPilot AI measures. Every money column is integer paise; divide by 100 for rupees.
// Relationships: Fact_Invoices[party_id] -> Dim_Customers[party_id]; Fact_Findings_AJEs[invoice_no] -> Fact_Invoices[invoice_no].

Total Revenue = DIVIDE ( SUM ( Fact_Invoices[taxable_paise] ), 100 )

Materiality Threshold = DIVIDE ( {int(materiality_paise or 0)}, 100 )

Flagged Fraud Volume =
DIVIDE (
    CALCULATE ( SUM ( Fact_Invoices[total_paise] ), Fact_Invoices[risk_score] >= 60 ),
    100
)

Cut-off Error % =
DIVIDE (
    SUMX (
        FILTER ( VALUES ( Fact_Findings_AJEs[finding_id] ),
                 CALCULATE ( MAX ( Fact_Findings_AJEs[category] ) ) = "{cutoff}" ),
        CALCULATE ( MAX ( Fact_Findings_AJEs[impact_paise] ) )
    ),
    SUM ( Fact_Invoices[taxable_paise] )
)

RP Exposure % =
DIVIDE (
    CALCULATE ( SUM ( Fact_Invoices[taxable_paise] ), Dim_Customers[is_related_party] = 1 ),
    SUM ( Fact_Invoices[taxable_paise] )
)
"""


def package(engagement_id=None, role="audit_staff"):
    """-> (zip bytes, filename): the four CSVs (UTF-8 with BOM, opens cleanly in Excel) and measures.dax."""
    t = tables(engagement_id, role)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, (key, cols) in COLUMNS.items():
            z.writestr(name, "﻿" + _csv(t[key], cols))
        z.writestr("measures.dax", dax(t["engagement"]["materiality_paise"]))
    return buf.getvalue(), f"AuditPilot_PowerBI_{t['engagement']['id']}.zip"
