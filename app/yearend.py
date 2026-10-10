"""Year-end layer (vault/13 MT-6): how the year developed month by month, which March documents were reversed,
returned, dispatched, delivered or keyed in after the period end, and a year-end freeze (anchor + snapshot run).

Continuous audit (Apr-Feb) is erp.write_doc -> risk_graph.on_event; this module is the March / April view (SA 315
risk identification, SA 330 cut-off response, SA 560 subsequent events). Read-only on the books; ids and codes only.
"""
import json
from collections import defaultdict
from datetime import date

from app import config, db, money, risk_graph


def _eng(a, eid):
    r = a.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone()
    if r is None:
        raise LookupError("NOT_FOUND: no engagement yet. Upload the register first (upload_sales_register)")
    return dict(r)


def _months(start, end):
    y, m = int(start[:4]), int(start[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= end[:7]:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _plus_months(iso, n):
    y, m = int(iso[:4]), int(iso[5:7]) + n
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}-28"


_DATE_SQL = {"invoice": "SELECT id, invoice_date, party_id FROM invoices",
             "credit_note": "SELECT id, cn_date, party_id FROM credit_notes",
             "settlement": "SELECT id, settled_on, party_id FROM settlements",
             "purchase_order": "SELECT id, po_date, vendor_id FROM purchase_orders",
             "goods_receipt": "SELECT g.id, g.received_on, p.vendor_id FROM goods_receipts g JOIN purchase_orders p"
                              " ON p.id = g.po_id",
             "purchase_bill": "SELECT id, bill_date, vendor_id FROM purchase_bills",
             "journal": "SELECT CAST(no AS TEXT), voucher_date, NULL FROM journals"}


def _object_dates(e):
    """(object_type, id) -> (date, party_id) for every dated document a risk hit can sit on."""
    out = {}
    for t, sql in _DATE_SQL.items():
        for oid, d, pid in e.execute(sql):
            out[(t, str(oid))] = (d, pid)
    return out


def _hit_key(h):
    if h["object_type"] == "register_row":
        sid = ((json.loads(h["evidence_json"] or "{}") or {}).get("sor") or {}).get("id")
        if sid:
            return "invoice", sid
    return h["object_type"], h["object_id"]


def timeline(party_id=None, engagement_id=None):
    """-> {months: [{ym, sales_paise, receipts_paise, cn_paise, open_exceptions, exceptions_paise, band, band_source}],
    period_start, period_end, performance_materiality_paise}. Covers the period and two months after it (subsequent
    events). band: the AuditGraph COMPANY snapshot taken in that month when one exists, else open exposure to date vs
    performance materiality (>= PM HIGH, >= PM/2 MODERATE). Open = severity >= 4 hits not in an EXPLAINED case."""
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        eng = _eng(a, eid)
        hits = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ? AND severity >= 4", (eid,))]
        explained = set()
        for (ids,) in a.execute("SELECT hit_ids_json FROM cases WHERE engagement_id = ? AND status = 'EXPLAINED'", (eid,)):
            explained |= set(json.loads(ids))
        snaps = {r[0]: r[1] for r in a.execute(
            "SELECT substr(at, 1, 7), band FROM risk_snapshots WHERE object_type = 'COMPANY' ORDER BY at")}
    last = min(_plus_months(eng["period_end"], 2), config.today())
    months = _months(eng["period_start"], last)
    pf, args = ("AND i.party_id = ?", [party_id]) if party_id else ("", [])
    with db.borrow("erp", "system") as e:
        sales = dict(e.execute(f"SELECT substr(i.invoice_date, 1, 7), SUM(l.taxable_paise + l.igst_paise + l.cgst_paise +"
                               f" l.sgst_paise) FROM invoices i JOIN invoice_lines l ON l.invoice_id = i.id WHERE i.status ="
                               f" 'ISSUED' {pf} GROUP BY 1", args))
        receipts = dict(e.execute(f"SELECT substr(settled_on, 1, 7), SUM(amount_paise) FROM settlements i WHERE direction ="
                                  f" 'RECEIPT' {pf} GROUP BY 1", args))
        cns = dict(e.execute(f"SELECT substr(i.cn_date, 1, 7), SUM(l.taxable_paise + l.igst_paise + l.cgst_paise +"
                             f" l.sgst_paise) FROM credit_notes i JOIN cn_lines l ON l.cn_id = i.id WHERE i.status = 'ISSUED'"
                             f" {pf} GROUP BY 1", args))
        dates = _object_dates(e)
        pm = risk_graph._context(eng, e)[0]
    per_month, best = defaultdict(int), {}
    for h in hits:
        if h["id"] in explained:
            continue
        k = _hit_key(h)
        d = dates.get(k)
        if d is None or (party_id and d[1] != party_id):
            continue
        per_month[d[0][:7]] += 1
        best[k] = (d[0][:7], max(best.get(k, ("", 0))[1], h["impact_paise"] or 0))
    out = []
    for ym in months:
        exposure = sum(v for m, v in best.values() if m <= ym)
        if ym in snaps and not party_id:
            band, src = snaps[ym], "snapshot"
        else:
            band = "HIGH" if exposure >= pm else "MODERATE" if exposure >= pm / 2 else "LOW"
            src = "exposure"
        out.append({"ym": ym, "sales_paise": sales.get(ym, 0), "receipts_paise": receipts.get(ym, 0),
                    "cn_paise": cns.get(ym, 0), "open_exceptions": per_month.get(ym, 0), "exceptions_paise": exposure,
                    "band": band, "band_source": src, "post_period": ym > eng["period_end"][:7]})
    return {"party_id": party_id, "period_start": eng["period_start"], "period_end": eng["period_end"],
            "performance_materiality_paise": pm, "months": out}


def march_april_links(engagement_id=None):
    """-> {period_end, items: [{march_doc, april_events, hits, affected_paise}]}: every document dated in the last month
    of the period with something after the period end: a credit note, a cancellation, a dispatch or delivery, being
    keyed in (erp_log), or (purchases) the vendor's bill. affected = the largest serious hit impact per object."""
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        eng = _eng(a, eid)
        hits = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ?", (eid,))]
    end = eng["period_end"]
    month = end[:7]
    docs, events = {}, defaultdict(list)
    with db.borrow("erp", "system") as e:
        for r in e.execute("SELECT i.id, i.invoice_no, i.invoice_date, i.party_id, i.status, i.cancelled_on,"
                           " COALESCE(SUM(l.taxable_paise + l.igst_paise + l.cgst_paise + l.sgst_paise), 0) AS total"
                           " FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id = i.id WHERE substr(i.invoice_date, 1, 7) = ?"
                           " GROUP BY i.id", (month,)):
            docs[("invoice", r["id"])] = {"doc_type": "invoice", "doc_id": r["id"], "doc_no": r["invoice_no"],
                                          "date": r["invoice_date"], "party_id": r["party_id"], "amount_paise": r["total"]}
            if r["status"] == "CANCELLED" and (r["cancelled_on"] or "") > end:
                events[("invoice", r["id"])].append({"kind": "CANCELLATION", "id": r["id"], "date": r["cancelled_on"]})
        inv = {k[1] for k in docs}
        for r in e.execute("SELECT l.invoice_id, c.id, c.cn_no, c.cn_date, c.reason, c.return_movement_id,"
                           " SUM(l.taxable_paise + l.igst_paise + l.cgst_paise + l.sgst_paise) FROM cn_lines l JOIN credit_notes c"
                           " ON c.id = l.cn_id WHERE c.cn_date > ? AND c.status = 'ISSUED' AND l.invoice_id IS NOT NULL"
                           " GROUP BY l.invoice_id, c.id", (end,)):
            if r[0] in inv:
                events[("invoice", r[0])].append({"kind": "CREDIT_NOTE", "id": r[1], "doc_no": r[2], "date": r[3],
                                                  "reason": r[4], "return_movement_id": r[5], "amount_paise": r[6]})
        # a delivery after the period end matters only when control passes on delivery (FOR destination)
        for r in e.execute("SELECT im.invoice_id, m.id, m.moved_on, m.delivered_on, so.delivery_terms FROM invoice_movements im"
                           " JOIN movements m ON m.id = im.movement_id JOIN invoices i ON i.id = im.invoice_id LEFT JOIN"
                           " sales_orders so ON so.id = i.so_id WHERE m.direction = 'OUT' AND (m.moved_on > ? OR m.delivered_on > ?)",
                           (end, end)):
            if r[0] not in inv:
                continue
            if r[2] > end:
                events[("invoice", r[0])].append({"kind": "LATE_DISPATCH", "id": r[1], "date": r[2]})
            elif r[3] and r[3] > end and r[4] == "FOR_DESTINATION":
                events[("invoice", r[0])].append({"kind": "DELIVERED_AFTER_PERIOD", "id": r[1], "date": r[3]})
        for r in e.execute("SELECT doc_id, MIN(recorded_at) FROM erp_log WHERE doc_type = 'invoice' AND action = 'CREATE'"
                           " GROUP BY doc_id"):
            if r[0] in inv and r[1][:10] > end:
                events[("invoice", r[0])].append({"kind": "ENTERED_AFTER_PERIOD", "id": r[0], "date": r[1][:10]})
        # purchases: goods received in the last month, billed after the period end
        for r in e.execute("SELECT g.id, g.grn_no, g.received_on, g.qty, g.po_id, p.vendor_id, p.rate_paise FROM goods_receipts g"
                           " JOIN purchase_orders p ON p.id = g.po_id WHERE substr(g.received_on, 1, 7) = ? AND g.kind = 'RECEIPT'",
                           (month,)):
            bills = [dict(b) for b in e.execute("SELECT id, bill_no, bill_date, taxable_paise + tax_paise AS total FROM"
                                                " purchase_bills WHERE po_id = ?", (r["po_id"],))]
            if bills and all(b["bill_date"] > end for b in bills):
                k = ("goods_receipt", r["id"])
                docs[k] = {"doc_type": "goods_receipt", "doc_id": r["id"], "doc_no": r["grn_no"], "date": r["received_on"],
                           "party_id": r["vendor_id"], "amount_paise": r["qty"] * r["rate_paise"], "po_id": r["po_id"]}
                events[k] += [{"kind": "BILL_AFTER_PERIOD", "id": b["id"], "doc_no": b["bill_no"], "date": b["bill_date"],
                               "amount_paise": b["total"]} for b in bills]
    by_obj = defaultdict(list)
    for h in hits:
        by_obj[_hit_key(h)].append(h)
    items = []
    for k, evs in events.items():
        related = [k] + [("credit_note", x["id"]) for x in evs if x["kind"] == "CREDIT_NOTE"]
        if k[0] == "goods_receipt":
            related.append(("purchase_order", docs[k]["po_id"]))
        hs = [h for r in related for h in by_obj.get(r, [])]
        best = {}
        for h in hs:
            if h["severity"] >= 4:
                kk = (h["object_type"], h["object_id"])
                best[kk] = max(best.get(kk, 0), h["impact_paise"] or 0)
        affected = sum(best.values())
        items.append({"march_doc": docs[k], "april_events": sorted(evs, key=lambda x: (x["date"] or "", x["kind"])),
                      "hits": [{"detector": h["detector"], "code": h["code"], "severity": h["severity"],
                                "impact_paise": h["impact_paise"], "object_type": h["object_type"],
                                "object_id": h["object_id"]} for h in sorted(hs, key=lambda h: (-h["severity"], h["id"]))],
                      "affected_paise": affected, "affected_formatted": money.fmt_inr(affected)})
    items.sort(key=lambda i: (-i["affected_paise"], i["march_doc"]["date"], i["march_doc"]["doc_id"]))
    return {"period_end": end, "items": items}


def freeze(engagement_id=None):
    """Year-end freeze: a full analytics run (re-baselined hits, cases and an AuditGraph snapshot run) and an anchor
    on both chain heads. The anchor uses label PERIODIC (03 anchors CHECK unchanged). -> {anchor, analytics_run,
    snapshot_run, company, cases}."""
    from app import analytics, trail
    eid = engagement_id or config.ENGAGEMENT_ID
    run = analytics.run_all(eid)
    with db.borrow("audit", "system") as a:
        snap = a.execute("SELECT run_id FROM risk_snapshots WHERE run_id LIKE 'RG-%' ORDER BY at DESC, rowid DESC"
                         " LIMIT 1").fetchone()
    anc = trail.anchor(eid, "PERIODIC")
    return {"anchor": anc, "analytics_run": run["run_id"], "snapshot_run": snap[0] if snap else None,
            "company": run["company"], "cases": run.get("cases"), "frozen_at": anc["at"],
            "as_of": date.fromisoformat(config.today()).isoformat()}
