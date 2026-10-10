"""FastAPI REST API server for AuditPilot AI.

Exposes high-performance, well-typed REST APIs for the Next.js web application
while preserving and mounting the MCP server and existing SQLite databases.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app import cases, charts, config, db, erp, evidence, explain, explorer, findings, gateway, intake, ledger, memo, money, money_trail, notify, partner, powerbi, register, reports, risk_graph, sampling, trail, workpaper, yearend

app = FastAPI(
    title="AuditPilot AI API",
    version="1.0.0",
    description="Statutory Revenue Audit API for AuditPilot AI Next.js Application",
)

# Enable CORS for Next.js (port 3000 and any local dev origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_identity(auth_header: Optional[str] = Header(None, alias="Authorization")) -> Dict[str, Any]:
    """Resolve token from Authorization: Bearer <token> or identities.json."""
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED: missing Bearer token")
    token = auth_header[7:].strip()
    try:
        rec = partner.identity(token)
        return {"token": token, **rec}
    except LookupError:
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED: invalid token")


AUDIT_ROLES = ("audit_staff", "engagement_partner")
CLIENT_ROLES = ("sales", "warehouse", "accounts", "client_admin")


def require(*roles):
    """Dependency: the Bearer token's role must be one of `roles` (identity comes only from the token)."""
    def dep(auth_header: Optional[str] = Header(None, alias="Authorization")) -> Dict[str, Any]:
        who = _get_identity(auth_header)
        if who.get("role") not in roles:
            raise HTTPException(status_code=403, detail=f"PERMISSION_DENIED: role {who.get('role')} may not use this endpoint")
        return who
    return dep


AUDIT = Depends(require(*AUDIT_ROLES))
ANYONE = Depends(require(*AUDIT_ROLES, *CLIENT_ROLES))


# ---------------------------------------------------------------- Auth & Identities

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "entity": config.ENTITY_NAME,
        "engagement_id": config.ENGAGEMENT_ID,
        "now": config.now(),
        "today": config.today(),
    }


@app.get("/api/identities")
def list_identities():
    """Return available judge / demo identities for quick selection in login UI."""
    ids_file = Path(os.environ.get("IDENTITIES", "identities.json"))
    if not ids_file.exists():
        return []
    try:
        ids_dict = json.loads(ids_file.read_text(encoding="utf-8"))
        out = []
        demo = os.environ.get("DEMO_ROLE_SWITCHER") == "1"     # local demo only; the partner token is never listed
        for token, rec in ids_dict.items():
            out.append({
                "token": token if demo and rec.get("role") != "engagement_partner" else None,
                "principal": rec.get("principal"),
                "role": rec.get("role"),
                "name": rec.get("name", rec.get("principal")),
                "membership_no": rec.get("membership_no"),
            })
        return out
    except Exception as e:
        return []


class TokenLoginRequest(BaseModel):
    token: str


@app.post("/api/auth/token-login")
def token_login(req: TokenLoginRequest):
    tok = (req.token or "").strip()
    try:
        rec = partner.identity(tok)
        return {
            "token": tok,
            "principal": rec.get("principal"),
            "role": rec.get("role"),
            "name": rec.get("name", rec.get("principal")),
            "membership_no": rec.get("membership_no"),
        }
    except LookupError:
        raise HTTPException(status_code=401, detail="Unknown or invalid token.")


# ---------------------------------------------------------------- Audit Overview

@app.get("/api/audit/overview", dependencies=[AUDIT])
def get_audit_overview():
    """Engagement statistics, revenue tested, detector counts, risk bands."""
    eid = config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        eng = a.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone()
        if not eng:
            return {
                "has_engagement": False,
                "message": "No active engagement. Upload sales register to initialize.",
            }
        eng_dict = dict(eng)
        
        # Detector counts
        by_det = dict(a.execute("SELECT detector, count(*) FROM risk_hits WHERE engagement_id = ? GROUP BY detector ORDER BY detector", (eid,)).fetchall())
        by_code = dict(a.execute("SELECT code, count(*) FROM risk_hits WHERE engagement_id = ? GROUP BY code ORDER BY count(*) DESC LIMIT 20", (eid,)).fetchall())
        
        # Findings count by status
        findings_counts = dict(a.execute("SELECT status, count(*) FROM findings WHERE engagement_id = ? GROUP BY status", (eid,)).fetchall())
        
        # Samples counts
        samples_row = a.execute("SELECT count(*), sum(tested_at IS NOT NULL) FROM samples s JOIN sample_runs r ON r.id = s.run_id WHERE r.engagement_id = ?", (eid,)).fetchone()
        
        # Register count
        reg_count = a.execute("SELECT count(*) FROM register_rows WHERE submission_id = ?", (eng_dict.get("register_submission_id") or "",)).fetchone()[0]

    with db.borrow("erp", "system") as e:
        inv_count = e.execute("SELECT count(*) FROM invoices WHERE status = 'ISSUED'").fetchone()[0]
        cust_count = e.execute("SELECT count(*) FROM parties WHERE tags LIKE '%CUSTOMER%'").fetchone()[0]
        revenue_paise = e.execute("SELECT COALESCE(SUM(l.taxable_paise), 0) FROM invoices i JOIN invoice_lines l ON l.invoice_id = i.id WHERE i.status = 'ISSUED'").fetchone()[0]

    with db.borrow("pbc", "system") as p:
        evidence_counts = dict(p.execute("SELECT status, count(*) FROM evidence_requests WHERE engagement_id = ? GROUP BY status", (eid,)).fetchall())

    # Risk graph company risk (stored by the last AuditGraph run) + distinct flagged cycles from the D10 hits
    company_risk = risk_graph.company_band(eid) or {}
    with db.borrow("audit", "system") as a:
        cycles = {json.dumps([(json.loads(r[0] or "{}") or {}).get(k) for k in ("members", "flow")])
                  for r in a.execute("SELECT evidence_json FROM risk_hits WHERE engagement_id = ? AND detector = 'D10'"
                                     " AND code = 'CIRCULAR_FLOW'", (eid,))}
    company_risk["cycles_count"] = len(cycles - {"[null, null]"})
    
    return {
        "has_engagement": True,
        "engagement_id": eid,
        "entity_name": config.ENTITY_NAME,
        "period_start": eng_dict.get("period_start", config.PERIOD_START),
        "period_end": eng_dict.get("period_end", config.PERIOD_END),
        "framework": eng_dict.get("framework", config.FRAMEWORK),
        "status": eng_dict.get("status"),
        "materiality_paise": eng_dict.get("materiality_paise"),
        "materiality_formatted": money.fmt_inr(eng_dict.get("materiality_paise") or 0),
        "revenue_paise": revenue_paise,
        "revenue_formatted": money.fmt_inr(revenue_paise),
        "invoices_count": inv_count,
        "customers_count": cust_count,
        "register_rows_count": reg_count,
        "company_risk": company_risk,
        "detector_counts": by_det,
        "top_codes": by_code,
        "findings_counts": findings_counts,
        "samples_total": samples_row[0] if samples_row else 0,
        "samples_tested": (samples_row[1] or 0) if samples_row else 0,
        "evidence_requests": evidence_counts,
        "signed_by": eng_dict.get("signed_by"),
        "signed_at": eng_dict.get("signed_at"),
        "detectors": powerbi.detector_rows(),
    }


# ---------------------------------------------------------------- Transactions & 100% Population

@app.get("/api/audit/transactions", dependencies=[AUDIT])
def list_transactions(
    limit: int = 50,
    offset: int = 0,
    band: Optional[str] = None,
    detector: Optional[str] = None,
    search: Optional[str] = None,
):
    """100% population transactions table with risk scores, detector hits, and SoR matching."""
    eid = config.ENGAGEMENT_ID
    with db.borrow("erp", "system") as e, db.borrow("audit", "system") as a:
        # Load risk snapshots for invoices
        risk_map = {}
        for r in a.execute("SELECT object_id, R, band, reasons_json FROM risk_snapshots WHERE UPPER(object_type) = 'INVOICE'").fetchall():
            risk_map[r[0]] = {
                "score": r[1] // 1000 if r[1] is not None else 0,
                "band": r[2] or "LOW",
                "reasons": json.loads(r[3] or "[]"),
            }

        # Load detector hits by invoice_id
        hits_map = {}
        for r in a.execute("SELECT object_id, detector, code, severity FROM risk_hits WHERE engagement_id = ? AND UPPER(object_type) = 'INVOICE'", (eid,)).fetchall():
            hits_map.setdefault(r[0], []).append({
                "detector": r[1],
                "code": r[2],
                "severity": r[3],
            })

        # Query invoices
        query = (
            "SELECT i.id, i.invoice_no, i.invoice_date, i.supplier_gstin, i.buyer_gstin, "
            "p.name as party_name, (CASE WHEN p.tags LIKE '%RP%' OR p.tags LIKE '%DIRECTOR%' OR p.tags LIKE '%KMP%' OR p.tags LIKE '%RELATIVE%' THEN 1 ELSE 0 END) as is_related_party, i.irn, i.status, "
            "COALESCE(SUM(l.taxable_paise), 0) as taxable_paise, "
            "COALESCE(SUM(l.igst_paise + l.cgst_paise + l.sgst_paise), 0) as tax_paise, "
            "i.round_off_paise "
            "FROM invoices i "
            "JOIN parties p ON p.id = i.party_id "
            "LEFT JOIN invoice_lines l ON l.invoice_id = i.id "
            "WHERE i.status = 'ISSUED' "
        )
        params = []
        if search:
            query += "AND (i.invoice_no LIKE ? OR p.name LIKE ? OR i.buyer_gstin LIKE ?) "
            s = f"%{search}%"
            params.extend([s, s, s])
        
        query += "GROUP BY i.id ORDER BY i.invoice_date DESC, i.invoice_no DESC"
        rows = [dict(r) for r in e.execute(query, params).fetchall()]

        # Filter in memory by band or detector if requested
        result_rows = []
        for r in rows:
            inv_id = r["id"]
            rk = risk_map.get(inv_id, {"score": 10, "band": "LOW", "reasons": []})
            hits = hits_map.get(inv_id, [])
            
            if band and rk["band"] != band.upper():
                continue
            if detector and not any(h["detector"] == detector for h in hits):
                continue
                
            total_paise = r["taxable_paise"] + r["tax_paise"] + (r["round_off_paise"] or 0)
            result_rows.append({
                "id": inv_id,
                "invoice_no": r["invoice_no"],
                "invoice_date": r["invoice_date"],
                "party_name": r["party_name"],
                "buyer_gstin": r["buyer_gstin"],
                "is_related_party": bool(r["is_related_party"]),
                "taxable_amount": money.fmt_inr(r["taxable_paise"]),
                "taxable_paise": r["taxable_paise"],
                "total_amount": money.fmt_inr(total_paise),
                "total_paise": total_paise,
                "irn": r["irn"],
                "risk_score": rk["score"],
                "risk_band": rk["band"],
                "reasons": rk["reasons"],
                "detector_hits": hits,
            })

        total_count = len(result_rows)
        paged_rows = result_rows[offset : offset + limit]

        return {
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "items": paged_rows,
        }


@app.get("/api/audit/transactions/{invoice_no:path}", dependencies=[AUDIT])
def get_transaction_detail(invoice_no: str):
    """Full documentary trail for one transaction: invoice lines, EWB, LR/POD, credit notes, risk history."""
    with db.borrow("erp", "system") as e, db.borrow("audit", "system") as a, db.borrow("ext", "system") as x:
        inv = e.execute("SELECT * FROM invoices WHERE invoice_no = ? OR id = ?", (invoice_no, invoice_no)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        inv_dict = dict(inv)
        iid = inv_dict["id"]
        
        party = dict(e.execute("SELECT * FROM parties WHERE id = ?", (inv_dict["party_id"],)).fetchone())
        lines = [dict(r) for r in e.execute("SELECT l.*, it.name as item_name FROM invoice_lines l JOIN items it ON it.id = l.item_id WHERE invoice_id = ? ORDER BY line_no", (iid,)).fetchall()]
        
        # Movements (LR, POD)
        movements = [dict(r) for r in e.execute("SELECT m.* FROM movements m JOIN invoice_movements im ON im.movement_id = m.id WHERE im.invoice_id = ?", (iid,)).fetchall()]
        
        # E-Way Bills
        ewbs = [dict(r) for r in x.execute("SELECT * FROM ewaybills WHERE doc_no = ? AND supplier_gstin = ?", (inv_dict["invoice_no"], inv_dict["supplier_gstin"])).fetchall()]
        
        # Journals
        journals = [dict(r) for r in e.execute("SELECT j.*, jl.* FROM journals j JOIN journal_lines jl ON jl.journal_no = j.no WHERE j.source_id = ? OR jl.party_id = ? ORDER BY j.no", (iid, inv_dict["party_id"])).fetchall()]
        
        # Risk hits
        hits = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ? AND object_id = ?", (config.ENGAGEMENT_ID, iid)).fetchall()]
        
        # Evidence requests
        evidence_reqs = explorer.evidence_for("audit_staff", inv_dict["invoice_no"])
        
        # Formatted lines
        for l in lines:
            l["taxable_formatted"] = money.fmt_inr(l["taxable_paise"])
            l["total_tax_formatted"] = money.fmt_inr(l["igst_paise"] + l["cgst_paise"] + l["sgst_paise"])
            
        return {
            "invoice": inv_dict,
            "party": party,
            "lines": lines,
            "movements": movements,
            "ewaybills": ewbs,
            "journals": journals,
            "risk_hits": hits,
            "evidence": evidence_reqs,
        }


# ---------------------------------------------------------------- Risk Graph & Circular Trading

@app.get("/api/audit/risk-graph", dependencies=[AUDIT])
def get_risk_graph_data():
    """Graph structure: entity nodes, flows, and circular cycles."""
    eid = config.ENGAGEMENT_ID
    g = risk_graph.build(eid)
    cycles = g.get("cycles", [])
    
    # Enrich cycles for UI visualization
    enriched_cycles = []
    for c in cycles:
        members = c.get("members", [])
        amount = c.get("circular_paise", 0)
        enriched_cycles.append({
            "nodes": members,
            "amount_paise": amount,
            "amount_formatted": money.fmt_inr(amount),
            "invoices": list(c.get("residuals", {}).keys()),
            "span_days": c.get("span_days", 0),
            "type": c.get("flow", "CIRCULAR_GOODS"),
        })

    # Nodes & Links formatting for D3 / Vis network
    nodes = []
    seen_nodes = set()
    links = []

    with db.borrow("erp", "system") as e:
        parties = {r[0]: dict(r) for r in e.execute("SELECT * FROM parties").fetchall()}

    for c in enriched_cycles:
        for node in c["nodes"]:
            if node not in seen_nodes:
                seen_nodes.add(node)
                p = parties.get(node, {})
                tags = p.get("tags") or ""
                nodes.append({
                    "id": node,
                    "name": p.get("name", node),
                    "is_rp": "RP" in tags or "DIRECTOR" in tags or "KMP" in tags or "RELATIVE" in tags,
                    "group": "circular",
                    "state": p.get("state_code", ""),
                })
        c_nodes = c["nodes"]
        for i in range(len(c_nodes)):
            src = c_nodes[i]
            tgt = c_nodes[(i + 1) % len(c_nodes)]
            links.append({
                "source": src,
                "target": tgt,
                "amount": c["amount_formatted"],
                "type": "circular",
            })

    # Add primary company node
    nodes.insert(0, {
        "id": "SELF",
        "name": config.ENTITY_NAME,
        "is_rp": False,
        "group": "audited_entity",
        "state": "27",
    })

    return {
        "company": g.get("company", {}),
        "cycles": enriched_cycles,
        "graph": {
            "nodes": nodes,
            "links": links,
        },
    }


# ---------------------------------------------------------------- Findings & Partner Sign-off

@app.get("/api/audit/findings", dependencies=[AUDIT])
def list_findings(status: Optional[str] = None):
    """List findings for the review queue."""
    eid = config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        query = "SELECT * FROM findings WHERE engagement_id = ?"
        params = [eid]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY gross_impact_paise DESC, id"
        rows = [dict(r) for r in a.execute(query, params).fetchall()]

    for r in rows:
        r["gross_impact_formatted"] = money.fmt_inr(r.get("gross_impact_paise") or 0)
        r["taxable_impact_formatted"] = money.fmt_inr(r.get("taxable_impact_paise") or 0)
        r["doc_refs"] = json.loads(r.get("doc_refs_json") or "[]")
        r["proposed_aje"] = json.loads(r.get("proposed_aje_json") or "null")

    return rows


class DecideFindingRequest(BaseModel):
    decision: str  # CONFIRM, REJECT, MODIFY
    note: str
    taxable_impact_paise: Optional[int] = None
    proposed_aje: Optional[List[Dict[str, Any]]] = None


@app.post("/api/audit/findings/{finding_id}/decide")
def decide_finding_endpoint(
    finding_id: str,
    req: DecideFindingRequest,
    auth_header: Optional[str] = Header(None, alias="Authorization"),
):
    """Partner decision with mandatory comment. Token must belong to engagement_partner."""
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED")
    token = auth_header[7:].strip()
    try:
        res = partner.decide_finding(
            token=token,
            finding_id=finding_id,
            decision=req.decision,
            note=req.note,
            taxable_impact_paise=req.taxable_impact_paise,
            proposed_aje=req.proposed_aje,
        )
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/audit/signoff-blockers", dependencies=[AUDIT])
def get_signoff_blockers():
    """List of reasons blocking the engagement partner's final sign-off."""
    return partner.blockers()


class SignOffRequest(BaseModel):
    statement: str
    password: str


@app.post("/api/audit/sign-off")
def execute_sign_off(
    req: SignOffRequest,
    auth_header: Optional[str] = Header(None, alias="Authorization"),
):
    """Final partner sign-off."""
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED")
    token = auth_header[7:].strip()
    try:
        rec = partner._partner(token)
        res = findings.sign_off(config.ENGAGEMENT_ID, rec, req.statement, req.password)
        trail.trail(rec["principal"], rec["role"], "partner.sign_off", {"engagement_id": config.ENGAGEMENT_ID}, "OK", res, transport="UI")
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------- Evidence & PBC Requests

@app.get("/api/audit/evidence/requests", dependencies=[ANYONE])
def list_evidence_requests(status: Optional[str] = None):
    """List evidence requests."""
    eid = config.ENGAGEMENT_ID
    with db.borrow("pbc", "system") as p:
        query = "SELECT * FROM evidence_requests WHERE engagement_id = ?"
        params = [eid]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY requested_at DESC"
        reqs = [dict(r) for r in p.execute(query, params).fetchall()]

        for r in reqs:
            subs = [dict(s) for s in p.execute("SELECT id, filename, mime, size, sha256, submitted_by, submitted_at FROM submissions WHERE request_id = ? ORDER BY submitted_at", (r["id"],)).fetchall()]
            r["submissions"] = subs

    return reqs


@app.post("/api/audit/evidence/submit")
async def submit_evidence_file(
    request_id: str = Form(...),
    file: UploadFile = File(...),
    who: Dict[str, Any] = Depends(require(*CLIENT_ROLES)),
):
    """Client uploads evidence for a request; the server computes sha256 and stores the bytes verbatim."""
    content = await file.read()
    filename = file.filename or "evidence.bin"
    sid = intake.submit("EVIDENCE", content, filename, who["principal"], request_id=request_id)
    return intake.on_client_upload(sid)              # EVIDENCE_RECEIVED event (n8n W3) + next_steps


# ---------------------------------------------------------------- SHAP Explainability

@app.get("/api/audit/shap-summary", dependencies=[AUDIT])
def get_shap_summary(min_risk: int = 30):
    """Global SHAP importance: mean |attribution| per risk code over the invoices scored >= min_risk."""
    return explain.summary(min_r=min_risk)


@app.get("/api/audit/shap/{invoice_no:path}", dependencies=[AUDIT])
def get_shap_explanation(invoice_no: str):
    """Exact Shapley attribution of the invoice's AuditGraph risk score (app/explain.py): every risk hit and the
    customer's entity risk E are players of the real scoring formula; the attributions sum to the score."""
    x = explain.explain_invoice(invoice_no)
    if x is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND: no invoice with that number or id")
    pos = [c for c in x["contributions"] if c["value"] > 0]
    neg = [c for c in x["contributions"] if c["value"] < 0]
    return {**x,
            "shap_values": {c["feature"]: c["value"] for c in x["contributions"]},
            "top_positive": [{"feature": c["feature"], "value": c["value"]} for c in pos[:3]],
            "top_negative": [{"feature": c["feature"], "value": c["value"]} for c in neg[:3]],
            "detector_hits_count": sum(1 for c in x["contributions"] if c["kind"] == "hit")}


@app.get("/api/money-trail/{object_id:path}", dependencies=[AUDIT])
def get_money_trail(object_id: str, hops: int = Query(2, ge=1, le=3)):
    """vault/13 §6: {root, nodes, edges, numbers, cycles}. Edges carry source BANK/PORTAL/BOOKS/IDENTITY and status
    VERIFIED/CLAIMED/INFERRED; numbers never attribute money downstream."""
    try:
        return money_trail.trace(object_id, hops=hops)
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


class CaseAction(BaseModel):
    action: str
    note: Optional[str] = None
    doc_kind: Optional[str] = None
    aje_lines: Optional[List[Dict[str, Any]]] = None      # paise: [{account_code, party_id?, dr_paise, cr_paise}]


@app.get("/api/cases", dependencies=[AUDIT])
def get_cases(status: Optional[str] = None, band: Optional[str] = None, limit: int = Query(25, ge=1, le=100),
              offset: int = Query(0, ge=0)):
    """vault/13 §6: risk-ranked audit cases with the three numbers (recorded / verified / potentially affected)."""
    return cases.list_cases(status=status, band=band, limit=limit, offset=offset)


@app.get("/api/cases/{case_id}", dependencies=[AUDIT])
def get_case_detail(case_id: str):
    try:
        return cases.get_case(case_id)
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@app.post("/api/cases/{case_id}/action")
def post_case_action(case_id: str, body: CaseAction, who: Dict[str, Any] = Depends(require("audit_staff"))):
    """audit_staff only; identity from the token. PROPOSE_ADJUSTMENT creates a PROPOSED finding (the partner decides)."""
    try:
        out = cases.act(case_id, body.action, body.note, who["principal"], who["role"], doc_kind=body.doc_kind,
                        aje_lines=body.aje_lines)
        trail.trail(who["principal"], who["role"], "cases.act", {"case_id": case_id, "action": body.action}, "OK",
                    {"event": out["event"]["id"]}, transport="UI")
        return out
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    except PermissionError as ex:
        raise HTTPException(status_code=403, detail=str(ex))
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@app.post("/api/cases/{case_id}/investigate")
def post_case_investigate(case_id: str, demo: bool = False, who: Dict[str, Any] = Depends(require("audit_staff"))):
    """MT-5: multi-agent investigation (risk, evidence, money-flow, reporting) saved as a PROPOSED case event.
    409 when the LLM is off or the CostMeter cap is hit."""
    import asyncio
    from app import investigator
    try:
        cases.get_case(case_id)
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    ok, why = investigator.ready()
    if not ok:
        raise HTTPException(status_code=409, detail=f"LLM_OFF: {why}")
    try:
        out = asyncio.run(investigator.investigate_case(case_id, demo=demo))
    except RuntimeError as ex:
        raise HTTPException(status_code=409, detail=str(ex))
    trail.trail(who["principal"], who["role"], "investigator.investigate_case", {"case_id": case_id}, "OK",
                {"event": out["event"]["id"], "usd": out["usd"]}, transport="UI")
    return out


@app.get("/api/yearend/timeline", dependencies=[AUDIT])
def get_yearend_timeline(party_id: Optional[str] = None):
    """vault/13 §6: monthly sales / receipts / credit notes / open exceptions and the band, period + 2 months."""
    try:
        return yearend.timeline(party_id=party_id)
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@app.get("/api/yearend/march-april", dependencies=[AUDIT])
def get_yearend_march_april():
    """Every last-month document with a post-period credit note, cancellation, dispatch / delivery, late keying or bill."""
    try:
        return yearend.march_april_links()
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@app.post("/api/yearend/freeze")
def post_yearend_freeze(who: Dict[str, Any] = Depends(require("audit_staff"))):
    """Year-end freeze: full analytics run + AuditGraph snapshot + anchor on both chain heads."""
    try:
        out = yearend.freeze()
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    trail.trail(who["principal"], who["role"], "yearend.freeze", {}, "OK", {"anchor": out["anchor"]["id"]}, transport="UI")
    return out


def _report(build, format):
    if format not in ("json", "md", "html"):
        raise HTTPException(status_code=400, detail="INVALID_ARGUMENT: format is json, md or html")
    try:
        r = build()
    except LookupError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    out = reports.render(r, format)
    if format == "md":
        return Response(out, media_type="text/markdown; charset=utf-8")
    if format == "html":
        return Response(out, media_type="text/html; charset=utf-8")
    return out


@app.get("/api/reports/continuous", dependencies=[AUDIT])
def get_report_continuous(format: str = "json"):
    """vault/13 §6 Report A: unreconciled, missing evidence, control failures, risk trend, open alerts. DRAFT until sign-off."""
    return _report(reports.continuous, format)


@app.get("/api/reports/year-end", dependencies=[AUDIT])
def get_report_year_end(format: str = "json", ai: bool = False):
    """vault/13 §6 Report B: risk register, counterparty exposure, funds flow, investigated cases, March-April, AJEs,
    unresolved questions. ai=true adds a labelled AI-drafted summary when the LLM is on. Never an audit opinion."""
    return _report(lambda: reports.year_end(ai_summary=ai), format)


@app.get("/api/audit/analytics/charts", dependencies=[AUDIT])
def get_analytics_charts():
    """EX-2: daily volume (z-scores, period-end window), Benford first digits (chi-square), risk histogram + scatter."""
    return charts.charts()


# ---------------------------------------------------------------- Deliverables & Exports

def _fresh_deliverables(eid):
    """Same order as the generate_deliverables MCP tool: D11 first, every serious hit a PROPOSED finding."""
    evidence.check_for_changes(eid)
    findings.from_hits(eid)


@app.get("/api/audit/deliverables/workpaper", dependencies=[AUDIT])
def download_workpaper():
    """The 4-sheet workpaper (xlsx), DRAFT until the partner signs off."""
    eid = config.ENGAGEMENT_ID
    _fresh_deliverables(eid)
    wp = workpaper.build(eid)
    return Response(content=Path(wp["path"]).read_bytes(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={eid}_workpaper.xlsx",
                             "X-Content-SHA256": wp["sha256"]})


@app.get("/api/audit/deliverables/memo", dependencies=[AUDIT])
def get_findings_memo():
    """The findings memo (markdown), DRAFT until the partner signs off."""
    eid = config.ENGAGEMENT_ID
    _fresh_deliverables(eid)
    mm = memo.build(eid)
    return {"memo": Path(mm["path"]).read_text(encoding="utf-8"), "sha256": mm["sha256"]}


# ---------------------------------------------------------------- Audit Trail (Hash-chained)

@app.get("/api/audit/trail", dependencies=[AUDIT])
def get_audit_trail(limit: int = 50, offset: int = 0):
    """Retrieve hash-chained audit trail entries."""
    with db.borrow("audit", "system") as a:
        total = a.execute("SELECT count(*) FROM audit_trail").fetchone()[0]
        rows = [dict(r) for r in a.execute("SELECT * FROM audit_trail ORDER BY seq DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()]
        
    for r in rows:
        r["args"] = json.loads(r.get("args_json") or "{}")
        r["result"] = json.loads(r.get("result_json") or "null")

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": rows,
    }


# ---------------------------------------------------------------- Power BI & Integrations

@app.get("/api/integrations/powerbi", dependencies=[AUDIT])
@app.get("/api/v1/powerbi/feed", dependencies=[AUDIT])
def get_powerbi_dataset():
    """Power BI "Web" source: invoices, customers, detectors and findings/AJEs, money in integer paise (EX-1)."""
    return powerbi.feed()


@app.get("/api/integrations/powerbi/package", dependencies=[AUDIT])
def get_powerbi_package():
    """Zip: Fact_Invoices, Dim_Customers, Dim_Detectors, Fact_Findings_AJEs (CSV, paise) + measures.dax."""
    data, name = powerbi.package()
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/integrations/n8n/events", dependencies=[AUDIT])
def n8n_events(limit: int = 20):
    """The real event feed n8n receives (03 #38 events): what was emitted, and whether the signed webhook was
    delivered (notified_at). Workflows run in n8n; this app only emits events (n8n/README.md)."""
    with db.borrow("audit", "system") as a:
        rows = [dict(r) for r in a.execute("SELECT id, kind, at, notified_at FROM events ORDER BY id DESC LIMIT ?",
                                           (min(max(limit, 1), 100),))]
    return {"webhook_configured": bool(config.N8N_WEBHOOK_URL), "events": rows,
            "workflows": ["W1 register uploaded -> notify", "W2 samples selected -> evidence request + reminders",
                          "W3 evidence received -> test_sample", "W4 schedule -> analytics + changes + integrity"]}
