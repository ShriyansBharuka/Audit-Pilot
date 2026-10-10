"""Read-only data for the Audit Investigation Explorer (UI): risk history and evidence files per document.

Everything else the Explorer shows comes through the MCP tools (get_risk_graph, trace_sale, query_records,
list_audit_items, check_for_changes), so the UI respects the same permissions as any agent. These two reads
have no MCP tool; they open audit.db / pbc.db with the caller's role, so a client role is refused by db.connect.
"""
import json

from app import config, db

AUDIT_ROLES = ("audit_staff", "engagement_partner")


def _need(role):
    if role not in AUDIT_ROLES:
        raise PermissionError("PERMISSION_DENIED: the investigation explorer is for audit identities only")


def risk_history(role, object_type, object_id):
    """AuditGraph snapshots for one object, oldest first: [{run_id, at, A, E, R, C, band, reasons}] (05 §19.6)."""
    _need(role)
    with db.borrow("audit", role) as a:
        rows = a.execute("SELECT * FROM risk_snapshots WHERE object_type = ? AND object_id = ? ORDER BY at, run_id",
                         (object_type, object_id)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["reasons"] = json.loads(d.pop("reasons_json") or "[]")
        d["C"] = None if d["C"] is None else d["C"] / 1000
        out.append(d)
    return out


def evidence_for(role, doc_no):
    """Evidence requests about one document and every file the client submitted for them (hash, who, when)."""
    _need(role)
    with db.borrow("pbc", role) as p:
        reqs = [dict(r) for r in p.execute(
            "SELECT * FROM evidence_requests WHERE engagement_id = ? AND about_doc_no = ? ORDER BY requested_at",
            (config.ENGAGEMENT_ID, doc_no))]
        for r in reqs:
            r["submissions"] = [dict(s) for s in p.execute(
                "SELECT id, filename, mime, size, sha256, declared_json, submitted_by, submitted_at"
                " FROM submissions WHERE request_id = ? ORDER BY submitted_at", (r["id"],))]
    return reqs
