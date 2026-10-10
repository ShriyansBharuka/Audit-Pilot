"""Evidence and change control (05 D8, D11, D12; 03 §6).

- extract(): the server reads the document itself ("Key: Value" text from render_document, PDF text via PyMuPDF +
  regex); anything else is NEEDS_MANUAL_REVIEW. A client-declared field is a claim, compared with what the document says.
- bundle(): everything a sample's conclusion depends on, snapshotted when the sample is selected.
- test_sample(): D8 + the five Fig. 2 attributes; proposes a conclusion (the partner decides).
- check_for_changes(): D11, every client change after testing began, field by field, with who / role / tool / when
  and the samples it makes STALE (computed, never stored); re-opens their evidence requests.
- verify_integrity(): D12, the five checks of 03 §6.
"""
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from app import chain, config, db, erp

INSTRUCTION = re.compile(r"ignore (all|previous)|you are|system prompt|mark .* verified|auditor (ai|agent)|"
                         r"sign[- ]?off|do not (report|flag)", re.I)

# ---------------------------------------------------------------- extraction

_KEYS = {"document": "document", "invoice no": "doc_no", "credit note no": "doc_no", "invoice date": "doc_date",
         "credit note date": "doc_date", "doc no": "ref_doc_no", "doc date": "ref_doc_date", "ewb no": "ewb_no",
         "e-way bill no": "ewb_no", "eway bill no": "ewb_no", "lr no": "lr_no", "lr date": "lr_date",
         "vehicle no": "vehicle_no", "buyer gstin": "buyer_gstin", "to gstin": "to_gstin", "supplier gstin": "supplier_gstin",
         "from gstin": "supplier_gstin", "taxable value": "taxable", "total": "total", "value": "value", "irn": "irn",
         "invoice refs": "invoice_refs", "delivered on": "delivered_on", "received by": "received_by",
         "total qty": "qty", "generated": "generated_at", "status": "status", "transport doc no": "transport_doc_no",
         "transporter": "transporter", "consignee": "consignee", "place of supply": "place_of_supply"}
_RX = {"irn": r"\b[0-9a-f]{64}\b", "ewb_no": r"\b3\d{11}\b", "buyer_gstin": r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
       "doc_no": r"\b(?:G\d+|CN/G\d+)/\d{4}/\d{2}\b", "doc_date": r"\b\d{4}-\d{2}-\d{2}\b"}


def _parse(text):
    fields = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = _KEYS.get(k.strip().lower())
        if key and key not in fields:
            fields[key] = v.strip()
    if "invoice_refs" in fields:
        fields["invoice_refs"] = [x.strip() for x in fields["invoice_refs"].split(",") if x.strip()]
    for key, rx in _RX.items():                        # regex fallback for documents not in our Key: Value layout
        if key not in fields:
            m = re.search(rx, text)
            if m:
                fields[key] = m.group(0)
    return fields


def _submission(p, sid):
    s = p.execute("SELECT * FROM submissions WHERE id = ?", (sid,)).fetchone()
    if s is None:
        raise LookupError("NOT_FOUND: no submission with that id")
    return s


def extract(submission_id):
    """-> {submission_id, sha256, method: KEY_VALUE | PDF_TEXT | NEEDS_MANUAL_REVIEW, fields, text_sha256,
    instructions: bool}. Machine-read fields only; the client's declared_fields stay claims."""
    with db.borrow("pbc", "system") as p:
        s = _submission(p, submission_id)
    data = Path(s["stored_path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != s["sha256"]:
        raise ValueError("PRECONDITION_FAILED: the stored evidence no longer matches its sha256")
    text, method = None, "NEEDS_MANUAL_REVIEW"
    if data[:4] == b"%PDF":
        try:
            import fitz
            with fitz.open(stream=data, filetype="pdf") as pdf:
                text = "\n".join(page.get_text() for page in pdf)
            method = "PDF_TEXT"
        except Exception:  # noqa: BLE001 - a corrupt PDF is a manual review, not a crash
            text = None
    else:
        try:
            text = data.decode("utf-8")
            method = "KEY_VALUE"
        except UnicodeDecodeError:
            text = None
    fields = _parse(text) if text else {}
    if text and not fields:
        method = "NEEDS_MANUAL_REVIEW"
    norm = re.sub(r"\s+", " ", text or "").strip().lower()
    return {"submission_id": submission_id, "sha256": s["sha256"], "method": method, "fields": fields,
            "text_sha256": hashlib.sha256(norm.encode()).hexdigest() if norm else None,
            "instructions": bool(text and INSTRUCTION.search(text)),
            "declared": json.loads(s["declared_json"] or "{}"), "request_id": s["request_id"]}

# ---------------------------------------------------------------- bundle (what a sample's conclusion depends on)

def bundle(invoice_id):
    """-> [(doc_type, doc_id), ...]: the invoice; its SO (+ scheme); movements (LR, POD); CNs crediting it;
    settlements; journals sourced to any of these; the customer + its links; and portal rows (ext:...)."""
    out = []
    with db.borrow("erp", "system") as e:
        inv = e.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if inv is None:
            c = e.execute("SELECT * FROM credit_notes WHERE id = ?", (invoice_id,)).fetchone()
            if c is None:
                return []
            out.append(("credit_note", c["id"]))
            out += [("invoice", r[0]) for r in e.execute("SELECT DISTINCT invoice_id FROM cn_lines WHERE cn_id = ? AND"
                                                          " invoice_id IS NOT NULL", (c["id"],))]
            if c["return_movement_id"]:
                out.append(("movement", c["return_movement_id"]))
            out.append(("party", c["party_id"]))
            out += [("journal", str(r[0])) for r in e.execute("SELECT no FROM journals WHERE source_type = 'credit_note' AND"
                                                               " source_id = ?", (c["id"],))]
            return out
        out.append(("invoice", inv["id"]))
        if inv["so_id"]:
            out.append(("sales_order", inv["so_id"]))
            sch = e.execute("SELECT scheme_id FROM sales_orders WHERE id = ?", (inv["so_id"],)).fetchone()
            if sch and sch[0]:
                out.append(("scheme", sch[0]))
        out += [("movement", r[0]) for r in e.execute("SELECT movement_id FROM invoice_movements WHERE invoice_id = ?",
                                                       (inv["id"],))]
        cns = [r[0] for r in e.execute("SELECT DISTINCT cn_id FROM cn_lines WHERE invoice_id = ?", (inv["id"],))]
        out += [("credit_note", c) for c in cns]
        sets = [r[0] for r in e.execute("SELECT id FROM settlements WHERE doc_type = 'INVOICE' AND doc_id = ?", (inv["id"],))]
        out += [("settlement", s) for s in sets]
        out += [("journal", str(r[0])) for r in e.execute(
            f"SELECT no FROM journals WHERE (source_type = 'invoice' AND source_id = ?) OR (source_type = 'credit_note'"
            f" AND source_id IN ({','.join('?' * len(cns)) or 'NULL'}))", (inv["id"], *cns))]
        out.append(("party", inv["party_id"]))
        out += [("party_link", r[0]) for r in e.execute("SELECT id FROM party_links WHERE from_party = ? OR to_party = ?",
                                                         (inv["party_id"], inv["party_id"]))]
        doc_no, gstin = inv["invoice_no"], inv["supplier_gstin"]
        irn = inv["irn"]
    with db.borrow("ext", "system") as x:
        out += [("ext:ewaybill", r[0]) for r in x.execute("SELECT ewb_no FROM ewaybills WHERE doc_no = ? AND supplier_gstin = ?",
                                                           (doc_no, gstin))]
        if irn:
            out.append(("ext:einvoice", irn))
        out += [("ext:gstr1", f"{gstin}|{doc_no}") for _ in x.execute("SELECT 1 FROM gstr1_docs WHERE gstin = ? AND"
                                                                        " doc_no = ? LIMIT 1", (gstin, doc_no))]
    return out


def _ext_rows(keys):
    """Current images of portal rows named in a bundle."""
    out = {}
    with db.borrow("ext", "system") as x:
        for kind, key in keys:
            if kind == "ext:ewaybill":
                r = x.execute("SELECT * FROM ewaybills WHERE ewb_no = ?", (key,)).fetchone()
            elif kind == "ext:einvoice":
                r = x.execute("SELECT * FROM einvoices WHERE irn = ?", (key,)).fetchone()
            elif kind == "ext:gstr1":
                g, no = key.split("|", 1)
                r = x.execute("SELECT * FROM gstr1_docs WHERE gstin = ? AND doc_no = ?", (g, no)).fetchone()
            else:
                continue
            out[f"{kind}|{key}"] = dict(r) if r else None
    return out


def snapshot(invoice_id):
    """(bundle_json, snapshot_hash) stored on a sample at selection: the doc list + portal row images."""
    docs = bundle(invoice_id)
    ext = _ext_rows([d for d in docs if d[0].startswith("ext:")])
    with db.borrow("erp", "system") as e:
        imgs = {f"{t}|{i}": erp.image(e, t, i) for t, i in docs if not t.startswith("ext:")}
    b = {"docs": docs, "ext": ext}
    return json.dumps(b, sort_keys=True, default=str), hashlib.sha256(chain.canon({"erp": imgs, "ext": ext}).encode()).hexdigest()

# ---------------------------------------------------------------- D11 changes after testing began

_STALE_ACTIONS = {"AMEND", "CANCEL"}


def _samples(a, eid):
    return [dict(r) for r in a.execute("SELECT s.*, r.kind AS run_kind FROM samples s JOIN sample_runs r ON r.id = s.run_id"
                                       " WHERE r.engagement_id = ?", (eid,))]


def check_for_changes(engagement_id, reopen=True):
    """D11: every change since testing started. -> {testing_started_seq, changes: [{kind, table, pk, fields, by, role,
    tool, at, seq, affected_samples}], stale_samples: [{run_id, sample_no, doc_id, reasons}]}."""
    from app import notify
    with db.borrow("audit", "system") as a:
        eng = a.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
        if eng is None or eng["testing_started_seq"] is None:
            return {"testing_started_seq": None, "changes": [], "stale_samples": []}
        samples = _samples(a, engagement_id)
    start = eng["testing_started_seq"]
    owners = defaultdict(list)                                  # (doc_type, doc_id) -> [sample keys]
    snap_seq, inv_of = {}, {}
    for s in samples:
        key = f"{s['run_id']}#{s['sample_no']}"
        snap_seq[key] = max(s["snapshot_seq"], s["tested_seq"] or 0)   # a re-test re-baselines the sample
        inv_of[key] = s["doc_id"]
        b = json.loads(s["bundle_json"] or "{}") or {}
        for t, i in (b.get("docs") if isinstance(b, dict) else b) or []:
            owners[(t, str(i))].append(key)
    changes, stale = [], defaultdict(list)
    with db.borrow("erp", "system") as e:
        sample_invs = {s["doc_id"] for s in samples}
        for r in e.execute("SELECT * FROM erp_log WHERE seq > ? ORDER BY seq", (start,)):
            key = (r["doc_type"], r["doc_id"])
            before = json.loads(r["before_json"]) if r["before_json"] else {}
            after = json.loads(r["after_json"])
            hit = [k for k in owners.get(key, []) if r["seq"] > snap_seq[k]]
            kind = None
            if hit and r["action"] in _STALE_ACTIONS:
                kind = "EVIDENCE_FIELD_CHANGED"
            elif r["action"] in ("CREATE", "POST") and r["doc_type"] in ("settlement", "credit_note", "journal"):
                links = _links(after)                  # a new receipt / CN / voucher on a sampled invoice: not stale
                hit = [k for k, inv in inv_of.items() if inv in links and r["seq"] > snap_seq[k]]
                kind = "SUBSEQUENT_ACTIVITY" if hit else None
            elif r["action"] == "CREATE" and r["doc_type"] == "movement":
                links = {x["invoice_id"] for x in after.get("invoice_movements", [])}
                hit = [k for k, inv in inv_of.items() if inv in links and r["seq"] > snap_seq[k]]
                kind = "EVIDENCE_ADDED" if hit else None
            if r["action"] == "CREATE" and r["doc_type"] in ("invoice", "credit_note"):
                d = after["header"].get("invoice_date") or after["header"].get("cn_date")
                if d and eng["period_start"] <= d <= eng["period_end"]:
                    cut = [f"{s['run_id']}#{s['sample_no']}" for s in samples if s["run_kind"] == "CUTOFF_TOD"]
                    changes.append(_change(r, "BACKDATED_INSERTION", {}, sorted({k.split('#')[0] for k in cut})))
            if not kind:
                continue
            fields = erp._diff(before, after) if before else {}
            changes.append(_change(r, kind, fields, hit))
            if kind in ("EVIDENCE_FIELD_CHANGED", "EVIDENCE_ADDED"):
                for k in hit:
                    stale[k].append(f"{kind}: {r['doc_type']} {r['doc_id']} changed by {r['actor']} ({r['role']}) via "
                                    f"{r['tool']} at {r['recorded_at']}")
        bundle_docs = {k for k in owners if not k[0].startswith("ext:")}
        for o in erp.out_of_band(e, bundle_docs):
            hit = owners.get((o["doc_type"], o["doc_id"]), [])
            changes.append({"kind": "OUT_OF_BAND_EDIT", "table": o["doc_type"], "pk": o["doc_id"], "fields": o.get("fields", {}),
                            "by": "unknown (outside the application)", "role": None, "tool": None, "at": None,
                            "seq": o["seq"], "affected_samples": hit})
            for k in hit:
                stale[k].append(f"OUT_OF_BAND_EDIT: {o['doc_type']} {o['doc_id']} edited outside the application")
    # portal rows changed since the snapshot (e.g. an e-way bill cancelled after testing)
    for s in samples:
        k = f"{s['run_id']}#{s['sample_no']}"
        b = json.loads(s["bundle_json"] or "{}") or {}
        if not isinstance(b, dict):
            continue
        now = _ext_rows([tuple(d) for d in b.get("docs", []) if d[0].startswith("ext:")])
        for ref, old in (b.get("ext") or {}).items():
            if now.get(ref) != old:
                f = {fld: [(old or {}).get(fld), (now.get(ref) or {}).get(fld)] for fld in set(old or {}) | set(now.get(ref) or {})
                     if (old or {}).get(fld) != (now.get(ref) or {}).get(fld)}
                changes.append({"kind": "PORTAL_CHANGED", "table": ref.split("|")[0], "pk": ref.split("|", 1)[1], "fields": f,
                                "by": "portal", "role": None, "tool": None, "at": None, "seq": None, "affected_samples": [k]})
                stale[k].append(f"PORTAL_CHANGED: {ref.split('|')[0]} changed after testing began")
    # register / RP-list re-uploads after testing started
    with db.borrow("pbc", "system") as p:
        for r in p.execute("SELECT * FROM submissions WHERE engagement_id = ? AND kind IN ('SALES_REGISTER', 'RP_LIST')"
                           " AND submitted_at > ? ORDER BY id", (engagement_id, eng["testing_started_at"])):
            changes.append({"kind": "RE_UPLOAD", "table": "submissions", "pk": r["id"], "fields": {"kind": [None, r["kind"]]},
                            "by": r["submitted_by"], "role": None, "tool": "upload", "at": r["submitted_at"], "seq": None,
                            "affected_samples": sorted({f"{s['run_id']}" for s in samples if s["run_kind"] != "CN_TOD"})})
    by_key = {f"{s['run_id']}#{s['sample_no']}": s for s in samples}
    stale_list = [{"run_id": k.split("#")[0], "sample_no": int(k.split("#")[1]), "doc_id": by_key[k]["doc_id"],
                   "reasons": v} for k, v in sorted(stale.items())]
    if reopen and stale_list:
        _reopen(engagement_id, stale_list)
        notify_key = sorted(f"{s['run_id']}#{s['sample_no']}" for s in stale_list)
        with db.borrow("audit", "system") as a:
            last = a.execute("SELECT payload_json FROM events WHERE kind = 'STALE_DETECTED' ORDER BY id DESC LIMIT 1").fetchone()
        if not last or json.loads(last[0]).get("samples") != notify_key:
            notify.emit("STALE_DETECTED", {"samples": notify_key, "changes": len(changes)}, engagement_id)
    return {"testing_started_seq": start, "changes": changes, "stale_samples": stale_list}


def _links(after):
    """Invoice ids a CN / settlement / journal image refers to."""
    h = after.get("header", {})
    out = {l.get("invoice_id") for l in after.get("cn_lines", [])}
    if h.get("doc_type") == "INVOICE":
        out.add(h.get("doc_id"))
    if h.get("source_type") == "invoice":
        out.add(h.get("source_id"))
    return out - {None}


def _change(r, kind, fields, affected):
    return {"kind": kind, "table": r["doc_type"], "pk": r["doc_id"], "fields": fields, "by": r["actor"], "role": r["role"],
            "tool": r["tool"], "at": r["recorded_at"], "seq": r["seq"], "reason": r["reason"], "affected_samples": affected}


def _reopen(eid, stale):
    with db.borrow("erp", "system") as e:
        nos = {s["doc_id"]: (e.execute("SELECT invoice_no FROM invoices WHERE id = ?", (s["doc_id"],)).fetchone() or
                             e.execute("SELECT cn_no FROM credit_notes WHERE id = ?", (s["doc_id"],)).fetchone() or [None])[0]
               for s in stale}
    with db.borrow("pbc", "system") as p, db.tx(p):
        for no in nos.values():
            if no:
                p.execute("UPDATE evidence_requests SET status = 'OPEN' WHERE engagement_id = ? AND about_doc_no = ? AND"
                          " status = 'RECEIVED'", (eid, no))

# ---------------------------------------------------------------- D12 integrity

def verify_integrity(engagement_id):
    """The five checks of 03 §6 -> {ok, checks, problems: [{code, detail}]}; writes D12 hits; INTEGRITY_ALERT on failure."""
    from app import analytics, notify
    problems, checks = [], {}
    with db.borrow("audit", "system") as a:
        anchors = [dict(r) for r in a.execute("SELECT * FROM anchors ORDER BY id")]
        trail_v = chain.verify(a, "audit_trail", anchors=[(x["trail_seq"], x["trail_hash"]) for x in anchors if x["trail_seq"]])
        trail_rows = [(r[0], r[1], r[2]) for r in a.execute("SELECT seq, erp_seq, erp_hash FROM audit_trail WHERE erp_seq"
                                                            " IS NOT NULL")]
    with db.borrow("erp", "system") as e:
        erp_v = chain.verify(e, "erp_log", anchors=[(x["erp_seq"], x["erp_hash"]) for x in anchors if x["erp_seq"]])
        oob = erp.out_of_band(e)
        unbalanced = [r[0] for r in e.execute("SELECT journal_no FROM journal_lines GROUP BY journal_no"
                                              " HAVING SUM(dr_paise) != SUM(cr_paise)")]
        hashes = {r[0]: r[1] for r in e.execute("SELECT seq, hash FROM erp_log")}
    checks["erp_chain"] = erp_v
    if erp_v["broken_at_seq"]:
        problems.append({"code": "CHAIN_BROKEN", "detail": f"erp_log breaks at seq {erp_v['broken_at_seq']}"})
    if erp_v["anchor_mismatch_at"]:
        at = next((x["at"] for x in anchors if x["erp_seq"] == erp_v["anchor_mismatch_at"]), None)
        problems.append({"code": "ANCHOR_MISMATCH", "detail": f"erp_log history before the anchor of {at} was rewritten "
                                                              f"(seq {erp_v['anchor_mismatch_at']})"})
    checks["out_of_band"] = oob
    for o in oob:
        problems.append({"code": "OUT_OF_BAND_EDIT", "detail": f"{o['doc_type']} {o['doc_id']} {o['kind'].lower()} outside "
                                                               f"the application", "fields": o.get("fields")})
    checks["balanced"] = {"unbalanced_journals": unbalanced}
    for j in unbalanced:
        problems.append({"code": "UNBALANCED_JOURNAL", "detail": f"journal {j}: debits != credits"})
    checks["trail_chain"] = trail_v
    if not trail_v["valid"]:
        problems.append({"code": "TRAIL_BROKEN", "detail": f"audit_trail breaks at seq {trail_v['broken_at_seq'] or trail_v['anchor_mismatch_at']}"})
    bad_anchor = [s for s, es, eh in trail_rows if es and hashes.get(es) != eh]
    checks["trail_anchors"] = {"rows_checked": len(trail_rows), "mismatched": bad_anchor[:20]}
    if bad_anchor:
        problems.append({"code": "ANCHOR_MISMATCH", "detail": f"{len(bad_anchor)} audit-trail row(s) point at erp_log "
                                                              f"entries that no longer exist as recorded"})
    hits = [{"detector": "D12", "code": p["code"], "object_type": "engagement", "object_id": engagement_id,
             "severity": 5, "impact_paise": 0, "reason": f"Integrity check failed: {p['detail']}.", "evidence": p}
            for p in problems]
    with db.borrow("audit", "system") as a:
        exists = a.execute("SELECT 1 FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    if exists:
        analytics.save_hits(engagement_id, f"D12-{config.now()}", hits, {"D12"})
        if problems:
            notify.emit("INTEGRITY_ALERT", {"problems": [p["code"] for p in problems][:20]}, engagement_id)
    return {"ok": not problems, "checks": checks, "problems": problems}

# ---------------------------------------------------------------- D8 + Fig. 2 attributes

def _requests_for(p, eid, doc_no):
    return [dict(r) for r in p.execute("SELECT * FROM evidence_requests WHERE engagement_id = ? AND about_doc_no = ?"
                                       " ORDER BY id", (eid, doc_no))]


def _norm(v):
    return re.sub(r"[\s,₹]", "", str(v or "")).upper().removeprefix("RS")


def test_sample(run_id, sample_no, actor, note=None):
    """D8 + the Fig. 2 attributes for one sample against the books, the portals and the client's evidence.
    -> {run_id, sample_no, attributes, exceptions, conclusion_proposed, next_steps}. Notes never change a result."""
    from app import analytics, money, register, trail
    eid = config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        s = a.execute("SELECT s.*, r.kind AS run_kind FROM samples s JOIN sample_runs r ON r.id = s.run_id WHERE"
                      " s.run_id = ? AND s.sample_no = ?", (run_id, sample_no)).fetchone()
        if s is None:
            raise LookupError("NOT_FOUND: no such sample; list them with list_audit_items(kind='samples')")
        s = dict(s)
        eng = dict(a.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone())
        own_hits = [dict(r) for r in a.execute("SELECT code, detector, severity FROM risk_hits WHERE object_id = ?",
                                               (s["doc_id"],))]
    changes = check_for_changes(eid)
    key = f"{run_id}#{sample_no}"
    stale = next((x for x in changes["stale_samples"] if f"{x['run_id']}#{x['sample_no']}" == key), None)
    is_cn = s["doc_type"] == "credit_note"
    with db.borrow("erp", "system") as e, db.borrow("ext", "system") as x:
        doc = dict(e.execute(f"SELECT * FROM {'credit_notes' if is_cn else 'invoices'} WHERE id = ?", (s["doc_id"],)).fetchone())
        doc_no = doc["cn_no"] if is_cn else doc["invoice_no"]
        lines = [dict(r) for r in e.execute(f"SELECT * FROM {'cn_lines' if is_cn else 'invoice_lines'} WHERE "
                                            f"{'cn_id' if is_cn else 'invoice_id'} = ?", (s["doc_id"],))]
        taxable = sum(l["taxable_paise"] for l in lines)
        tax = sum(l["igst_paise"] + l["cgst_paise"] + l["sgst_paise"] for l in lines)
        movs = [] if is_cn else [dict(r) for r in e.execute(
            "SELECT m.*, im.ewb_no FROM movements m JOIN invoice_movements im ON im.movement_id = m.id WHERE im.invoice_id = ?",
            (s["doc_id"],))]
        ewbs = [] if is_cn else [dict(r) for r in x.execute("SELECT * FROM ewaybills WHERE doc_no = ? AND supplier_gstin = ?",
                                                            (doc_no, doc["supplier_gstin"]))]
        all_invoice_nos = {r[0]: r[1] for r in e.execute("SELECT invoice_no, id FROM invoices")}
        goods = not is_cn and any(not str(l["hsn"]).startswith("99") and not l["item_id"].startswith("CHG") for l in lines)
        qty_by_no = {r[0]: r[1] for r in e.execute(
            "SELECT i.invoice_no, SUM(l.qty) FROM invoices i JOIN invoice_lines l ON l.invoice_id = i.id"
            " WHERE l.item_id NOT LIKE 'CHG%' AND l.hsn NOT LIKE '99%' GROUP BY i.id")}
    with db.borrow("pbc", "system") as p:
        reqs = _requests_for(p, eid, doc_no)
        subs = {r["id"]: [dict(t) for t in p.execute("SELECT * FROM submissions WHERE request_id = ? ORDER BY id", (r["id"],))]
                for r in reqs}
        other = defaultdict(set)                       # sha256 / text / ewb / irn already used by OTHER documents
        for r in p.execute("SELECT s.sha256, q.about_doc_no FROM submissions s JOIN evidence_requests q ON q.id = s.request_id"
                           " WHERE s.kind = 'EVIDENCE'"):
            if r[1] != doc_no:
                other["sha"].add(r[0])
        today = config.today()
        overdue = [r["id"] for r in reqs if r["status"] == "OPEN" and r["due_on"] < today]
    if overdue:
        with db.borrow("pbc", "system") as p, db.tx(p):
            p.executemany("UPDATE evidence_requests SET status = 'OVERDUE' WHERE id = ?", [(i,) for i in overdue])
    exceptions, docs_status, evidence_shas = [], {}, []
    other_texts, other_ewb, other_lr = _other_extracts(eid, doc_no)

    def exc(code, detail, **kw):
        exceptions.append({"code": code, "detail": detail, **kw})

    for r in reqs:
        kind = r["doc_kind"]
        got = subs.get(r["id"], [])
        if not got:
            docs_status[kind] = "NP"
            if r["id"] in overdue or r["status"] == "OVERDUE":
                exc("MISSING_DOCUMENT", f"{kind} requested ({r['id']}) is overdue")
            continue
        sub = got[-1]
        ext = extract(sub["id"])
        evidence_shas.append(sub["sha256"][:10])
        f = ext["fields"]
        if ext["instructions"]:
            exc("EVIDENCE_CONTAINS_INSTRUCTIONS", f"{kind} ({sub['id']}) contains instruction-like text; excluded from "
                                                  f"automatic matching", submission=sub["id"])
            docs_status[kind] = "✗"
            continue
        if ext["method"] == "NEEDS_MANUAL_REVIEW":
            docs_status[kind] = "NP"
            exc("NEEDS_MANUAL_REVIEW", f"{kind} ({sub['id']}) could not be machine-read", submission=sub["id"])
            continue
        n_before = len(exceptions)
        if kind not in ("LR", "POD"):                  # one LR / POD legitimately covers a consolidated load (rule below)
            if sub["sha256"] in other["sha"]:
                exc("REUSED_EVIDENCE", f"the same {kind} file was submitted for another document", submission=sub["id"])
            if ext["text_sha256"] and ext["text_sha256"] in other_texts:
                exc("REUSED_EVIDENCE", f"the same {kind} text was submitted for another document", submission=sub["id"])
        for k, v in (ext["declared"] or {}).items():
            if k in f and k != "doc_kind" and _norm(v) != _norm(f[k]):
                exc("DECLARED_VS_EXTRACTED", f"the client declared {k} differently from what the {kind} says",
                    field=k, submission=sub["id"])
        if kind in ("INVOICE", "CREDIT_NOTE"):
            dno = f.get("doc_no")
            if dno and dno != doc_no:
                exc("BELONGS_TO_OTHER_TXN" if dno in all_invoice_nos else "DOC_FIELD_MISMATCH",
                    f"the {kind.lower()} copy is for another document", field="doc_no", document=dno, sor=doc_no)
            want = {"doc_date": doc["cn_date"] if is_cn else doc["invoice_date"],
                    "taxable": money.to_rupees(taxable) if not is_cn else None,
                    "total": money.to_rupees(taxable + tax + (0 if is_cn else doc["round_off_paise"])),
                    "buyer_gstin": None if is_cn else doc["buyer_gstin"], "irn": doc["irn"]}
            for k, v in want.items():
                if v is not None and k in f and _norm(f[k]) != _norm(v):
                    exc("IRN_MISMATCH" if k == "irn" else "DOC_FIELD_MISMATCH", f"{k} on the document differs from the "
                        f"books", field=k, document=f[k], sor=v)
        elif kind == "EWAY_BILL":
            no = f.get("ewb_no")
            with db.borrow("ext", "system") as x:
                row = x.execute("SELECT * FROM ewaybills WHERE ewb_no = ?", (no,)).fetchone() if no else None
            if not no or row is None:
                exc("EWB_NOT_ON_PORTAL", "the e-way bill on the document does not exist on the portal", document=no)
            else:
                if row["doc_no"] != doc_no:
                    exc("BELONGS_TO_OTHER_TXN", "the e-way bill belongs to another invoice", document=row["doc_no"],
                        sor=doc_no)
                for k, col in (("value", "value_paise"), ("vehicle_no", "vehicle_no"), ("ref_doc_date", "doc_date")):
                    v = money.to_rupees(row[col]) if col == "value_paise" else row[col]
                    if k in f and _norm(f[k]) != _norm(v):
                        exc("DOC_FIELD_MISMATCH", f"{k} on the e-way bill copy differs from the portal", field=k,
                            document=f[k], sor=v)
                if no in other_ewb:
                    exc("REUSED_EVIDENCE", "the same e-way bill was produced for another document", document=no)
        elif kind in ("LR", "POD"):
            lr = f.get("lr_no")
            m = next((m for m in movs if m["lr_no"] == lr), None) if lr else None
            refs = f.get("invoice_refs") or []
            if lr and m is None:
                exc("DOC_FIELD_MISMATCH", f"the {kind} number is not on any movement of this invoice", field="lr_no",
                    document=lr, sor=[m["lr_no"] for m in movs])
            if refs and doc_no not in refs:
                exc("BELONGS_TO_OTHER_TXN", f"the {kind} covers other invoices, not this one", document=refs)
            # the same LR number on another document is an exception only if it omits this invoice or carries less
            # than the invoices it names (a genuine consolidated load stays clean; 05 D8)
            if kind == "LR" and lr and lr in other_lr and (doc_no not in refs or (
                    str(f.get("qty", "")).isdigit() and sum(qty_by_no.get(n, 0) for n in refs) > int(f["qty"]))):
                exc("REUSED_EVIDENCE", "the same LR was produced for another document and does not cover this invoice "
                                       "or its quantity", document=lr)
            if m:
                if kind == "LR":
                    for k, col in (("lr_date", "lr_date"), ("vehicle_no", "vehicle_no")):
                        if k in f and m[col] and _norm(f[k]) != _norm(m[col]):
                            exc("DOC_FIELD_MISMATCH", f"{k} on the LR differs from the movement", field=k,
                                document=f[k], sor=m[col])
                    act = [e_ for e_ in ewbs if e_["status"] == "ACT"]
                    if act and "vehicle_no" in f and all(_norm(f["vehicle_no"]) != _norm(e_["vehicle_no"]) for e_ in act):
                        exc("LR_VEHICLE_NE_EWB_VEHICLE", "the LR's vehicle is not the e-way bill's vehicle")
                if kind == "POD" and "delivered_on" in f and m["delivered_on"] and f["delivered_on"] != m["delivered_on"]:
                    exc("DOC_FIELD_MISMATCH", "the POD date differs from the books", field="delivered_on",
                        document=f["delivered_on"], sor=m["delivered_on"])
        docs_status[kind] = "✗" if len(exceptions) > n_before else "✓"
    for k in ("INVOICE", "EWAY_BILL", "LR", "POD"):
        if is_cn:
            break
        if k not in docs_status:
            docs_status[k] = "NA" if (k != "INVOICE" and not goods) or (k == "EWAY_BILL" and taxable + tax <=
                                                                         config.EWB_THRESHOLD_PAISE) else "NP"
    # Fig. 2 attributes from the books, the register and the portals (independent of the client's copies)
    codes = {h["code"] for h in own_hits if h["severity"] >= 3}
    attrs = {
        "correct_amount": "✗" if codes & {"TAXABLE_DIFF", "TOTAL_DIFF", "REVENUE_POSTING_DIFF", "EWB_VALUE_MISMATCH",
                                          "GSTR1_VALUE_DIFF", "QTY_SHORT"} else "✓",
        "correct_party": "✗" if codes & {"CUSTOMER_DIFF", "GSTIN_DIFF", "DISPATCH_PARTY_MISMATCH", "THIRD_PARTY_PAYER",
                                         "PAYER_IS_RP"} else "✓",
        "correct_sales_gl": "✗" if codes & {"DUPLICATE_POSTING", "REVENUE_POSTING_DIFF", "UNUSUAL_CONTRA"} else "✓",
        "correct_period": "✗" if codes & {"PREMATURE", "DELAYED", "DATE_DIFF", "FY_DIFF", "BACKDATED_ENTRY",
                                          "POST_PERIOD_REVERSAL"} else ("?" if "CUTOFF_UNRESOLVED" in codes else "✓"),
        "correct_tax": "✗" if codes & {"TAX_TYPE_WRONG", "TAX_RATE_WRONG", "TAX_DIFF", "IRN_MISSING", "IRN_MISMATCH",
                                       "NOT_IN_GSTR1"} else "✓",
    }
    hard = [x for x in exceptions if x["code"] not in ("NEEDS_MANUAL_REVIEW",)]
    if stale:
        conclusion = "STALE"
    elif hard or "✗" in attrs.values():
        conclusion = "EXCEPTION"
    elif "NP" in docs_status.values() or "?" in attrs.values():
        conclusion = "PENDING_EVIDENCE"
    else:
        conclusion = "NO_EXCEPTION"
    result = {"documents": docs_status, "attributes": attrs, "exceptions": exceptions, "evidence": evidence_shas,
              "stale": stale["reasons"] if stale else [], "analytics_codes": sorted(codes)}
    with db.borrow("erp", "system") as e:
        head = chain.head(e, "erp_log")[0]
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute("UPDATE samples SET test_result_json = ?, tested_at = ?, tested_seq = ?, conclusion_proposed = ?,"
                  " notes = CASE WHEN ? IS NULL THEN notes ELSE COALESCE(notes || char(10), '') || ? END"
                  " WHERE run_id = ? AND sample_no = ?",
                  (json.dumps(result, default=str), config.now(), head, conclusion, note,
                   f"[{config.now()} {actor}] {note}" if note else None, run_id, sample_no))
        a.execute("DELETE FROM risk_hits WHERE engagement_id = ? AND detector = 'D8' AND object_id = ?", (eid, s["doc_id"]))
    d8 = [{"detector": "D8", "code": x["code"], "object_type": s["doc_type"], "object_id": s["doc_id"],
           "severity": 4 if x["code"] in ("NEEDS_MANUAL_REVIEW", "MISSING_DOCUMENT", "DECLARED_VS_EXTRACTED") else 5,
           "impact_paise": taxable, "reason": f"Sample {run_id}#{sample_no} ({s['doc_id']}): {x['detail']}.",
           "evidence": x} for x in exceptions]
    if d8:
        with db.borrow("audit", "system") as a, db.tx(a):
            at = config.now()
            a.executemany("INSERT INTO risk_hits(engagement_id, analytics_run, detector, code, object_type, object_id,"
                          " severity, impact_paise, reason, evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          [(eid, f"D8-{run_id}#{sample_no}", h["detector"], h["code"], h["object_type"], h["object_id"],
                            h["severity"], h["impact_paise"], h["reason"], json.dumps(h["evidence"], default=str), at)
                           for h in d8])
    trail.anchor(eid, "TEST")
    nxt = [{"tool": "propose_finding", "example_args": {"category": "…", "doc_refs": [s["doc_id"]]},
            "why": "record the exception as a PROPOSED finding"}] if conclusion == "EXCEPTION" else []
    if conclusion == "PENDING_EVIDENCE":
        nxt.append({"tool": "list_evidence_requests", "example_args": {"status": "OPEN"}, "why": "documents still awaited"})
    return {"run_id": run_id, "sample_no": sample_no, "doc_id": s["doc_id"], "attributes": {**attrs, **docs_status},
            "exceptions": exceptions, "conclusion_proposed": conclusion, "next_steps": nxt}


def _other_extracts(eid, doc_no):
    """Normalised texts, e-way bill and LR numbers already produced for OTHER documents (REUSED_EVIDENCE)."""
    texts, ewbs, lrs = set(), set(), set()
    with db.borrow("pbc", "system") as p:
        rows = [(r[0], r[1]) for r in p.execute("SELECT s.id, q.about_doc_no FROM submissions s JOIN evidence_requests q"
                                                " ON q.id = s.request_id WHERE s.kind = 'EVIDENCE' AND q.engagement_id = ?",
                                                (eid,))]
    for sid, about in rows:
        if about == doc_no:
            continue
        x = extract(sid)
        if x["text_sha256"]:
            texts.add(x["text_sha256"])
        if x["fields"].get("ewb_no"):
            ewbs.add(x["fields"]["ewb_no"])
        if x["fields"].get("lr_no") and x["fields"].get("document", "").upper().startswith("LORRY"):
            lrs.add(x["fields"]["lr_no"])
    return texts, ewbs, lrs
