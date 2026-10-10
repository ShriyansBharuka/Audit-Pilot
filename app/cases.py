"""Audit cases (vault/13 MT-4): every severity >= 4 hit grouped by its root object into one case AUD-0001..., with
the three numbers from the money trail (recorded / bank-verified / potentially affected), a risk score separate from
the confidence in the evidence, the hit list, the documents and an append-only history.

Root objects: an invoice (register rows fold into their system-of-record invoice), a purchase order (its GRNs and
bills fold in), a payment, a credit note, a journal, or a party (a D10 cycle folds into its first entity member), so
NO_MOVEMENT + EWB_REQUIRED_MISSING on one invoice is one case. Titles and explanations cite codes and ids only, never
client text. Actions are audit_staff only; a proposed adjustment is a PROPOSED finding that the partner decides as
today. The client never sees a case (audit.db is closed to client roles; an evidence request carries only the case id).
"""
import json
from collections import defaultdict
from datetime import date, timedelta

from app import config, db, findings, ledger, money, money_trail, risk_graph

ACTIONS = {"EXPLAINED": "EXPLAINED", "REQUEST_EVIDENCE": "EVIDENCE_REQUESTED", "ESCALATE": "ESCALATED",
           "PROPOSE_ADJUSTMENT": "ADJUSTMENT_PROPOSED"}
DOC_KINDS = ("INVOICE", "EWAY_BILL", "LR", "POD", "CREDIT_NOTE", "RETURN_PROOF", "CONTRACT", "OTHER")
TRACEABLE = {"invoice", "credit_note", "purchase_order", "purchase_bill", "settlement", "party"}
SUGGEST = {
    "SHORT_RECEIPT": "Request proof of the remaining delivery (GRN, LR) or the vendor's credit note; check later receipts.",
    "PAYMENT_WITHOUT_RECEIPT": "Request the goods receipt and transport document, or the advance agreement.",
    "DUPLICATE_PAYMENT": "Request the vendor's statement and evidence of refund or adjustment of the second payment.",
    "BENEFICIARY_MISMATCH": "Request the payment authorisation and the vendor's bank confirmation for the account paid.",
    "UNRECORDED_LIABILITY": "Propose an accrual at the period end (purchases / creditors) or obtain the reason none was booked.",
    "PRICE_VARIANCE": "Request the approved price revision or a debit note to the vendor.",
    "ADVANCE_UNSETTLED": "Request the purchase order and the vendor's confirmation of the advance balance.",
    "PREMATURE": "Request the LR / POD; propose deferring the revenue to the period control transferred.",
    "NO_MOVEMENT": "Request the e-way bill, LR and POD; without them the sale is not supported.",
    "POST_PERIOD_REVERSAL": "Inspect the April credit note against the March sale; consider a cut-off adjustment.",
    "UNDISCLOSED_RP": "Ask management to confirm the relationship and update the related-party list (Ind AS 24).",
    "CIRCULAR_FLOW": "Obtain the commercial substance of each leg of the cycle; consider the circular value only once.",
    "REVENUE_WITHOUT_SALE": "Request support for the journal and the approval trail; propose reversal if unsupported.",
}


def _now_ev(a, case_id, action, by, role, note=None, payload=None):
    a.execute("INSERT INTO case_events(case_id, at, by, role, action, note, payload_json) VALUES (?,?,?,?,?,?,?)",
              (case_id, config.now(), by, role, action, note, json.dumps(payload, sort_keys=True) if payload else None))
    return a.execute("SELECT * FROM case_events WHERE id = last_insert_rowid()").fetchone()


def add_event(case_id, action, by, role, note=None, payload=None):
    """Append one history row without changing the status (MT-5 AI_INVESTIGATION). -> event dict."""
    with db.borrow("audit", "system") as a, db.tx(a):
        if a.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone() is None:
            raise LookupError(f"NOT_FOUND: no case {case_id}. Use list_cases. Example: get_case(case_id='AUD-0001')")
        return _event(_now_ev(a, case_id, action, by, role, note, payload))


def _event(r):
    return {"id": r["id"], "at": r["at"], "by": r["by"], "action": r["action"], "note": r["note"],
            "payload": json.loads(r["payload_json"]) if r["payload_json"] else None}

# ---------------------------------------------------------------- grouping

def _root(h, e, kinds):
    ev = json.loads(h["evidence_json"] or "{}") or {}
    t, oid = h["object_type"], h["object_id"]
    if h["detector"] == "D10":
        ents = [m for m in ev.get("members") or [] if m != "SELF" and kinds.get(m) == "ENTITY"]
        if ents:
            return "party", ents[0]
    if t == "register_row":
        sid = (ev.get("sor") or {}).get("id")
        return ("invoice", sid) if sid else (t, oid)
    if t == "goods_receipt":
        r = e.execute("SELECT po_id FROM goods_receipts WHERE id = ?", (oid,)).fetchone()
        return ("purchase_order", r[0]) if r else (t, oid)
    if t == "purchase_bill":
        r = e.execute("SELECT po_id FROM purchase_bills WHERE id = ?", (oid,)).fetchone()
        return ("purchase_order", r[0]) if r and r[0] else (t, oid)
    return t, oid


def _counterparty(e, rtype, rid):
    sql = {"invoice": "SELECT party_id FROM invoices WHERE id = ?",
           "credit_note": "SELECT party_id FROM credit_notes WHERE id = ?",
           "purchase_order": "SELECT vendor_id FROM purchase_orders WHERE id = ?",
           "purchase_bill": "SELECT vendor_id FROM purchase_bills WHERE id = ?",
           "settlement": "SELECT party_id FROM settlements WHERE id = ?",
           "party": "SELECT id FROM parties WHERE id = ?"}.get(rtype)
    r = e.execute(sql, (rid,)).fetchone() if sql else None
    return r[0] if r else None


def _affected(hs):
    """Largest serious impact per object, each D10 cycle once at its minimum-span value (never a sum of its edges)."""
    best, cycles = {}, {}
    for h in hs:
        if h["severity"] < 4:
            continue
        if h["detector"] == "D10":
            ev = json.loads(h["evidence_json"] or "{}") or {}
            cycles[tuple(ev.get("members") or [h["object_id"]])] = h["impact_paise"]
        else:
            k = (h["object_type"], h["object_id"])
            best[k] = max(best.get(k, 0), h["impact_paise"] or 0)
    return sum(best.values()) + sum(cycles.values())


def _score(a, rtype, rid, hs):
    """Risk score (0-100) and confidence (x1000): the AuditGraph snapshot for an invoice / party, else engine A."""
    otype = {"invoice": "INVOICE", "credit_note": "CN", "party": "PARTY"}.get(rtype)
    if otype:
        r = a.execute("SELECT R, E, C FROM risk_snapshots WHERE object_type = ? AND object_id = ? ORDER BY at DESC, rowid DESC"
                      " LIMIT 1", (otype, rid)).fetchone()
        if r is not None:
            v = r["E"] if otype == "PARTY" else r["R"]
            if v is not None:
                return round(v / 1000), int(r["C"] or 0)
    return risk_graph._engine_a(hs), int(risk_graph._confidence(hs) * 1000)


def _title(code, rtype, rid, n):
    more = f" (+{n - 1} more)" if n > 1 else ""
    return f"{code.replace('_', ' ').capitalize()} on {rtype.replace('_', ' ')} {rid}{more}"


def rebuild(engagement_id=None):
    """Idempotent: one case per root of serious hits. Ids and statuses are kept; numbers, hits and titles refresh; a
    case with no serious hits left becomes active = 0. -> {active, new: [case ids]}."""
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        hits = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ? ORDER BY severity DESC,"
                                           " impact_paise DESC, id", (eid,))]
        have = {(r["root_type"], r["root_id"]): dict(r) for r in a.execute("SELECT * FROM cases WHERE engagement_id = ?", (eid,))}
        last = a.execute("SELECT id FROM cases WHERE id >= 'AUD-0' AND id < 'AUD-:' ORDER BY id DESC LIMIT 1").fetchone()
    groups = defaultdict(list)
    with db.borrow("erp", "system") as e:
        kinds = dict(e.execute("SELECT id, kind FROM parties"))
        for h in hits:
            groups[_root(h, e, kinds)].append(h)
        roots = {k: hs for k, hs in groups.items() if any(h["severity"] >= 4 for h in hs)}
        cp = {k: _counterparty(e, *k) for k in roots}
    rows, n, now = [], int(last[0][4:]) if last else 0, config.now()
    with db.borrow("audit", "system") as a:
        for (rtype, rid), hs in sorted(roots.items(), key=lambda kv: (-kv[1][0]["severity"], -(kv[1][0]["impact_paise"] or 0),
                                                                      kv[0])):
            codes = list(dict.fromkeys(h["code"] for h in hs if h["severity"] >= 4))
            nums = {"recorded_paise": 0, "verified_paise": 0, "received_paise": None}
            if rtype in TRACEABLE:
                try:
                    t = money_trail.trace(rid, hops=1, engagement_id=eid, role="system")["numbers"]
                    nums = {k: t[k] for k in nums}
                except LookupError:
                    pass
            score, conf = _score(a, rtype, rid, hs)
            rows.append({"root_type": rtype, "root_id": rid, "title": _title(codes[0], rtype, rid, len(codes)),
                         "counterparty_id": cp[(rtype, rid)], "codes_json": json.dumps(codes),
                         "hit_ids_json": json.dumps([h["id"] for h in hs]), "top_severity": hs[0]["severity"], **nums,
                         "affected_paise": _affected(hs), "risk_score": score, "confidence": conf,
                         "band": risk_graph.band(score)})
    new = []
    with db.borrow("audit", "system") as a, db.tx(a):
        for r in rows:
            old = have.get((r["root_type"], r["root_id"]))
            if old:
                a.execute("UPDATE cases SET title=?, counterparty_id=?, codes_json=?, hit_ids_json=?, top_severity=?,"
                          " recorded_paise=?, verified_paise=?, received_paise=?, affected_paise=?, risk_score=?, confidence=?,"
                          " band=?, active=1, updated_at=? WHERE id = ?",
                          (r["title"], r["counterparty_id"], r["codes_json"], r["hit_ids_json"], r["top_severity"],
                           r["recorded_paise"], r["verified_paise"], r["received_paise"], r["affected_paise"],
                           r["risk_score"], r["confidence"], r["band"], now, old["id"]))
                continue
            n += 1
            cid = f"AUD-{n:04d}"
            a.execute("INSERT INTO cases(id, engagement_id, root_type, root_id, title, counterparty_id, codes_json, hit_ids_json,"
                      " top_severity, recorded_paise, verified_paise, received_paise, affected_paise, risk_score, confidence,"
                      " band, status, active, opened_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'OPEN',1,?,?)",
                      (cid, eid, r["root_type"], r["root_id"], r["title"], r["counterparty_id"], r["codes_json"],
                       r["hit_ids_json"], r["top_severity"], r["recorded_paise"], r["verified_paise"], r["received_paise"],
                       r["affected_paise"], r["risk_score"], r["confidence"], r["band"], now, now))
            _now_ev(a, cid, "OPENED", "system:cases", "system", None, {"codes": json.loads(r["codes_json"])})
            new.append(cid)
        live = {(r["root_type"], r["root_id"]) for r in rows}
        for k, old in have.items():
            if k not in live and old["active"]:
                a.execute("UPDATE cases SET active = 0, updated_at = ? WHERE id = ?", (now, old["id"]))
    return {"active": len(rows), "new": new}

# ---------------------------------------------------------------- reading

def _summary(r, names):
    out = {"case_id": r["id"], "title": r["title"], "root_type": r["root_type"], "root_id": r["root_id"],
           "counterparty_id": r["counterparty_id"], "counterparty_name": names.get(r["counterparty_id"]),
           "band": r["band"], "risk_score": r["risk_score"], "confidence": r["confidence"] / 1000,
           "recorded_paise": r["recorded_paise"], "verified_paise": r["verified_paise"],
           "received_paise": r["received_paise"], "affected_paise": r["affected_paise"], "status": r["status"],
           "active": bool(r["active"]), "opened_at": r["opened_at"], "updated_at": r["updated_at"],
           "codes": json.loads(r["codes_json"])}
    for k in ("recorded_paise", "verified_paise", "received_paise", "affected_paise"):
        if out[k] is not None:
            out[k.replace("_paise", "_formatted")] = money.fmt_inr(out[k])
    return out


def _names(ids):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    with db.borrow("erp", "system") as e:
        return dict(e.execute(f"SELECT id, name FROM parties WHERE id IN ({','.join('?' * len(ids))})", ids))


def refresh_if_stale(engagement_id=None):
    """Rebuild when hits were written after the last rebuild (e.g. D0 reconcile after run_analytics)."""
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        h = a.execute("SELECT max(created_at) FROM risk_hits WHERE engagement_id = ?", (eid,)).fetchone()[0]
        c = a.execute("SELECT max(updated_at) FROM cases WHERE engagement_id = ?", (eid,)).fetchone()[0]
    if h and (c is None or h > c):
        rebuild(eid)


def list_cases(engagement_id=None, status=None, band=None, limit=25, offset=0, include_inactive=False):
    """-> {total, items}. Ranked by risk score, then potentially affected amount."""
    eid = engagement_id or config.ENGAGEMENT_ID
    refresh_if_stale(eid)
    sql, args = "SELECT * FROM cases WHERE engagement_id = ?", [eid]
    if not include_inactive:
        sql += " AND active = 1"
    if status:
        sql += " AND status = ?"
        args.append(status)
    if band:
        sql += " AND band = ?"
        args.append(band)
    with db.borrow("audit", "system") as a:
        rows = [dict(r) for r in a.execute(sql + " ORDER BY risk_score DESC, affected_paise DESC, id", args)]
    limit, offset = max(1, min(100, int(limit or 25))), max(0, int(offset or 0))
    chunk = rows[offset:offset + limit]
    names = _names({r["counterparty_id"] for r in chunk})
    return {"total": len(rows), "items": [_summary(r, names) for r in chunk]}


def _one(a, case_id):
    r = a.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if r is None:
        raise LookupError(f"NOT_FOUND: no case {case_id}. Use list_cases. Example: get_case(case_id='AUD-0001')")
    return dict(r)


_DOC = {"SALE": "invoice", "EINVOICE": "einvoice", "DISPATCH": "movement", "CREDIT_NOTE": "credit_note",
        "ORDER": "purchase_order", "GOODS_RECEIPT": "goods_receipt", "GOODS_RETURN": "goods_receipt",
        "BILL": "purchase_bill", "PAYMENT_OUT": "settlement", "PAYMENT_IN": "settlement"}


def get_case(case_id):
    """-> {case, hits, documents, money_trail, numbers, explanation, suggested_action, history, investigation}."""
    with db.borrow("audit", "system") as a:
        c = _one(a, case_id)
        ids = json.loads(c["hit_ids_json"])
        hits = [dict(r) for r in a.execute(f"SELECT * FROM risk_hits WHERE id IN ({','.join('?' * len(ids))})", ids)] if ids else []
        history = [_event(r) for r in a.execute("SELECT * FROM case_events WHERE case_id = ? ORDER BY id", (case_id,))]
    hits.sort(key=lambda h: (-h["severity"], -(h["impact_paise"] or 0), h["id"]))
    trail = {"nodes": [], "edges": [], "numbers": {}, "cycles": []}
    if c["root_type"] in TRACEABLE:
        try:
            trail = money_trail.trace(c["root_id"], hops=2, engagement_id=c["engagement_id"], role="system")
        except LookupError:
            pass
    docs = [{"doc_type": "bank_txn" if x["source"] == "BANK" else _DOC.get(x["kind"], x["kind"].lower()),
             "doc_id": x["evidence_refs"][0] if x["source"] in ("BANK", "PORTAL") and x["evidence_refs"] else
             (x["doc_ids"][0] if x["doc_ids"] else None),
             "doc_no": x["evidence_refs"][0] if x["evidence_refs"] else None, "date": x["date"],
             "amount_paise": x["amount_paise"], "amount_formatted": x["amount_formatted"], "source": x["source"],
             "status": x["status"]} for x in trail["edges"] if x["hop"] == 1]
    summary = _summary(c, _names([c["counterparty_id"]]))
    codes = summary["codes"]
    fmt = money.fmt_inr
    explanation = (f"{len(hits)} risk hit(s) on {c['root_type'].replace('_', ' ')} {c['root_id']} ({', '.join(codes)}). "
                   f"Recorded in the books {fmt(c['recorded_paise'])}; verified by bank lines naming the recorded "
                   f"counterparty {fmt(c['verified_paise'])}"
                   + (f"; goods received at the PO rate {fmt(c['received_paise'])}" if c["received_paise"] is not None else "")
                   + f". Potentially affected {fmt(c['affected_paise'])}: an amount to investigate, not a loss. "
                   f"Where the money went after the counterparty is not established.")
    inv = next((h["payload"] for h in reversed(history) if h["action"] == "AI_INVESTIGATION"), None)
    return {"case": summary,
            "hits": [{"id": h["id"], "detector": h["detector"], "code": h["code"], "severity": h["severity"],
                      "reason": h["reason"], "impact_paise": h["impact_paise"], "object_type": h["object_type"],
                      "object_id": h["object_id"]} for h in hits],
            "documents": docs,
            "money_trail": {"nodes": trail["nodes"], "edges": trail["edges"], "cycles": trail.get("cycles", [])},
            "numbers": {"verified_paise": c["verified_paise"], "affected_paise": c["affected_paise"],
                        "recorded_paise": c["recorded_paise"], "received_paise": c["received_paise"],
                        "risk_score": c["risk_score"], "confidence": c["confidence"] / 1000,
                        "attribution": "NOT_ESTABLISHED"},
            "explanation": explanation,
            "suggested_action": next((SUGGEST[k] for k in codes if k in SUGGEST),
                                     "Inspect the source documents and request the missing evidence."),
            "history": history, "investigation": inv}

# ---------------------------------------------------------------- actions (audit_staff)

def _doc_no(e, rtype, rid):
    sql = {"invoice": "SELECT invoice_no FROM invoices WHERE id = ?", "credit_note": "SELECT cn_no FROM credit_notes WHERE id = ?",
           "purchase_order": "SELECT po_no FROM purchase_orders WHERE id = ?"}.get(rtype)
    r = e.execute(sql, (rid,)).fetchone() if sql else None
    return r[0] if r else rid


def act(case_id, action, note, actor, role, doc_kind=None, aje_lines=None):
    """EXPLAINED (note required) | REQUEST_EVIDENCE (doc_kind; a pbc request carrying only the case id) | ESCALATE
    (note required) | PROPOSE_ADJUSTMENT (aje_lines in paise, else the detector's standard AJE -> a PROPOSED finding).
    -> {case, event}."""
    if role != "audit_staff":
        raise PermissionError("PERMISSION_DENIED: only audit staff act on cases (the partner decides findings)")
    if action not in ACTIONS:
        raise ValueError(f"INVALID_ARGUMENT: action is one of {', '.join(ACTIONS)}. Example: act_on_case(case_id='AUD-0001',"
                         f" action='EXPLAINED', note='later GRN 15 Apr covers the balance')")
    note = (note or "").strip() or None
    if action in ("EXPLAINED", "ESCALATE") and not note:
        raise ValueError(f"INVALID_ARGUMENT: {action} needs a note saying why")
    with db.borrow("audit", "system") as a:
        c = _one(a, case_id)
    payload = {}
    if action == "REQUEST_EVIDENCE":
        kind = doc_kind or "OTHER"
        if kind not in DOC_KINDS:
            raise ValueError(f"INVALID_ARGUMENT: doc_kind is one of {', '.join(DOC_KINDS)}")
        with db.borrow("erp", "system") as e:
            about = _doc_no(e, c["root_type"], c["root_id"])
        due = (date.fromisoformat(config.today()) + timedelta(days=7)).isoformat()
        with db.borrow("pbc", "system") as pb, db.tx(pb):
            last = pb.execute("SELECT id FROM evidence_requests WHERE id >= 'REQ-0' AND id < 'REQ-:' ORDER BY id DESC"
                              " LIMIT 1").fetchone()
            rid = f"REQ-{(int(last[0][4:]) if last else 0) + 1:06d}"
            pb.execute("INSERT INTO evidence_requests(id, engagement_id, sample_ref, doc_kind, about_doc_no, requested_at,"
                       " due_on, status) VALUES (?,?,?,?,?,?,?,'OPEN')", (rid, c["engagement_id"], case_id, kind, about,
                                                                         config.now(), due))
        payload = {"request_id": rid, "doc_kind": kind, "due_on": due}
    if action == "PROPOSE_ADJUSTMENT":
        with db.borrow("audit", "system") as a:
            top = a.execute(f"SELECT * FROM risk_hits WHERE id IN ({','.join('?' * len(json.loads(c['hit_ids_json'])))})"
                            " ORDER BY severity DESC, impact_paise DESC LIMIT 1", json.loads(c["hit_ids_json"])).fetchone()
        det, code = (top["detector"], top["code"]) if top else (None, None)
        lines = aje_lines or findings.aje({"detector": det, "code": code, "doc_refs": [c["root_id"]]})
        if not lines:
            raise ValueError("INVALID_ARGUMENT: no standard adjustment for this case; pass balanced aje_lines. Example: "
                             "[{account_code:'PURCHASES', dr_paise:9000000}, {account_code:'CREDITORS', party_id:'P-VEN5', "
                             "cr_paise:9000000}]")
        with db.borrow("erp", "audit_staff") as e:
            ledger.check_lines(e, lines)
        impact = sum(int(l.get("dr_paise") or 0) for l in lines)
        payload = {"aje_lines": lines}
    with db.borrow("audit", "system") as a, db.tx(a):
        if action == "PROPOSE_ADJUSTMENT":
            last = a.execute("SELECT id FROM findings WHERE id >= 'F-0' AND id < 'F-:' ORDER BY id DESC LIMIT 1").fetchone()
            fid = f"F-{(int(last[0][2:]) if last else 0) + 1:03d}"
            end = a.execute("SELECT period_end FROM engagements WHERE id = ?", (c["engagement_id"],)).fetchone()
            a.execute("INSERT INTO findings(id, engagement_id, detector, code, category, title, explanation, standards,"
                      " doc_refs_json, evidence_json, taxable_impact_paise, tax_impact_paise, gross_impact_paise, affected_fy,"
                      " confidence, proposed_aje_json, status, prepared_by, prepared_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,?,"
                      "'MEDIUM',?,'PROPOSED',?,?)",
                      (fid, c["engagement_id"], det, code, findings.CATEGORY.get(det, "Case"), c["title"],
                       f"Adjustment proposed on case {case_id} ({c['root_type']} {c['root_id']})."
                       + (" Auditor's note recorded in the case history." if note else ""),
                       findings.STANDARDS.get(det, ""), json.dumps([c["root_id"]]),
                       json.dumps({"group": f"CASE|{case_id}", "case": case_id}), impact, impact,
                       findings.fy_label(end[0]) if end else None,
                       json.dumps(lines), actor, config.now()))
            payload["finding_id"] = fid
        a.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?", (ACTIONS[action], config.now(), case_id))
        ev = _event(_now_ev(a, case_id, action, actor, role, note, payload))
        c = _one(a, case_id)
    return {"case": _summary(c, _names([c["counterparty_id"]])), "event": ev}
