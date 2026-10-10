"""The client's system of record: write_doc + every business service (07 §4, 03 §2).

Every ERP write ends with write_doc in the same transaction: it appends the document's full after-image
(header + child rows, canonical JSON) to the hash-chained erp_log. After the transaction commits, the queued
events go to risk_graph.on_event (05 §19.6): best-effort, never blocking or rolling back the business write.
"""
import json
import logging

from app import chain, config

log = logging.getLogger("auditpilot.erp")
STUB = True    # services land in queue item 3 (SH-4); write_doc and the integrity helpers below are real

# doc_type -> (table, pk column, ((child table, fk column, order column), ...))
DOCS = {
    "party": ("parties", "id", ()),
    "party_link": ("party_links", "id", ()),
    "item": ("items", "id", ()),
    "scheme": ("schemes", "id", ()),
    "sales_order": ("sales_orders", "id", (("so_lines", "so_id", "line_no"),)),
    "movement": ("movements", "id", (("movement_lines", "movement_id", "item_id"),
                                     ("invoice_movements", "movement_id", "invoice_id"))),
    "invoice": ("invoices", "id", (("invoice_lines", "invoice_id", "line_no"),)),
    "credit_note": ("credit_notes", "id", (("cn_lines", "cn_id", "line_no"),)),
    "settlement": ("settlements", "id", ()),
    "purchase_bill": ("purchase_bills", "id", ()),
    "account": ("accounts", "code", ()),
    "journal": ("journals", "no", (("journal_lines", "journal_no", "line_no"),)),
}

# ---------------------------------------------------------------- the edit log

def image(conn, doc_type, doc_id):
    """The document as it is now: {"header": row, "<child table>": [rows]}; None if it doesn't exist."""
    table, pk, children = DOCS[doc_type]
    r = conn.execute(f"SELECT * FROM {table} WHERE {pk} = ?", (doc_id,)).fetchone()
    if r is None:
        return None
    out = {"header": dict(r)}
    for ctab, fk, order in children:
        out[ctab] = [dict(c) for c in conn.execute(f"SELECT * FROM {ctab} WHERE {fk} = ? ORDER BY {order}", (doc_id,))]
    return out


def _last_after(conn, doc_type, doc_id):
    r = conn.execute("SELECT after_json FROM erp_log WHERE doc_type = ? AND doc_id = ? ORDER BY seq DESC LIMIT 1",
                     (doc_type, str(doc_id))).fetchone()
    return r[0] if r else None


_PENDING = {}     # id(conn) -> [(doc_type, doc_id, seq)] waiting for the transaction to commit


def write_doc(conn, actor, role, tool, action, doc_type, doc_id, reason=None):
    """Append the doc's after-image to erp_log (03 §6). Call it after writing the typed rows, inside the
    transaction. before_json = the previous after_json of this doc. Returns the erp_log seq."""
    img = image(conn, doc_type, doc_id)
    if img is None:
        raise ValueError(f"NOT_FOUND: {doc_type} {doc_id} was not written before write_doc")
    seq, _h = chain.append(conn, "erp_log", {
        "recorded_at": config.now(), "actor": actor, "role": role, "tool": tool, "action": action,
        "doc_type": doc_type, "doc_id": str(doc_id), "before_json": _last_after(conn, doc_type, doc_id),
        "after_json": chain.canon(img), "reason": reason})
    _PENDING.setdefault(id(conn), []).append((doc_type, str(doc_id), seq))
    return seq


def flush_events(conn):
    """After COMMIT: hand each logged document to AuditGraph. Errors are logged, never raised."""
    from app import risk_graph
    out = []
    for doc_type, doc_id, seq in _PENDING.pop(id(conn), []):
        try:
            out += risk_graph.on_event(doc_type, doc_id, seq) or []
        except Exception:  # noqa: BLE001 - best-effort by contract (05 §19.6)
            log.exception("risk_graph.on_event failed for %s %s (seq %s)", doc_type, doc_id, seq)
    return out


def discard_events(conn):
    _PENDING.pop(id(conn), None)

# ---------------------------------------------------------------- integrity helpers (used by evidence.verify_integrity)

def out_of_band(conn):
    """Documents whose current rows differ from their latest erp_log after-image (03 §6 check 2): an edit made
    outside the application (direct SQLite). kind = CHANGED | MISSING (logged, now gone) | UNLOGGED (no log row)."""
    latest = {}
    for r in conn.execute("SELECT doc_type, doc_id, seq, after_json, actor FROM erp_log WHERE seq IN "
                          "(SELECT MAX(seq) FROM erp_log GROUP BY doc_type, doc_id)"):
        latest[(r[0], r[1])] = (r[2], r[3], r[4])
    out = []
    for doc_type, (table, pk, _c) in DOCS.items():
        ids = [str(r[0]) for r in conn.execute(f"SELECT {pk} FROM {table}")]
        for doc_id in ids:
            got = latest.pop((doc_type, doc_id), None)
            if got is None:
                out.append({"doc_type": doc_type, "doc_id": doc_id, "kind": "UNLOGGED", "seq": None})
                continue
            seq, after, actor = got
            now = image(conn, doc_type, doc_id)
            if chain.canon(now) != after:
                before, cur = json.loads(after), now
                out.append({"doc_type": doc_type, "doc_id": doc_id, "kind": "CHANGED", "seq": seq,
                            "last_logged_by": actor, "fields": _diff(before, cur)})
    for (doc_type, doc_id), (seq, _a, actor) in latest.items():
        out.append({"doc_type": doc_type, "doc_id": doc_id, "kind": "MISSING", "seq": seq, "last_logged_by": actor})
    return out


def _diff(before, after):
    """{'header.lr_date': [old, new], 'invoice_lines[1].qty': [old, new]} between two images."""
    out = {}
    for k in sorted(set(before) | set(after)):
        b, a = before.get(k), after.get(k)
        if isinstance(b, dict) or isinstance(a, dict):
            b, a = b or {}, a or {}
            for f in sorted(set(b) | set(a)):
                if b.get(f) != a.get(f):
                    out[f"{k}.{f}"] = [b.get(f), a.get(f)]
        elif b != a:
            for i in range(max(len(b or []), len(a or []))):
                rb = (b or [])[i] if i < len(b or []) else None
                ra = (a or [])[i] if i < len(a or []) else None
                if rb != ra:
                    for f in sorted(set(rb or {}) | set(ra or {})):
                        if (rb or {}).get(f) != (ra or {}).get(f):
                            out[f"{k}[{i}].{f}"] = [(rb or {}).get(f), (ra or {}).get(f)]
    return out

# ---------------------------------------------------------------- services (queue item 3)

SERVICES = ("create_party", "link_parties", "create_item", "create_lead", "create_scheme", "create_sales_order",
            "issue_invoice", "generate_eway_bill", "record_dispatch", "record_delivery", "issue_credit_note",
            "record_receipt", "record_payment", "record_purchase", "post_journal_entry", "file_gstr1", "file_gstr3b",
            "amend_record", "cancel_document", "import_records", "export_sales_register", "render_document")


def _stub(name):
    def service(actor, role, **args):
        return {"result": {}, "next_steps": []}
    service.__name__ = service.__qualname__ = name
    service.__doc__ = f"erp.{name}: STUB until SH-4."
    return service


for _name in SERVICES:
    globals()[_name] = _stub(_name)
