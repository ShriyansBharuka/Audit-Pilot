"""Audit MCP tools (04 §4 #30-46) + the /files/<key> download route.

Audit identities read the client's books through read-only handles (db.connect: mode=ro + query_only); everything
they write lives in audit.db (or pbc.db requests). Conclusions are always PROPOSED: only the human partner, in the
web UI, confirms or signs off. Reasons cite ids; client text is returned under client_data.
"""
import json
import secrets
import sqlite3
from collections import Counter
from datetime import datetime, timedelta

from app import (analytics, config, db, evidence, findings, intake, ledger, memo, money_trail, register, risk_graph,
                 sampling, workpaper)
from app import gateway
from app.gateway import ToolError, tool
from app.toolkit import call, clean, inr, limit_of, money_in, offset_of, page, paise, result, scrub, steps

AUD = ("audit_staff",)
AUD_ORC = ("audit_staff", "orchestrator")
EID = lambda: config.ENGAGEMENT_ID


def _eng(a):
    return a.execute("SELECT * FROM engagements WHERE id = ?", (EID(),)).fetchone()


def _is_stub(mod):
    return getattr(mod, "STUB", False)


def _need_engagement(a):
    eng = _eng(a)
    if eng is None:
        raise ToolError("PRECONDITION_FAILED: no engagement yet; it opens when the client uploads the sales register "
                        "(upload_sales_register). Check again with get_engagement_status.")
    return eng

# ---------------------------------------------------------------- hub

@tool(*AUD_ORC, read_only=True)
def get_engagement_status() -> dict:
    """The auditor's hub: engagement and period, uploads (register / RP list), risk hits by detector, samples and
    evidence-request status, stale samples, integrity, company risk band and review state, with the next steps."""
    def go(who, role):
        with db.borrow("audit", role) as a:
            eng = _eng(a)
            if eng is None:
                return result({"engagement": None, "message": "No client upload yet. The engagement opens when the client "
                               "uploads the sales register."},
                              next_steps=steps(("list_audit_items", {"kind": "events"}, "watch for the upload event")))
            by_det = dict(a.execute("SELECT detector, count(*) FROM risk_hits WHERE engagement_id = ? GROUP BY detector"
                                    " ORDER BY detector", (EID(),)).fetchall())
            top_codes = dict(a.execute("SELECT code, count(*) n FROM risk_hits WHERE engagement_id = ? GROUP BY code"
                                       " ORDER BY n DESC LIMIT 15", (EID(),)).fetchall())
            runs = [dict(r) for r in a.execute("SELECT id, kind, size, run_at FROM sample_runs WHERE engagement_id = ?"
                                               " ORDER BY run_at", (EID(),))]
            tested = a.execute("SELECT count(*), sum(tested_at IS NOT NULL) FROM samples s JOIN sample_runs r ON"
                               " r.id = s.run_id WHERE r.engagement_id = ?", (EID(),)).fetchone()
            f_status = dict(a.execute("SELECT status, count(*) FROM findings WHERE engagement_id = ? GROUP BY status",
                                      (EID(),)).fetchall())
            reg_rows = a.execute("SELECT count(*) FROM register_rows WHERE submission_id = ?",
                                 (eng["register_submission_id"] or "",)).fetchone()[0]
        with db.borrow("pbc", role) as p:
            reqs = dict(p.execute("SELECT status, count(*) FROM evidence_requests WHERE engagement_id = ? GROUP BY status",
                                  (EID(),)).fetchall())
        status = {"engagement_id": eng["id"], "entity": eng["entity_name"], "framework": eng["framework"],
                  "period_start": eng["period_start"], "period_end": eng["period_end"], "status": eng["status"],
                  "materiality_paise": eng["materiality_paise"], "register_submission": eng["register_submission_id"],
                  "register_rows": reg_rows, "rp_list_submission": eng["rp_submission_id"],
                  "risk_hits_by_detector": by_det, "top_codes": top_codes, "sample_runs": runs,
                  "samples": {"total": tested[0], "tested": tested[1] or 0}, "evidence_requests": reqs,
                  "findings": f_status, "signed_by": eng["signed_by"]}
        if not _is_stub(evidence):
            ch = evidence.check_for_changes(EID())
            status["stale_samples"] = len(ch.get("stale_samples", []))
            status["integrity_ok"] = evidence.verify_integrity(EID()).get("ok")
        status["company_risk"] = risk_graph.company_band(EID())     # the latest AuditGraph flag (run_analytics)
        nxt = []
        if eng["register_submission_id"] and "D0" not in by_det:
            nxt.append(("reconcile_register_to_system", {}, "every register vs books difference"))
        if not any(d not in ("D0", "D1", "D2") for d in by_det):
            nxt.append(("run_analytics", {}, "100% population detectors D3-D14"))
        if not runs:
            nxt.append(("select_samples", {"kind": "sales_tod"}, "risk-based Sales TOD (starts testing)"))
        elif tested[0] and (tested[1] or 0) < tested[0]:
            nxt.append(("test_sample", {"run_id": runs[0]["id"], "sample_no": 1}, "test samples as evidence arrives"))
        nxt.append(("list_audit_items", {"kind": "risk_hits"}, "the exceptions found so far"))
        return result(status, next_steps=steps(*nxt))
    return call(go)


@tool(*AUD)
def configure_engagement(period_end: str | None = None, period_start: str | None = None, framework: str | None = None,
                         materiality: str | None = None, performance_materiality: str | None = None,
                         trivial: str | None = None) -> dict:
    """Set the period, framework (IND_AS | AS) and materiality (rupee strings; SA 320) before testing starts.
    Defaults: FY 2025-26, Ind AS; materiality defaults to 0.5% of revenue when findings are evaluated. Example:
    configure_engagement(period_end='2026-03-31', materiality='8500000.00')"""
    def go(who, role):
        intake.ensure_engagement()
        sets = {}
        for k, v in (("period_end", period_end), ("period_start", period_start)):
            if v:
                datetime.strptime(v, "%Y-%m-%d")
                sets[k] = v
        if framework:
            if framework not in ("IND_AS", "AS"):
                raise ToolError("INVALID_ARGUMENT: framework is IND_AS or AS")
            sets["framework"] = framework
        for k, v in (("materiality_paise", materiality), ("performance_materiality_paise", performance_materiality),
                     ("trivial_paise", trivial)):
            if v is not None:
                sets[k] = paise(v, k.replace("_paise", ""))
        if not sets:
            raise ToolError("INVALID_ARGUMENT: pass at least one of period_end, period_start, framework, materiality, "
                            "performance_materiality, trivial")
        with db.borrow("audit", role) as a, db.tx(a):
            eng = _need_engagement(a)
            if eng["testing_started_seq"] is not None:
                raise ToolError("PRECONDITION_FAILED: testing has started (samples selected); the period and materiality"
                                " are frozen for this engagement")
            a.execute(f"UPDATE engagements SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?", (*sets.values(), EID()))
        return result({"engagement_id": EID(), "updated": sorted(sets)},
                      next_steps=steps(("get_engagement_status", {}, "confirm the settings")))
    return call(go)


@tool(*AUD, read_only=True)
def get_workpaper_sheet(sheet: str = "sales_register", limit: int = 25, cursor: str | None = None) -> dict:
    """Page through a workpaper sheet: sales_register (the client's register verbatim + auditor columns SoR_Match,
    SoR_Doc_Id, RP_Status, Risk_Codes), sales_tod, cutoff_tod or cn_tod (the selected samples with reasons and test
    results). The full workbook comes from generate_deliverables."""
    def go(who, role):
        meta, rows = workpaper.sheet_rows(EID(), sheet)
        items, nxt = page(rows, limit, cursor)
        if sheet == "sales_register":
            items = [{"row_no": r["row_no"], "auditor": r["auditor"],
                      "client_data": {"cells": [clean(c.get("v") if isinstance(c.get("v"), str) else c.get("v"))
                                                for c in r["cells"]]}} for r in items]
        return result({"sheet": sheet, "rows": len(rows), **meta}, items, nxt,
                      steps(("generate_deliverables", {}, "the formatted 4-sheet workbook")))
    return call(go)


def _hit_item(h):
    ev = h.get("evidence") if "evidence" in h else json.loads(h.get("evidence_json") or "null")
    out = {k: h[k] for k in ("detector", "code", "object_type", "object_id", "severity", "impact_paise", "reason")}
    if "id" in h:
        out["id"] = h["id"]
    out["impact"] = inr(h["impact_paise"] or 0)
    out["client_data"] = {"evidence": clean(json.dumps(ev, default=str), 1200)} if ev else {}
    return out


@tool(*AUD)
def reconcile_register_to_system(limit: int = 25, cursor: str | None = None) -> dict:
    """D0: compare the uploaded register with the system of record row by row. Every difference is a risk hit
    (NOT_IN_SOR, MISSING_FROM_REGISTER, DUPLICATE_ROW, CANCELLED_BUT_LISTED, DATE_DIFF, FY_DIFF, CUSTOMER_DIFF,
    GSTIN_DIFF, TAXABLE_DIFF, TAX_DIFF, TOTAL_DIFF, FORMAT_ONLY, TIEOUT_RESIDUE) with a plain reason and ₹ impact."""
    def go(who, role):
        hits = sorted(register.reconcile(EID()), key=lambda h: (-h["severity"], -(h["impact_paise"] or 0)))
        items, nxt = page([_hit_item(h) for h in hits], limit, cursor)
        return result({"differences": len(hits), "by_code": dict(Counter(h["code"] for h in hits)),
                       "impact_total": inr(sum(h["impact_paise"] or 0 for h in hits if h["code"] != "TIEOUT_RESIDUE"))},
                      items, nxt, steps(("run_analytics", {}, "the 100% population detectors"),
                                        ("trace_sale", {"invoice": "G2/0001/25"}, "drill into one document")))
    return call(go)


@tool(*AUD_ORC)
def run_analytics(detectors: list[str] | None = None, incremental: bool = False) -> dict:
    """Run the population procedures over 100% of the books and portals (D1-D7, D9, D10, D13, D14; default all) and
    write risk hits with plain-language reasons. Returns counts by detector/code and the top 20."""
    def go(who, role):
        r = analytics.run_all(EID(), detectors=detectors, incremental=incremental)
        top = [_hit_item(h) for h in r.get("top", [])]
        return result({"run_id": r.get("run_id"), "counts": r.get("counts", {}), "company_risk": r.get("company")},
                      top, None,
                      steps(("select_samples", {"kind": "sales_tod"}, "risk-based samples (KEY stratum = these hits)"),
                            ("list_audit_items", {"kind": "risk_hits", "filters": {"min_severity": 4}}, "all serious hits")))
    return call(go)


@tool(*AUD)
def select_samples(kind: str = "sales_tod", size: int = 30, seed: str | None = None) -> dict:
    """Select samples: kind sales_tod (25-35, risk-based: KEY hits, high value, related parties, PPS for the rest),
    cutoff (last 10 before / first 15 after the period end + D3/D13 hits) or credit_note. The seed is random and
    recorded unless you pass one; every pick carries a reason. The FIRST call starts testing (anchor + snapshots)
    and sends evidence requests to the client automatically. Example: select_samples(kind='cutoff')"""
    def go(who, role):
        r = sampling.select(EID(), kind, size=size, seed=seed, actor=who)
        items = [scrub(i) for i in r.get("items", [])]
        return result({k: r.get(k) for k in ("run_id", "kind", "seed", "size", "population", "strata", "requests_sent")},
                      items[:100], None, r.get("next_steps") or steps(
                          ("reproduce_selection", {"run_id": r.get("run_id")}, "prove the selection is reproducible")))
    return call(go)


@tool(*AUD, read_only=True)
def reproduce_selection(run_id: str) -> dict:
    """Re-run a sample selection on its frozen population with its stored seed -> {identical, diff}."""
    return call(lambda who, role: result(sampling.reproduce(run_id)))


@tool(*AUD_ORC)
def test_sample(run_id: str, sample_no: int, note: str | None = None) -> dict:
    """Test one sample against the books, the portals and the client's evidence (D8 + the Fig. 2 attributes:
    amount, party, sales GL, period, tax). Proposes a conclusion; your note never changes a result."""
    def go(who, role):
        r = evidence.test_sample(run_id, sample_no, who, note)
        return result({k: r.get(k) for k in ("run_id", "sample_no", "conclusion_proposed", "attributes")},
                      exceptions=r.get("exceptions", []), next_steps=r.get("next_steps", []))
    return call(go)


@tool(*AUD_ORC, read_only=True)
def check_for_changes(limit: int = 25, cursor: str | None = None) -> dict:
    """D11: every client change since testing started, field by field (who, role, tool, when), and the samples it
    makes STALE; also edits made outside the application and back-dated insertions."""
    def go(who, role):
        r = evidence.check_for_changes(EID())
        items, nxt = page(r.get("changes", []), limit, cursor)
        return result({"changes": len(r.get("changes", [])), "stale_samples": r.get("stale_samples", [])},
                      [scrub(i) for i in items], nxt,
                      steps(("test_sample", {"run_id": "…", "sample_no": 1}, "re-test a stale sample")))
    return call(go)


@tool(*AUD_ORC, read_only=True)
def verify_integrity() -> dict:
    """D12: recompute the erp_log and audit_trail hash chains, check every anchor, compare current records with their
    last logged image (edits outside the application) and Dr = Cr per journal."""
    return call(lambda who, role: result(evidence.verify_integrity(EID())))


def _next_finding_id(a):
    r = a.execute("SELECT id FROM findings WHERE id >= 'F-0' AND id < 'F-:' ORDER BY id DESC LIMIT 1").fetchone()
    return f"F-{(int(r[0][2:]) if r else 0) + 1:03d}"


@tool(*AUD)
def propose_finding(category: str, title: str, explanation: str, doc_refs: list[str] | None = None,
                    taxable_impact: str = "0", tax_impact: str = "0", affected_fy: str | None = None,
                    standards: str | None = None, aje_lines: list[dict] | None = None, confidence: str = "MEDIUM",
                    detector: str | None = None, code: str | None = None) -> dict:
    """Record your own finding (status PROPOSED; only the engagement partner confirms). aje_lines: balanced
    [{account_code, party_id?, debit | credit (rupee strings)}] or omit for disclosure-only. Example:
    propose_finding(category='Cut-off', title='Sale recorded before dispatch', explanation='…', doc_refs=['INV-000391'],
    taxable_impact='1559322.00', affected_fy='2025-26', aje_lines=[{'account_code': 'SALES', 'debit': '1559322.00'},
    {'account_code': 'CONTRACT_LIABILITY', 'credit': '1559322.00'}])"""
    def go(who, role):
        if confidence not in ("HIGH", "MEDIUM", "LOW"):
            raise ToolError("INVALID_ARGUMENT: confidence is HIGH, MEDIUM or LOW")
        lines = money_in(aje_lines) if aje_lines else None
        if lines:
            with db.borrow("erp", role) as e:
                ledger.check_lines(e, lines)              # read-only check: balanced, accounts exist, party on DEBTORS
        t, x = paise(taxable_impact, "taxable_impact") or 0, paise(tax_impact, "tax_impact") or 0
        with db.borrow("audit", role) as a, db.tx(a):
            _need_engagement(a)
            fid = _next_finding_id(a)
            a.execute("INSERT INTO findings(id, engagement_id, detector, code, category, title, explanation, standards,"
                      " doc_refs_json, taxable_impact_paise, tax_impact_paise, gross_impact_paise, affected_fy, confidence,"
                      " proposed_aje_json, status, prepared_by, prepared_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
                      "'PROPOSED',?,?)", (fid, EID(), detector, code, category, title, explanation, standards,
                                         json.dumps(doc_refs or []), t, x, t + x, affected_fy, confidence,
                                         json.dumps(lines) if lines else None, who, config.now()))
        return result({"finding_id": fid, "status": "PROPOSED", "gross_impact": inr(t + x)},
                      next_steps=steps(("submit_for_partner_review", {}, "when testing is complete")))
    return call(go)


@tool(*AUD)
def add_auditor_note(target_type: str, target_id: str, note: str) -> dict:
    """Attach a note to a sample ('<run_id>#<sample_no>'), a finding (F-001) or a risk hit (its id). Notes never
    change a result."""
    def go(who, role):
        stamp = f"[{config.now()} {who}] {note}"
        with db.borrow("audit", role) as a, db.tx(a):
            if target_type == "sample":
                run_id, _, n = target_id.partition("#")
                cur = a.execute("UPDATE samples SET notes = COALESCE(notes || char(10), '') || ? WHERE run_id = ?"
                                " AND sample_no = ?", (stamp, run_id, int(n or 0)))
            elif target_type in ("finding", "risk_hit"):
                table, key = ("findings", "id") if target_type == "finding" else ("risk_hits", "id")
                row = a.execute(f"SELECT evidence_json FROM {table} WHERE {key} = ?", (target_id,)).fetchone()
                if row is None:
                    raise ToolError(f"NOT_FOUND: no {target_type} with that id")
                ev = json.loads(row[0] or "null")
                ev = ev if isinstance(ev, dict) else {"evidence": ev}
                ev.setdefault("auditor_notes", []).append(stamp)
                cur = a.execute(f"UPDATE {table} SET evidence_json = ? WHERE {key} = ?", (json.dumps(ev), target_id))
            else:
                raise ToolError("INVALID_ARGUMENT: target_type is sample, finding or risk_hit")
            if cur.rowcount == 0:
                raise ToolError(f"NOT_FOUND: no {target_type} with that id")
        return result({"target_type": target_type, "target_id": target_id, "noted": True})
    return call(go)


_KINDS = ("risk_hits", "findings", "samples", "selections", "changes", "trail", "events")


@tool(*AUD_ORC, read_only=True)
def list_audit_items(kind: str, filters: dict | None = None, limit: int = 25, cursor: str | None = None) -> dict:
    """Page through audit records. kind: risk_hits (filters detector, code, object_id, min_severity), findings
    (status), samples (run_id), selections, changes, trail (principal, tool, outcome), events. The orchestrator may
    list events only. Example: list_audit_items(kind='risk_hits', filters={'detector': 'D3', 'min_severity': 4})"""
    def go(who, role):
        if kind not in _KINDS:
            raise ToolError(f"INVALID_ARGUMENT: kind must be one of {', '.join(_KINDS)}")
        if role == "orchestrator" and kind != "events":
            raise ToolError("PERMISSION_DENIED: the orchestrator may list events only (list_audit_items(kind='events'))")
        f = filters or {}
        n, off = limit_of(limit), offset_of(cursor)
        if kind == "changes":
            ch = evidence.check_for_changes(EID()).get("changes", [])
            items, nxt = page(ch, limit, cursor)
            return result({"kind": kind, "total": len(ch)}, [scrub(i) for i in items], nxt)
        q = {"risk_hits": ("SELECT * FROM risk_hits WHERE engagement_id = ?", "severity DESC, impact_paise DESC, id",
                           {"detector": "detector = ?", "code": "code = ?", "object_id": "object_id = ?",
                            "min_severity": "severity >= ?"}),
             "findings": ("SELECT * FROM findings WHERE engagement_id = ?", "id", {"status": "status = ?"}),
             "samples": ("SELECT s.* FROM samples s JOIN sample_runs r ON r.id = s.run_id WHERE r.engagement_id = ?",
                         "s.run_id, s.sample_no", {"run_id": "s.run_id = ?", "stratum": "s.stratum = ?"}),
             "selections": ("SELECT id, kind, seed, size, as_of_seq, population_sha256, algo_version, run_by, run_at"
                            " FROM sample_runs WHERE engagement_id = ?", "run_at", {"kind": "kind = ?"}),
             "trail": ("SELECT seq, at, principal, role, transport, tool, outcome, erp_seq FROM audit_trail WHERE ? = ?",
                       "seq DESC", {"principal": "principal = ?", "tool": "tool = ?", "outcome": "outcome = ?"}),
             "events": ("SELECT * FROM events WHERE (engagement_id = ? OR engagement_id IS NULL)", "id DESC",
                        {"kind": "kind = ?"})}[kind]
        base, order, allowed = q
        args = [1, 1] if kind == "trail" else [EID()]
        clauses = []
        for k, v in f.items():
            if k not in allowed:
                raise ToolError(f"INVALID_ARGUMENT: filters for {kind}: {', '.join(allowed)}")
            clauses.append(allowed[k])
            args.append(v)
        sql = base + "".join(f" AND {c}" for c in clauses)
        with db.borrow("audit", role) as a:
            total = a.execute(f"SELECT count(*) FROM ({sql})", args).fetchone()[0]
            rows = [dict(r) for r in a.execute(f"{sql} ORDER BY {order} LIMIT ? OFFSET ?", (*args, n, off))]
        if kind == "risk_hits":
            rows = [_hit_item(r) for r in rows]
        elif kind == "findings":
            rows = [scrub(r, ("title", "explanation", "decision_note")) for r in rows]
        elif kind == "events":
            rows = [scrub(r, ("payload_json",)) for r in rows]
        else:
            rows = [scrub(r, ("notes",)) for r in rows]
        return result({"kind": kind, "total": total, "count": len(rows)}, rows, str(off + n) if off + n < total else None)
    return call(go)


def make_download(path, sha256, roles=("audit_staff", "engagement_partner"), hours=24):
    """A one-time /files/<key> URL for a deliverable (never a server path)."""
    key = secrets.token_urlsafe(18)
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute("INSERT INTO downloads(key, path, sha256, roles_allowed, expires_at) VALUES (?,?,?,?,?)",
                  (key, str(path), sha256, ",".join(roles),
                   (datetime.fromisoformat(config.now()) + timedelta(hours=hours)).isoformat(timespec="seconds")))
    return f"{gateway.PUBLIC_URL.rsplit('/mcp', 1)[0]}/files/{key}"


@tool(*AUD)
def generate_deliverables() -> dict:
    """Build the 4-sheet workpaper (xlsx), the findings memo (md/html) and the audit-trail export, all marked DRAFT
    until the partner signs off -> one-time download URLs + sha256 (never server paths)."""
    def go(who, role):
        from app import trail
        changes = evidence.check_for_changes(EID())               # D11 runs before every deliverable (05 D11)
        new = findings.from_hits(EID())                           # every serious hit is a PROPOSED finding
        out = {"new_findings": new, "stale_samples": len(changes["stale_samples"])}
        wp = workpaper.build(EID())
        mm = memo.build(EID())
        files = [("workpaper.xlsx", wp["path"], wp["sha256"]), ("memo.md", mm["path"], mm["sha256"])]
        import hashlib
        from pathlib import Path
        files.append(("memo.html", mm["html_path"], hashlib.sha256(Path(mm["html_path"]).read_bytes()).hexdigest()))
        exp_dir = config.AUDIT_FILES_DIR / EID()
        for name, sha in trail.export(exp_dir, EID()).items():
            files.append((name, str(exp_dir / name), sha))
        out["files"] = [{"name": n, "sha256": s, "url": make_download(p, s)} for n, p, s in files]
        out["status"] = "DRAFT (until the engagement partner signs off)"
        out["verify_offline"] = "python scripts/verify_trail.py audit_trail.jsonl erp_log_head.json"
        trail.anchor(EID(), "DELIVERABLES")
        return result(out, next_steps=steps(("submit_for_partner_review", {}, "hand over to the engagement partner")))
    return call(go)


@tool(*AUD)
def submit_for_partner_review() -> dict:
    """Mark the engagement READY_FOR_REVIEW and list what still blocks sign-off (PROPOSED findings, stale samples,
    integrity failures). The engagement partner decides every finding and signs off in the web UI only."""
    def go(who, role):
        findings.from_hits(EID())
        blockers = []
        with db.borrow("audit", role) as a:
            _need_engagement(a)
            proposed = a.execute("SELECT count(*) FROM findings WHERE engagement_id = ? AND status = 'PROPOSED'",
                                 (EID(),)).fetchone()[0]
        if proposed:
            blockers.append(f"{proposed} finding(s) await the partner's decision")
        if not _is_stub(evidence):
            stale = evidence.check_for_changes(EID()).get("stale_samples", [])
            if stale:
                blockers.append(f"{len(stale)} stale sample(s) need re-testing")
            if not evidence.verify_integrity(EID()).get("ok"):
                blockers.append("integrity check failed (verify_integrity)")
        with db.borrow("audit", role) as a, db.tx(a):
            a.execute("UPDATE engagements SET status = 'READY_FOR_REVIEW' WHERE id = ? AND status != 'SIGNED_OFF'",
                      (EID(),))
        from app import notify
        notify.emit("READY_FOR_REVIEW", {"blockers": len(blockers)}, EID())
        return result({"status": "READY_FOR_REVIEW", "review_url": config.env("UI_URL", "http://localhost:8501"),
                       "blocking_items": blockers},
                      next_steps=steps(("get_engagement_status", {}, "follow the partner's decisions")))
    return call(go)


_ALLOWED_SQL = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


@tool(*AUD, read_only=True)
def run_readonly_sql(sql: str, database: str = "erp") -> dict:
    """Ad-hoc SELECT on the books (database='erp') or portals ('ext') through the read-only handle; only
    SELECT/READ/FUNCTION are authorised; at most 100 rows. Example: run_readonly_sql(sql="SELECT party_id,
    count(*) n FROM invoices GROUP BY party_id ORDER BY n DESC LIMIT 10")"""
    def go(who, role):
        if database not in ("erp", "ext"):
            raise ToolError("INVALID_ARGUMENT: database is 'erp' or 'ext'")
        c = db.connect(database, role)
        try:
            c.set_authorizer(lambda action, *a: sqlite3.SQLITE_OK if action in _ALLOWED_SQL else sqlite3.SQLITE_DENY)
            try:
                cur = c.execute(sql)
            except sqlite3.DatabaseError as e:
                raise ToolError(f"INVALID_ARGUMENT: only a single SELECT is allowed ({type(e).__name__})") from e
            cols = [d[0] for d in cur.description or []]
            rows = [dict(zip(cols, [clean(v) for v in r])) for r in cur.fetchmany(100)]
        finally:
            c.close()
        return result({"columns": cols, "rows": len(rows), "capped_at": 100}, rows, None)
    return call(go)


@tool(*AUD, read_only=True)
def get_risk_graph(min_risk: int = 30, focus_party: str | None = None, limit: int = 150,
                   cursor: str | None = None) -> dict:
    """AuditGraph (05 §19): the company risk band (SA 315) and exposure, and the top risk-scored nodes and edges.
    Each node carries its risk R' (0-100) and confidence C. focus_party narrows to one party's neighbourhood."""
    def go(who, role):
        g = risk_graph.build(EID())
        nodes = [n for n in g.get("nodes", []) if (n.get("R") or n.get("E") or 0) >= min_risk
                 and (not focus_party or n["id"] == focus_party or any(
                     e for e in g.get("edges", []) if focus_party in (e["a"], e["b"]) and n["id"] in (e["a"], e["b"])))]
        nodes.sort(key=lambda n: -(n.get("R") or n.get("E") or 0))
        n_lim = max(1, min(150, int(limit or 150)))
        off = offset_of(cursor)
        chunk = nodes[off:off + n_lim]
        ids = {n["id"] for n in chunk}
        edges = [e for e in g.get("edges", []) if e["a"] in ids or e["b"] in ids][:300]
        return result({"company": g.get("company"), "nodes": len(nodes), "cycles": len(g.get("cycles", []))},
                      [scrub(n, ("label",)) for n in chunk], str(off + n_lim) if off + n_lim < len(nodes) else None,
                      edges=edges, cycles=g.get("cycles", [])[:20])
    return call(go)

@tool(*AUD, read_only=True)
def trace_money(object_id: str, hops: int = 2, limit: int = 50, cursor: str | None = None) -> dict:
    """Money trail (vault/13): for an invoice, credit note, PO, GRN, purchase bill, settlement, bank line or party,
    every edge with its provenance: VERIFIED (bank line / portal record), CLAIMED (the company's own books), INFERRED
    (identity link). numbers = recorded vs bank-verified vs goods received vs potentially affected (not a loss).
    Transfers beyond hop 1 are context only: nothing is attributed downstream. Example: trace_money(object_id='PO-000001')"""
    def go(who, role):
        try:
            r = money_trail.trace(object_id, hops=hops, role=role)
        except LookupError as ex:
            raise ToolError(str(ex)) from None
        items, nxt = page(r["edges"], limit, cursor)
        return result({"root": r["root"], "numbers": r["numbers"], "edges": len(r["edges"]), "cycles": r["cycles"]},
                      items, nxt,
                      steps(("list_audit_items", {"kind": "risk_hits", "filters": {"min_severity": 4}},
                             "the hits behind affected_basis"),
                            ("trace_sale", {"invoice": "G2/0001/25"}, "the document chain of one sale")),
                      nodes=[scrub(n, ("label",)) for n in r["nodes"]])
    return call(go)

# ---------------------------------------------------------------- /files/<key> (one-time deliverable downloads)

@gateway.mcp.custom_route("/files/{key}", methods=["GET"])
async def download(request):
    from starlette.responses import FileResponse, JSONResponse
    auth = request.headers.get("authorization", "")
    ident = gateway.IDS.get(auth.removeprefix("Bearer ").strip()) if auth.startswith("Bearer ") else None
    key = request.path_params["key"]
    with db.borrow("audit", "system") as a, db.tx(a):
        row = a.execute("SELECT * FROM downloads WHERE key = ?", (key,)).fetchone()
        if row is None or row["expires_at"] < config.now():
            return JSONResponse({"error": "NOT_FOUND: unknown or expired download link"}, status_code=404)
        if not ident or ident["role"] not in row["roles_allowed"].split(","):
            return JSONResponse({"error": "UNAUTHENTICATED: send the auditor's Bearer token"}, status_code=401)
        a.execute("UPDATE downloads SET expires_at = '1970-01-01T00:00:00+05:30' WHERE key = ?", (key,))  # one-time
    return FileResponse(row["path"], filename=row["path"].replace("\\", "/").rsplit("/", 1)[-1])
