"""Population procedures over 100% of the books and portals (05): D1/D2 (via related_parties), D3, D4, D5, D6, D7,
D9, D13, D14 -> audit.risk_hits. D10 (cycles) is AuditGraph's (risk_graph.py, 05 §19.4).

Deterministic rules over structured fields decide every hit; LLMs never do (05 §0). Each hit carries a plain-language,
server-written reason that cites ids and system-assigned numbers only (client text stays in evidence), a severity
1-5 and a ₹ impact. Concentration codes (D5) are risk points, not findings, unless D3/D4/D9 corroborate them.
"""
import json
import re
import statistics
from collections import defaultdict
from datetime import date, timedelta

from app import config, db, money

ALL = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D9", "D13", "D14", "D15")
_SAFE = re.compile(r"^[A-Za-z0-9/\-_. ]{1,40}$")


def save_hits(engagement_id, run_id, hits, detectors):
    """Replace this engagement's hits for `detectors` with `hits` (risk_hit dicts, 07 §4). Returns the count."""
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute(f"DELETE FROM risk_hits WHERE engagement_id = ? AND detector IN ({','.join('?' * len(detectors))})",
                  (engagement_id, *sorted(detectors)))
        at = config.now()
        a.executemany("INSERT INTO risk_hits(engagement_id, analytics_run, detector, code, object_type, object_id, severity,"
                      " impact_paise, reason, evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      [(engagement_id, run_id, h["detector"], h["code"], h["object_type"], str(h["object_id"]),
                        h["severity"], abs(int(h.get("impact_paise") or 0)), h["reason"],
                        json.dumps(h.get("evidence"), sort_keys=True, default=str), at) for h in hits])
    return len(hits)


def _hit(det, code, otype, oid, sev, impact, reason, evidence=None):
    return {"detector": det, "code": code, "object_type": otype, "object_id": str(oid), "severity": sev,
            "impact_paise": abs(int(impact or 0)), "reason": reason, "evidence": evidence or {}}


def _inr(p):
    return money.fmt_inr(p)


def _ref(inv):
    """'invoice G2/0391/25 (INV-000391)': the number only when it is a plain system-style number (no client text)."""
    no = inv.get("invoice_no") or inv.get("cn_no") or ""
    return f"{no} ({inv['id']})" if _SAFE.match(no) else inv["id"]


def _d(s):
    return date.fromisoformat(s[:10])

# ---------------------------------------------------------------- population

def load_population(e, x, party_ids=None, period_end=None):
    """Everything the detectors read, in a handful of queries (erp + ext, read-only). party_ids narrows the
    documents to those customers (AuditGraph's per-event update); masters and portals stay whole."""
    P = {"narrow": bool(party_ids)}
    pp = list(party_ids or ())
    inlist = f"({','.join('?' * len(pp))})"
    inv_f = f" WHERE party_id IN {inlist}" if pp else ""
    line_f = f" WHERE l.invoice_id IN (SELECT id FROM invoices WHERE party_id IN {inlist})" if pp else ""
    P["invoices"] = {r["id"]: dict(r) for r in e.execute("SELECT * FROM invoices" + inv_f, pp)}
    lines = defaultdict(list)
    for r in e.execute("SELECT l.*, i.gst_rate_bp AS item_rate, i.cost_paise FROM invoice_lines l JOIN items i"
                       " ON i.id = l.item_id" + line_f + " ORDER BY invoice_id, line_no", pp):
        lines[r["invoice_id"]].append(dict(r))
    for iid, inv in P["invoices"].items():
        ls = lines.get(iid, [])
        inv["lines"] = ls
        inv["taxable"] = sum(l["taxable_paise"] for l in ls)
        inv["igst"], inv["cgst"], inv["sgst"] = (sum(l[k] for l in ls) for k in ("igst_paise", "cgst_paise", "sgst_paise"))
        inv["tax"] = inv["igst"] + inv["cgst"] + inv["sgst"]
        inv["value"] = inv["taxable"] + inv["tax"]                    # incl. tax, before round-off (Rule 138 value)
        inv["goods"] = any(not str(l["hsn"]).startswith("99") and not l["item_id"].startswith("CHG") for l in ls)
        inv["gross"] = sum(l["qty"] * l["rate_paise"] for l in ls if not l["item_id"].startswith("CHG"))
        inv["discount"] = sum(l["discount_paise"] for l in ls if not l["item_id"].startswith("CHG"))
    sel = f"(SELECT id FROM invoices WHERE party_id IN {inlist})"
    P["so"] = {r["id"]: dict(r) for r in e.execute("SELECT * FROM sales_orders" + inv_f, pp)}
    mov_f = f" WHERE party_id IN {inlist} OR id IN (SELECT movement_id FROM invoice_movements WHERE invoice_id IN {sel})" \
        if pp else ""
    P["movements"] = {r["id"]: dict(r, lines={}) for r in e.execute("SELECT * FROM movements" + mov_f, pp + pp)}
    for r in e.execute("SELECT * FROM movement_lines" + (f" WHERE movement_id IN (SELECT id FROM movements{mov_f})"
                                                         if pp else ""), pp + pp):
        P["movements"][r["movement_id"]]["lines"][r["item_id"]] = r["qty"]
    P["inv_mov"] = defaultdict(list)
    P["mov_inv"] = defaultdict(list)
    for r in e.execute("SELECT * FROM invoice_movements" + (f" WHERE invoice_id IN {sel}" if pp else ""), pp):
        P["inv_mov"][r["invoice_id"]].append(dict(r))
        P["mov_inv"][r["movement_id"]].append(r["invoice_id"])
    P["parties"] = {r["id"]: dict(r) for r in e.execute("SELECT * FROM parties")}
    P["items"] = {r["id"]: dict(r) for r in e.execute("SELECT * FROM items")}
    P["schemes"] = {r["id"]: dict(r) for r in e.execute("SELECT * FROM schemes")}
    P["settle"] = defaultdict(list)
    for r in e.execute("SELECT * FROM settlements WHERE direction = 'RECEIPT' AND doc_type = 'INVOICE'"
                       + (f" AND doc_id IN {sel}" if pp else ""), pp):
        P["settle"][r["doc_id"]].append(dict(r))
    P["cns"] = {r["id"]: dict(r, lines=[]) for r in e.execute("SELECT * FROM credit_notes" + inv_f, pp)}
    for r in e.execute("SELECT * FROM cn_lines" + (f" WHERE cn_id IN (SELECT id FROM credit_notes WHERE party_id IN"
                                                   f" {inlist})" if pp else "") + " ORDER BY cn_id, line_no", pp):
        P["cns"][r["cn_id"]]["lines"].append(dict(r))
    P["revenue_accounts"] = {r[0] for r in e.execute("SELECT code FROM accounts WHERE is_revenue = 1")}
    jf = (f" WHERE source_id IN {sel} OR source_id IN (SELECT id FROM credit_notes WHERE party_id IN {inlist})"
          if pp else "")
    P["journals"] = {r["no"]: dict(r, lines=[]) for r in e.execute("SELECT * FROM journals" + jf, pp + pp)}
    for r in e.execute("SELECT * FROM journal_lines" + (f" WHERE journal_no IN (SELECT no FROM journals{jf})" if pp else "")
                       + " ORDER BY journal_no, line_no", pp + pp):
        P["journals"][r["journal_no"]]["lines"].append(dict(r))
    if period_end:                                      # D13 needs the first post-period entry even in a narrow load
        r = e.execute("SELECT MIN(l.seq) FROM erp_log l JOIN invoices i ON l.doc_type = 'invoice' AND l.doc_id = i.id"
                      " AND l.action = 'CREATE' WHERE i.invoice_date > ?", (period_end,)).fetchone()
        P["first_after_seq"] = r[0]
    ids = list(P["invoices"]) + list(P["cns"]) + [str(j) for j in P["journals"]] + list(P["movements"])
    P["created"], P["pod_recorded"], P["log_role"] = {}, {}, {}
    for r in e.execute("SELECT seq, recorded_at, role, action, doc_type, doc_id, reason FROM erp_log"
                       " WHERE doc_type IN ('invoice', 'credit_note', 'journal', 'movement')"
                       + (f" AND doc_id IN ({','.join('?' * len(ids))})" if pp and ids else "")
                       + " ORDER BY seq", ids if pp and ids else []):
        key = (r["doc_type"], r["doc_id"])
        if r["action"] in ("CREATE", "POST", "IMPORT") and key not in P["created"]:
            P["created"][key] = (r["seq"], r["recorded_at"])
            P["log_role"][key] = r["role"]
        if r["doc_type"] == "movement" and r["reason"] == "POD":
            P["pod_recorded"][r["doc_id"]] = r["recorded_at"]
    P["einv"] = {r["irn"]: dict(r) for r in x.execute("SELECT * FROM einvoices")}
    P["einv_by_doc"] = {(r["supplier_gstin"], r["doc_type"], r["doc_no"]): r for r in P["einv"].values()}
    P["ewb"] = {r["ewb_no"]: dict(r) for r in x.execute("SELECT * FROM ewaybills")}
    P["ewb_by_doc"] = defaultdict(list)
    for r in P["ewb"].values():
        P["ewb_by_doc"][(r["supplier_gstin"], r["doc_no"])].append(r)
    P["gstr1"] = {(r["gstin"], r["doc_no"]): dict(r) for r in x.execute("SELECT * FROM gstr1_docs WHERE doc_no IS NOT NULL")}
    P["gstr1_periods"] = {(r[0], r[1]) for r in x.execute("SELECT DISTINCT gstin, period FROM gstr1_docs")}
    P["gstr3b"] = {(r["gstin"], r["period"]): dict(r) for r in x.execute("SELECT * FROM gstr3b")}
    P["bank"] = {r["id"]: dict(r) for r in x.execute("SELECT * FROM bank_txns")}
    # SALES voucher per invoice (first, not reversed) = the posting date
    rev = {j["reverses_no"] for j in P["journals"].values() if j["reverses_no"]}
    P["sales_vouchers"] = defaultdict(list)
    for j in P["journals"].values():
        if j["voucher_type"] == "SALES" and j["source_type"] == "invoice":
            P["sales_vouchers"][j["source_id"]].append(j)
    P["reversed"] = rev
    # purchase to pay (D15): orders, receipts, bills, vendor payments with their bank lines, year-end accruals
    P["pos"] = {r["id"]: dict(r) for r in e.execute("SELECT * FROM purchase_orders")}
    P["grns"] = [dict(r) for r in e.execute("SELECT * FROM goods_receipts ORDER BY received_on, id")]
    P["bills"] = {r["id"]: dict(r) for r in e.execute("SELECT * FROM purchase_bills")}
    P["vendor_payments"] = [dict(r) for r in e.execute("SELECT * FROM settlements WHERE direction = 'PAYMENT'"
                                                       " ORDER BY settled_on, id")]
    P["accruals"] = [dict(r) for r in e.execute(
        "SELECT j.no, j.voucher_date, l.party_id, l.cr_paise FROM journals j JOIN journal_lines l ON l.journal_no = j.no"
        " WHERE j.voucher_type = 'JOURNAL' AND l.account_code = 'CREDITORS' AND l.cr_paise > 0")]
    return P


def _units_state():
    return {u: v["state_code"] for u, v in config.UNITS.items()}

# ---------------------------------------------------------------- D3 cut-off by transfer of control

_B81 = ("substantive_reason", "identified_as_customers", "ready_for_transfer", "cannot_redirect")


def control_date(P, inv):
    """(date | None, basis) per 05 D3: set by the SO's delivery terms, from independent movement evidence."""
    if not inv["goods"]:
        return inv["invoice_date"], "service: invoice date"
    so = P["so"].get(inv["so_id"]) or {}
    terms = so.get("delivery_terms") or "FOR_DISPATCH"
    movs = [P["movements"][m["movement_id"]] for m in P["inv_mov"].get(inv["id"], [])
            if P["movements"][m["movement_id"]]["direction"] == "OUT"]
    if terms == "BILL_AND_HOLD":
        bh = json.loads(so.get("bill_and_hold_json") or "{}") if so.get("bill_and_hold_json") else {}
        if all(bh.get(k) for k in _B81) and bh.get("requested_on"):
            return bh["requested_on"], "bill-and-hold: customer's written request (B81 criteria recorded)"
        terms = "FOR_DISPATCH"
    if terms == "CONSIGNMENT":
        return None, "consignment: no revenue until the consignee's onward sale"
    if terms == "FOR_DESTINATION":
        pods = sorted(m["delivered_on"] for m in movs if m["delivered_on"])
        return (pods[0], "FOR-destination: POD") if pods else (None, "FOR-destination with no POD")
    if not movs:
        return None, "no movement recorded"
    indep = []
    for m in movs:
        if m["lr_date"]:
            indep.append(m["lr_date"])
    for e in P["ewb_by_doc"].get((inv["supplier_gstin"], inv["invoice_no"]), []):
        if e["status"] == "ACT":
            indep.append(e["generated_at"][:10])                    # stored in IST: 01:30 on 1 Apr is April
    moved = min(m["moved_on"] for m in movs)
    cd = max(min(indep), moved) if indep else moved
    return cd, f"{terms.lower().replace('_', '-')}: earliest of LR / e-way bill, not before the movement"


def control_dates(e):
    """{invoice_id: control date or None} (used by D2 to tag RP status on the control date)."""
    with db.borrow("ext", "system") as x:
        P = load_population(e, x)
    return {iid: control_date(P, inv)[0] for iid, inv in P["invoices"].items()}


def d3(P, eng):
    hits, end = [], eng["period_end"]
    start = eng["period_start"]
    for inv in P["invoices"].values():
        if inv["status"] != "ISSUED":
            continue
        sv = [j for j in P["sales_vouchers"].get(inv["id"], []) if j["no"] not in P["reversed"]]
        vdate = sv[0]["voucher_date"] if sv else inv["invoice_date"]
        cd, basis = control_date(P, inv)
        ev = {"invoice_no": inv["invoice_no"], "invoice_date": inv["invoice_date"], "voucher_date": vdate,
              "control_date": cd, "basis": basis,
              "delivery_terms": (P["so"].get(inv["so_id"]) or {}).get("delivery_terms")}
        so = P["so"].get(inv["so_id"]) or {}
        if so.get("delivery_terms") == "BILL_AND_HOLD" and "B81" not in basis:
            hits.append(_hit("D3", "BILL_AND_HOLD_UNSUPPORTED", "invoice", inv["id"], 4, inv["taxable"],
                             f"Invoice {_ref(inv)} is billed under bill-and-hold terms without all four Ind AS 115 B81 "
                             f"criteria recorded, so control is treated as not transferred until the goods move.", ev))
        if cd is None:
            near = abs((_d(vdate) - _d(end)).days) <= 30
            if near and inv["goods"] and not _fresh(inv):
                hits.append(_hit("D3", "CUTOFF_UNRESOLVED", "invoice", inv["id"], 3, inv["taxable"],
                                 f"Invoice {_ref(inv)} sits near the period end but its transfer of control can't be dated "
                                 f"({basis}); request the LR / POD.", ev))
            if so.get("delivery_terms") == "CONSIGNMENT":
                hits.append(_hit("D3", "CONSIGNMENT_JUDGEMENT", "invoice", inv["id"], 3, inv["taxable"],
                                 f"Invoice {_ref(inv)} is on consignment terms: revenue only on the consignee's onward sale.", ev))
        elif start <= vdate <= end < cd:
            hits.append(_hit("D3", "PREMATURE", "invoice", inv["id"], 5, inv["taxable"],
                             f"Invoice {_ref(inv)} is booked on {vdate}, but control passed on {cd} ({basis}). Under "
                             f"Ind AS 115 the sale belongs to the next year: revenue is overstated by {_inr(inv['taxable'])}.", ev))
        elif cd <= end < vdate and cd >= start:
            hits.append(_hit("D3", "DELAYED", "invoice", inv["id"], 4, inv["taxable"],
                             f"Invoice {_ref(inv)} is booked on {vdate}, after the period end, but control passed on {cd}: "
                             f"revenue of {_inr(inv['taxable'])} is understated.", ev))
        if not inv["goods"]:
            continue
        movs = [P["movements"][m["movement_id"]] for m in P["inv_mov"].get(inv["id"], [])]
        out = [m for m in movs if m["direction"] == "OUT"]
        ewbs = [e for e in P["ewb_by_doc"].get((inv["supplier_gstin"], inv["invoice_no"]), []) if e["status"] == "ACT"]
        for m in out:
            dates = [m["moved_on"]] + ([m["lr_date"]] if m["lr_date"] else []) + [e["generated_at"][:10] for e in ewbs]
            spread = (max(map(_d, dates)) - min(map(_d, dates))).days
            if spread > 1:
                hits.append(_hit("D3", "DISPATCH_DATE_CONFLICT", "invoice", inv["id"], 3, inv["taxable"],
                                 f"Invoice {_ref(inv)}: the dispatch record, the LR and the e-way bill disagree on when the "
                                 f"goods left ({spread} days apart; movement {m['id']}).", {**ev, "dates": dates}))
            if m["delivered_on"] and m["delivered_on"] < m["moved_on"]:
                hits.append(_hit("D3", "POD_BEFORE_DISPATCH", "invoice", inv["id"], 4, inv["taxable"],
                                 f"Invoice {_ref(inv)}: the POD on movement {m['id']} is dated before the goods left.", ev))
        if out:
            first = min(m["moved_on"] for m in out)
            gap = (_d(first) - _d(inv["invoice_date"])).days
            if gap < 0 or gap > 1:
                hits.append(_hit("D3", "INVOICE_DATE_VS_REMOVAL", "invoice", inv["id"], 3, inv["taxable"],
                                 f"Invoice {_ref(inv)} is dated {inv['invoice_date']} but the goods left on {first}: a tax "
                                 f"invoice is issued at removal (CGST s.31(1)(a)).", ev))
    return hits

# ---------------------------------------------------------------- D4 movement and settlement

def _digits(s):
    return re.sub(r"\D", "", str(s or "")).lstrip("0")


def _fresh(inv):
    """Raised in the last 7 days: its dispatch and filing aren't due yet (continuous mode, 05 §19.6)."""
    return inv["invoice_date"] > (_d(config.today()) - timedelta(days=7)).isoformat()


def d4(P, eng, rp=None):
    hits, start, end = [], eng["period_start"], eng["period_end"]
    today = config.today()
    by_day = defaultdict(list)
    # dispatched qty per invoice and item, sharing a consolidated movement pro rata
    for inv in P["invoices"].values():
        if inv["status"] != "ISSUED" or not (start <= inv["invoice_date"] <= end):
            continue
        so = P["so"].get(inv["so_id"]) or {}
        export = inv["place_of_supply"] == "96"
        links = P["inv_mov"].get(inv["id"], [])
        movs = [P["movements"][l["movement_id"]] for l in links if P["movements"][l["movement_id"]]["direction"] == "OUT"]
        ev = {"invoice_no": inv["invoice_no"], "taxable_paise": inv["taxable"], "value_paise": inv["value"],
              "movements": [m["id"] for m in movs]}
        if inv["goods"] and not _fresh(inv):
            if not movs and so.get("delivery_terms") != "BILL_AND_HOLD":
                hits.append(_hit("D4", "NO_MOVEMENT", "invoice", inv["id"], 5, inv["taxable"],
                                 f"Invoice {_ref(inv)} ({_inr(inv['taxable'])} taxable) has no dispatch, LR or delivery "
                                 f"behind it: turnover with no physical movement.", ev))
            for m in movs:
                if m["party_id"] != inv["party_id"] or (m["so_id"] and inv["so_id"] and m["so_id"] != inv["so_id"]):
                    hits.append(_hit("D4", "DISPATCH_PARTY_MISMATCH", "invoice", inv["id"], 4, inv["taxable"],
                                     f"Invoice {_ref(inv)} is billed to {inv['party_id']} but its movement {m['id']} went to "
                                     f"{m['party_id']}.", ev))
            if movs:
                need = defaultdict(int)
                for l in inv["lines"]:
                    if not str(l["hsn"]).startswith("99") and not l["item_id"].startswith("CHG"):
                        need[l["item_id"]] += l["qty"]
                got = defaultdict(float)
                for m in movs:
                    for item, q in m["lines"].items():
                        share_tot = sum(sum(ll["qty"] for ll in P["invoices"][o]["lines"] if ll["item_id"] == item)
                                        for o in P["mov_inv"][m["id"]] if o in P["invoices"])
                        mine = need.get(item, 0)
                        got[item] += q * mine / share_tot if share_tot else 0
                short = {k: [v, round(got.get(k, 0))] for k, v in need.items() if got.get(k, 0) + 1e-9 < v}
                if short:
                    hits.append(_hit("D4", "QTY_SHORT", "invoice", inv["id"], 4, inv["taxable"],
                                     f"Invoice {_ref(inv)} bills more than was dispatched for {len(short)} item(s).",
                                     {**ev, "invoiced_vs_dispatched": short}))
            if not export:
                portal = [e for e in P["ewb_by_doc"].get((inv["supplier_gstin"], inv["invoice_no"]), []) if e["status"] == "ACT"]
                typed = [l["ewb_no"] for l in links if l["ewb_no"]]
                valid = portal or [P["ewb"][t] for t in typed if t in P["ewb"] and P["ewb"][t]["status"] == "ACT"]
                if inv["value"] > config.EWB_THRESHOLD_PAISE and not valid:
                    hits.append(_hit("D4", "EWB_REQUIRED_MISSING", "invoice", inv["id"], 4, inv["taxable"],
                                     f"Invoice {_ref(inv)} moved goods worth {_inr(inv['value'])} incl. tax with no valid "
                                     f"e-way bill on the portal (CGST Rule 138).", {**ev, "typed_ewb": typed}))
                for e in valid:
                    for m in movs:
                        if m["vehicle_no"] and e["vehicle_no"] and _digits(m["vehicle_no"]) != _digits(e["vehicle_no"]):
                            hits.append(_hit("D4", "LR_VEHICLE_MISMATCH", "invoice", inv["id"], 3, inv["taxable"],
                                             f"Invoice {_ref(inv)}: the vehicle on movement {m['id']} is not the vehicle on "
                                             f"e-way bill {e['ewb_no']}.", ev))
                    if e["reason"] != "SUPPLY":
                        hits.append(_hit("D4", "EWB_REASON_NOT_SUPPLY", "invoice", inv["id"], 4, inv["taxable"],
                                         f"Invoice {_ref(inv)} is a sale, but e-way bill {e['ewb_no']} moved the goods for "
                                         f"another purpose ({e['reason']}).", ev))
                if inv["value"] <= config.EWB_THRESHOLD_PAISE and not valid:
                    by_day[(inv["party_id"], inv["invoice_date"])].append(inv)
        paid = P["settle"].get(inv["id"], [])
        due = (_d(inv["invoice_date"]) + timedelta(days=90)).isoformat()
        if due < today and not any(s["settled_on"] <= due for s in paid):
            hits.append(_hit("D4", "UNPAID_90D", "invoice", inv["id"], 3, inv["value"],
                             f"Invoice {_ref(inv)} was not settled within 90 days of its date.", ev))
        cust = P["parties"].get(inv["party_id"]) or {}
        for s in paid:
            b = P["bank"].get(s["bank_txn_id"]) or {}
            acct = _digits(b.get("cp_account"))
            if not acct:
                continue
            if rp is not None and acct in rp and rp[acct] != inv["party_id"]:
                hits.append(_hit("D4", "PAYER_IS_RP", "invoice", inv["id"], 5, s["amount_paise"],
                                 f"Invoice {_ref(inv)} was paid from the bank account of {rp[acct]}, a director, relative "
                                 f"or related party of the company: the company may be funding its own sale.",
                                 {**ev, "bank_txn": b.get("id")}))
            elif acct != _digits(cust.get("bank_account")) and not P.setdefault("_fanout", _payer_fanout(P)).get(acct):
                hits.append(_hit("D4", "THIRD_PARTY_PAYER", "invoice", inv["id"], 3, s["amount_paise"],
                                 f"Invoice {_ref(inv)} was paid from an account that is not {inv['party_id']}'s own "
                                 f"(bank line {b.get('id')}).", {**ev, "bank_txn": b.get("id")}))
    for (party, day), invs in by_day.items():
        if len(invs) >= 3 and sum(i["value"] for i in invs) > config.EWB_THRESHOLD_PAISE:
            for inv in invs:
                hits.append(_hit("D4", "SPLIT_BELOW_THRESHOLD", "invoice", inv["id"], 4, inv["taxable"],
                                 f"Invoice {_ref(inv)} is one of {len(invs)} invoices to {party} on {day}, each at or below "
                                 f"Rs 50,000 but together {_inr(sum(i['value'] for i in invs))}, with no e-way bill.",
                                 {"invoices": [i["id"] for i in invs]}))
    # one vehicle on two active e-way bills with overlapping validity from different origins
    by_vehicle = defaultdict(list)
    for e in P["ewb"].values():
        if e["status"] == "ACT" and e["vehicle_no"]:
            by_vehicle[_digits(e["vehicle_no"]) + re.sub(r"\d", "", str(e["vehicle_no"])).upper()].append(e)
    inv_by_doc = {(i["supplier_gstin"], i["invoice_no"]): i for i in P["invoices"].values()}
    for v, es in by_vehicle.items():
        es.sort(key=lambda e: e["generated_at"])
        for i, a in enumerate(es):
            for b in es[i + 1:]:
                if b["generated_at"] >= a["valid_upto"]:
                    break
                if a["from_pincode"] != b["from_pincode"]:
                    for e in (a, b):
                        inv = inv_by_doc.get((e["supplier_gstin"], e["doc_no"]))
                        if inv:
                            hits.append(_hit("D4", "VEHICLE_DOUBLE_BOOKED", "invoice", inv["id"], 4, inv["taxable"],
                                             f"Invoice {_ref(inv)}: its vehicle is on two active e-way bills with overlapping "
                                             f"validity from different origins ({a['ewb_no']}, {b['ewb_no']}).",
                                             {"ewbs": [a["ewb_no"], b["ewb_no"]]}))
    return _dedup(hits)


def _payer_fanout(P):
    """Payer accounts paying for > 3 different customers: TReDS / factoring / collection accounts (no flag)."""
    seen = defaultdict(set)
    for iid, ss in P["settle"].items():
        for s in ss:
            acct = _digits((P["bank"].get(s["bank_txn_id"]) or {}).get("cp_account"))
            if acct:
                seen[acct].add(P["invoices"][iid]["party_id"])
    return {a: True for a, ps in seen.items() if len(ps) > 3}


def _dedup(hits):
    out, seen = [], set()
    for h in hits:
        k = (h["detector"], h["code"], h["object_type"], h["object_id"])
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out

# ---------------------------------------------------------------- D5 concentration (risk points + memo observations)

def _bdays(lo, hi):
    d, out = lo, []
    while d <= hi:
        if d.weekday() != 6:
            out.append(d)
        d += timedelta(days=1)
    return out


def _month_end_windows(start, end, n=10):
    """{(y, m): (first day of the last n business days, month end)} for every month of the period."""
    out, d = {}, _d(start)
    while d <= _d(end):
        nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = min(nxt - timedelta(days=1), _d(end))
        out[(d.year, d.month)] = (_bdays(d, last)[-n], last)
        d = nxt
    return out


def _mad(xs):
    m = statistics.median(xs)
    return m, statistics.median([abs(x - m) for x in xs])


def d5(P, eng):
    hits, start, end = [], eng["period_start"], eng["period_end"]
    wins = _month_end_windows(start, end)
    em = (_d(end).year, _d(end).month)
    fy = [i for i in P["invoices"].values() if i["status"] == "ISSUED" and start <= i["invoice_date"] <= end]
    in_win = lambda i, ym: wins[ym][0] <= _d(i["invoice_date"]) <= wins[ym][1]
    ym_of = lambda i: (int(i["invoice_date"][:4]), int(i["invoice_date"][5:7]))
    month_tot, win_tot = defaultdict(int), defaultdict(int)
    for i in fy:
        ym = ym_of(i)
        month_tot[ym] += i["taxable"]
        if in_win(i, ym):
            win_tot[ym] += i["taxable"]
    shares = {ym: win_tot[ym] / month_tot[ym] for ym in month_tot if month_tot[ym]}
    others = [s for ym, s in shares.items() if ym != em]
    if em in shares and len(others) >= 6:
        med, mad = _mad(others)
        if shares[em] > med + 3 * max(mad, 0.02):
            hits.append(_hit("D5", "END_WINDOW_SHARE", "company", "SELF", 2,
                             int(win_tot[em] - med * month_tot[em]),
                             f"{shares[em]:.0%} of the period-end month's sales fall in its last 10 business days, against "
                             f"a median of {med:.0%} at the other month-ends (risk indicator; corroborate with cut-off, "
                             f"movement and post-period credit notes).",
                             {"share": round(shares[em], 4), "median_other": round(med, 4), "mad": round(mad, 4)}))
    # per customer and per item: the period-end window against the run-rate (median monthly value)
    for key, label, kind in (("party_id", "customer", "party"), (None, "item", "item")):
        monthly = defaultdict(lambda: defaultdict(int))
        windows = defaultdict(lambda: defaultdict(int))        # end-window value per month, per customer / item
        for i in fy:
            ym = ym_of(i)
            for k, v in ([(i[key], i["taxable"])] if key else
                         [(l["item_id"], l["taxable_paise"]) for l in i["lines"] if not l["item_id"].startswith("CHG")]):
                monthly[k][ym] += v
                if in_win(i, ym):
                    windows[k][ym] += v
        for k, wm in windows.items():
            w = wm.get(em, 0)
            other_w = [wm.get(ym, 0) for ym in wins if ym != em]
            if not w or sum(1 for v in other_w if v) < 6:    # only regular month-end buyers have a run-rate to beat
                continue
            rate = statistics.median([monthly[k].get(ym, 0) for ym in wins if ym != em])
            med, mad = _mad(other_w)
            if rate and w >= 3 * rate and w >= med + 4 * max(mad, med / 4) and w >= 5_00_000_00:
                hits.append(_hit("D5", "END_WINDOW_SHARE", kind, k, 2, w - rate,
                                 f"{label.capitalize()} {k} billed {_inr(w)} in the last 10 business days of the period, "
                                 f"{w / rate:.1f}x its median monthly run-rate of {_inr(int(rate))}.",
                                 {"window_paise": w, "run_rate_paise": int(rate)}))
    # discounts: the period-end window against the customer's usual rate
    by_c = defaultdict(list)
    for i in fy:
        if i["gross"]:
            by_c[i["party_id"]].append(i)
    usual = {}
    for c, invs in by_c.items():
        pct = [i["discount"] / i["gross"] for i in invs]
        usual[c] = statistics.median(pct)
        win = [i for i in invs if in_win(i, em) and ym_of(i) == em]
        if len(pct) < 3 or not win:
            continue
        g = sum(i["gross"] for i in win)
        wp = sum(i["discount"] for i in win) / g
        med, mad = _mad(pct)
        if g >= 1_00_000_00 and wp - med >= 0.02 and (wp > 2 * med or wp > med + 3 * mad):
            hits.append(_hit("D5", "DISCOUNT_SPIKE", "party", c, 2, sum(i["discount"] for i in win) - int(med * g),
                             f"Customer {c} received {wp:.1%} discount in the last 10 business days against its usual "
                             f"{med:.1%} (s.15(3) post-supply discounts; SA 240 rebates).",
                             {"window_discount": round(wp, 4), "usual": round(med, 4)}))
    lo30 = (_d(end) - timedelta(days=30)).isoformat()
    used = defaultdict(list)
    for i in fy:
        for l in i["lines"]:
            if l["scheme_id"]:
                used[l["scheme_id"]].append(i["id"])
    for s in P["schemes"].values():
        if s["announced_on"] >= lo30 and s["announced_on"] <= end or (s["valid_from"] >= lo30 and s["valid_from"] <= end):
            hits.append(_hit("D5", "SCHEME_WINDOW", "scheme", s["id"], 2, 0,
                             f"Scheme {s['id']} was announced or starts in the last 30 days of the period "
                             f"(announced {s['announced_on']}, valid {s['valid_from']} to {s['valid_to']}).",
                             {"invoices": used.get(s["id"], [])[:50]}))
        if not s["approved_by"] and used.get(s["id"]):
            hits.append(_hit("D5", "SCHEME_WINDOW", "scheme", s["id"], 3, 0,
                             f"Scheme {s['id']} has no recorded approval but discounts were given under it on "
                             f"{len(used[s['id']])} invoice(s).", {"invoices": used[s["id"]][:50], "unapproved": True}))
    for i in fy:
        if i["invoice_date"] < lo30 or not i["gross"]:
            continue
        if any(l["scheme_id"] for l in i["lines"]):
            continue
        p = i["discount"] / i["gross"]
        if p - usual.get(i["party_id"], 0) >= 0.05:
            hits.append(_hit("D5", "SCHEME_WINDOW", "invoice", i["id"], 2, i["discount"],
                             f"Invoice {_ref(i)} carries a {p:.1%} discount with no scheme, above the customer's usual "
                             f"{usual.get(i['party_id'], 0):.1%}.", {"discount_paise": i["discount"]}))
    first = {}
    for i in sorted(P["invoices"].values(), key=lambda i: i["invoice_date"]):
        first.setdefault(i["party_id"], i)
    for c, i in first.items():
        if wins[em][0] <= _d(i["invoice_date"]) <= wins[em][1] and i["status"] == "ISSUED":
            hits.append(_hit("D5", "NEW_CUSTOMER_AT_YEAR_END", "party", c, 2, i["taxable"],
                             f"Customer {c}'s first-ever invoice ({_ref(i)}) falls in the last 10 business days of the "
                             f"period.", {"invoice_id": i["id"]}))
    amounts = [i["value"] for i in fy if i["value"] > 0]
    if len(amounts) >= 1000:                                  # first-digit tests need ~1,000+ values (Nigrini)
        import math
        obs = [0] * 10
        for a in amounts:
            obs[int(str(a)[0])] += 1
        mad = sum(abs(obs[dg] / len(amounts) - math.log10(1 + 1 / dg)) for dg in range(1, 10)) / 9
        if mad > 0.015:
            hits.append(_hit("D5", "BENFORD_FIRST_DIGIT", "company", "SELF", 1, 0,
                             f"First digits of invoice values deviate from Benford's law (MAD {mad:.4f} > 0.015, "
                             f"nonconformity; SA 520 analytical procedure; information only).", {"mad": round(mad, 5)}))
    return hits

# ---------------------------------------------------------------- D6 statutory documents and tax filings

def d6(P, eng):
    from app import portal
    hits, start, end = [], eng["period_start"], eng["period_end"]
    state = _units_state()
    books = set()
    for inv in P["invoices"].values():
        books.add((inv["supplier_gstin"], inv["invoice_no"]))
        if inv["status"] != "ISSUED" or not (start <= inv["invoice_date"] <= end):
            continue
        ev = {"invoice_no": inv["invoice_no"], "irn": inv["irn"]}
        if inv["buyer_gstin"] and config.AATO_EINVOICE and inv["place_of_supply"] != "96":
            want = portal.irn_of(inv["supplier_gstin"], portal.fy_label(inv["invoice_date"]), "INV", inv["invoice_no"])
            row = P["einv"].get(inv["irn"]) if inv["irn"] else None
            if not inv["irn"]:
                hits.append(_hit("D6", "IRN_MISSING", "invoice", inv["id"], 4, inv["tax"],
                                 f"B2B invoice {_ref(inv)} has no IRN; with e-invoicing applicable it is not a valid tax "
                                 f"invoice (Rule 48(5)).", ev))
            elif inv["irn"] != want:
                hits.append(_hit("D6", "IRN_MISMATCH", "invoice", inv["id"], 5, inv["taxable"],
                                 f"Invoice {_ref(inv)} records an IRN that is not the one this invoice would get; it "
                                 f"belongs to another document or was never issued for this one.",
                                 {**ev, "irn_belongs_to": (row or {}).get("doc_no")}))
            elif row is None:
                hits.append(_hit("D6", "IRN_NOT_ON_PORTAL", "invoice", inv["id"], 4, inv["taxable"],
                                 f"Invoice {_ref(inv)}'s IRN is not registered on the IRP.", ev))
            else:
                if row["status"] == "CNL":
                    hits.append(_hit("D6", "IRN_CANCELLED", "invoice", inv["id"], 4, inv["taxable"],
                                     f"Invoice {_ref(inv)} is active in the books but its IRN is cancelled on the IRP.", ev))
                if not portal.verify_signature(row):
                    hits.append(_hit("D6", "IRN_SIGNATURE_BAD", "invoice", inv["id"], 5, inv["taxable"],
                                     f"Invoice {_ref(inv)}: the e-invoice signature does not verify (record altered).", ev))
        for l in P["inv_mov"].get(inv["id"], []):
            t = l["ewb_no"]
            if not t:
                continue
            e = P["ewb"].get(t)
            if e is None:
                hits.append(_hit("D6", "EWB_NOT_FOUND", "invoice", inv["id"], 5, inv["taxable"],
                                 f"Invoice {_ref(inv)}'s dispatch quotes an e-way bill number that does not exist on the "
                                 f"portal.", {**ev, "typed_ewb": t}))
                continue
            if e["status"] == "CNL":
                hits.append(_hit("D6", "EWB_CANCELLED", "invoice", inv["id"], 4, inv["taxable"],
                                 f"Invoice {_ref(inv)} relies on e-way bill {t}, which is cancelled on the portal.", ev))
            if (e["doc_no"], e["doc_date"], e["supplier_gstin"]) != (inv["invoice_no"], inv["invoice_date"], inv["supplier_gstin"]) \
                    or (e["to_gstin"] or "") != (inv["buyer_gstin"] or ""):
                hits.append(_hit("D6", "EWB_DOC_MISMATCH", "invoice", inv["id"], 4, inv["taxable"],
                                 f"Invoice {_ref(inv)}: e-way bill {t} was generated for a different document, date or "
                                 f"party (doc {e['doc_no'] if _SAFE.match(e['doc_no'] or '') else '?'}, {e['doc_date']}).",
                                 {**ev, "ewb": {k: e[k] for k in ("doc_no", "doc_date", "to_gstin")}}))
        for e in P["ewb_by_doc"].get((inv["supplier_gstin"], inv["invoice_no"]), []):
            if e["status"] == "ACT" and abs(e["value_paise"] - inv["value"]) > 100:
                hits.append(_hit("D6", "EWB_VALUE_MISMATCH", "invoice", inv["id"], 4, abs(e["value_paise"] - inv["value"]),
                                 f"Invoice {_ref(inv)} is worth {_inr(inv['value'])} incl. tax, but its e-way bill {e['ewb_no']} "
                                 f"declares {_inr(e['value_paise'])}.", ev))
        g = P["gstr1"].get((inv["supplier_gstin"], inv["invoice_no"]))
        if g is None:
            y, m = int(inv["invoice_date"][:4]), int(inv["invoice_date"][5:7])
            filed = (inv["supplier_gstin"], f"{y}{m:02d}") in P["gstr1_periods"]
            due = date(y + (m == 12), m % 12 + 1, 11).isoformat()            # GSTR-1 is due on the 11th
            if filed or config.today() > due:
                hits.append(_hit("D6", "NOT_IN_GSTR1", "invoice", inv["id"], 4, inv["taxable"],
                                 f"Invoice {_ref(inv)} is in the books but not in GSTR-1"
                                 f"{'' if filed else ' (that month was never filed)'}.", ev))
        else:
            dt = abs(g["taxable_paise"] - inv["taxable"])
            dx = abs(g["igst_paise"] + g["cgst_paise"] + g["sgst_paise"] - inv["tax"])
            if dt > 100 or dx > 100:
                hits.append(_hit("D6", "GSTR1_VALUE_DIFF", "invoice", inv["id"], 4, dt + dx,
                                 f"Invoice {_ref(inv)}: GSTR-1 reports {_inr(g['taxable_paise'])} taxable against "
                                 f"{_inr(inv['taxable'])} in the books.", ev))
        inter = inv["place_of_supply"] != state.get(inv["series"])
        if (inter and (inv["cgst"] or inv["sgst"])) or (not inter and inv["igst"]) or inv["cgst"] != inv["sgst"]:
            hits.append(_hit("D6", "TAX_TYPE_WRONG", "invoice", inv["id"], 4, inv["tax"],
                             f"Invoice {_ref(inv)} is {'inter' if inter else 'intra'}-state but charges "
                             f"{'CGST/SGST' if inter else 'IGST'} (IGST Act s.10).", ev))
        for l in inv["lines"]:
            expect = money.tax_paise(l["taxable_paise"], l["gst_rate_bp"])
            got = l["igst_paise"] + l["cgst_paise"] + l["sgst_paise"]
            if abs(got - expect) > 100 or l["gst_rate_bp"] != l["item_rate"]:
                hits.append(_hit("D6", "TAX_RATE_WRONG", "invoice", inv["id"], 3, abs(money.tax_paise(
                    l["taxable_paise"], l["item_rate"]) - got),
                                 f"Invoice {_ref(inv)} line {l['line_no']}: tax is charged at {l['gst_rate_bp'] / 100:g}% "
                                 f"but item {l['item_id']} is rated {l['item_rate'] / 100:g}%.", ev))
                break
    cn_nos = {(config.UNITS.get(c["cn_no"].split("/")[1], {}).get("gstin") if c["cn_no"].count("/") >= 2 else None,
               c["cn_no"]) for c in P["cns"].values()}
    for (gstin, no), g in P["gstr1"].items():
        if g["section"] != "CDNR" and (gstin, no) not in books or g["section"] == "CDNR" and (gstin, no) not in cn_nos:
            hits.append(_hit("D6", "GSTR1_NOT_IN_BOOKS", "gstr1", f"{gstin}|{no}", 4, g["taxable_paise"],
                             f"GSTR-1 for {g['period']} reports a document that is not in the books.",
                             {"doc_no": no, "period": g["period"]}))
    # monthly: GSTR-3B 3.1(a) vs GSTR-1
    g1 = defaultdict(int)
    for (gstin, _no), g in P["gstr1"].items():
        g1[(gstin, g["period"])] += -g["taxable_paise"] if g["section"] == "CDNR" else g["taxable_paise"]
    for k, r in P["gstr3b"].items():
        if abs(r["outward_taxable_paise"] - g1.get(k, 0)) > 100:
            hits.append(_hit("D6", "GSTR3B_DIFF", "gstr3b", f"{k[0]}|{k[1]}", 4, abs(r["outward_taxable_paise"] - g1.get(k, 0)),
                             f"GSTR-3B for {k[1]} reports {_inr(r['outward_taxable_paise'])} outward taxable supplies "
                             f"against {_inr(g1.get(k, 0))} in GSTR-1.", {"gstin": k[0], "period": k[1]}))
    return hits

# ---------------------------------------------------------------- D7 revenue entries not from a sale

_GENERIC = re.compile(r"^\s*(adj(ustment)?|misc(ellaneous)?|entry|jv|correction|provision|accrual|sales?|revenue|"
                      r"rectification|as per mgmt|transfer|being.{0,10})\.?\s*$", re.I)


def d7(P, eng, confirmed_ajes=()):
    hits, start, end = [], eng["period_start"], eng["period_end"]
    revenue = P["revenue_accounts"]
    active = lambda st, sid: (st == "invoice" and (P["invoices"].get(sid) or {}).get("status") == "ISSUED") or \
                             (st == "credit_note" and (P["cns"].get(sid) or {}).get("status") == "ISSUED")
    for j in P["journals"].values():
        rev_lines = [l for l in j["lines"] if l["account_code"] in revenue]
        if not rev_lines:
            continue
        cr = sum(l["cr_paise"] for l in rev_lines) - sum(l["dr_paise"] for l in rev_lines)
        ev = {"journal_no": j["no"], "voucher_type": j["voucher_type"], "voucher_date": j["voucher_date"],
              "posted_by": j["posted_by"], "source": [j["source_type"], j["source_id"]], "aje_ref": j["aje_ref"]}
        in_fy = start <= j["voucher_date"] <= end
        if j["voucher_type"] not in ("SALES", "CREDIT_NOTE", "REVERSAL"):
            if j["aje_ref"] and j["aje_ref"] in confirmed_ajes:
                hits.append(_hit("D7", "ACCEPTED_AJE", "journal", j["no"], 1, abs(cr),
                                 f"Journal {j['no']} posts the confirmed audit adjustment {j['aje_ref']}.", ev))
            elif in_fy and cr:
                hits.append(_hit("D7", "REVENUE_WITHOUT_SALE", "journal", j["no"], 5, abs(cr),
                                 f"Journal {j['no']} ({j['voucher_type']}, {j['voucher_date']}) moves {_inr(abs(cr))} of "
                                 f"revenue with no invoice or credit note behind it.", ev))
        elif j["voucher_type"] in ("SALES", "CREDIT_NOTE") and not active(j["source_type"], j["source_id"]) \
                and j["no"] not in P["reversed"]:
            hits.append(_hit("D7", "REVENUE_WITHOUT_SALE", "journal", j["no"], 5, abs(cr),
                             f"Journal {j['no']} is a {j['voucher_type']} voucher whose source document is missing or "
                             f"cancelled and it was never reversed.", ev))
        if cr > 0 and j["voucher_type"] != "REVERSAL":
            contra = sorted({l["account_code"] for l in j["lines"] if l["dr_paise"]} - {"DEBTORS", "BANK", "ROUND_OFF"})
            if contra:
                hits.append(_hit("D7", "UNUSUAL_CONTRA", "journal", j["no"], 4, cr,
                                 f"Journal {j['no']} credits revenue against {', '.join(contra)} instead of a customer or "
                                 f"the bank.", ev))
        created = P["created"].get(("journal", str(j["no"])))
        if created and j["voucher_date"] <= end and created[1][:10] > end and j["voucher_type"] != "REVERSAL":
            hits.append(_hit("D7", "POST_CLOSING", "journal", j["no"], 4, abs(cr),
                             f"Journal {j['no']} is dated {j['voucher_date']} but was entered on {created[1][:10]}, after "
                             f"the period closed (SA 240 para 32(a)).", ev))
        if j["voucher_type"] == "JOURNAL":
            if cr and abs(cr) % 1_00_000_00 == 0:
                hits.append(_hit("D7", "ROUND_AMOUNT", "journal", j["no"], 2, abs(cr),
                                 f"Manual journal {j['no']} moves a round {_inr(abs(cr))} through revenue.", ev))
            if _GENERIC.match(j["narration"] or "") or len((j["narration"] or "").strip()) < 8:
                hits.append(_hit("D7", "GENERIC_NARRATION", "journal", j["no"], 2, abs(cr),
                                 f"Manual journal {j['no']} touching revenue has an empty or generic narration.", ev))
            role = P["log_role"].get(("journal", str(j["no"])))
            if role and role not in ("accounts", "client_admin"):
                hits.append(_hit("D7", "UNUSUAL_POSTER", "journal", j["no"], 3, abs(cr),
                                 f"Manual journal {j['no']} touching revenue was posted by role {role}.", ev))
    # per invoice: revenue posted vs taxable value, and duplicate SALES vouchers
    for inv in P["invoices"].values():
        sv = [j for j in P["sales_vouchers"].get(inv["id"], []) if j["no"] not in P["reversed"]]
        if inv["status"] != "ISSUED" or not (start <= inv["invoice_date"] <= end):
            continue
        if len(sv) > 1:
            hits.append(_hit("D7", "DUPLICATE_POSTING", "invoice", inv["id"], 5, inv["taxable"] * (len(sv) - 1),
                             f"Invoice {_ref(inv)} is posted in {len(sv)} sales vouchers.", {"journals": [j["no"] for j in sv]}))
        posted = sum(l["cr_paise"] - l["dr_paise"] for j in sv for l in j["lines"] if l["account_code"] in revenue)
        if sv and posted != inv["taxable"]:
            hits.append(_hit("D7", "REVENUE_POSTING_DIFF", "invoice", inv["id"], 5, posted - inv["taxable"],
                             f"Invoice {_ref(inv)} has taxable value {_inr(inv['taxable'])} but its vouchers post "
                             f"{_inr(posted)} to revenue.", {"journals": [j["no"] for j in sv]}))
    return hits

# ---------------------------------------------------------------- D9 credit notes

def d9(P, eng, rp=None):
    hits, start, end = [], eng["period_start"], eng["period_end"]
    today = config.today()
    credited = defaultdict(int)
    for c in P["cns"].values():
        if c["status"] != "ISSUED":
            continue
        for l in c["lines"]:
            if l["invoice_id"]:
                credited[l["invoice_id"]] += l["taxable_paise"]
    pre = defaultdict(list)
    for i in P["invoices"].values():
        if i["status"] == "ISSUED" and start <= i["invoice_date"] <= end:
            pre[i["party_id"]].append(i)
    for c in P["cns"].values():
        if c["status"] != "ISSUED":
            continue
        t = sum(l["taxable_paise"] for l in c["lines"])
        ev = {"cn_no": c["cn_no"], "cn_date": c["cn_date"], "reason": c["reason"], "taxable_paise": t}
        ref = f"credit note {_ref(c)}"
        linked = [P["invoices"][l["invoice_id"]] for l in c["lines"] if l["invoice_id"] in P["invoices"]]
        if c["cn_date"] > end:
            match = [i for i in pre.get(c["party_id"], []) if abs(i["taxable"] - t) <= t * 0.01 + 100]
            pre_linked = [i for i in linked if i["invoice_date"] <= end]
            targets = pre_linked or match
            if targets:
                inv = targets[0]
                movs = P["inv_mov"].get(inv["id"])
                unpaid = not P["settle"].get(inv["id"])
                is_rp = bool(rp and rp.get(inv["party_id"]))
                ret = bool(c["return_movement_id"])
                risk = "HIGH" if (not movs or unpaid or is_rp or (c["reason"] == "SALES_RETURN" and not ret)) else \
                    ("SUPPORTED" if ret else "NEEDS_EVIDENCE")
                hits.append(_hit("D9", "POST_PERIOD_REVERSAL", "credit_note", c["id"], 5, t,
                                 f"{ref.capitalize()} dated {c['cn_date']} reverses {_ref(inv)} of {inv['invoice_date']}, a "
                                 f"sale inside the period: {_inr(t)} needs a period-end refund liability or reversal "
                                 f"(Ind AS 115 paras 50-59; Ind AS 10 adjusting event). Stuffing risk: {risk}.",
                                 {**ev, "invoice": inv["id"], "linked": [i["id"] for i in linked],
                                  "amount_match": [i["id"] for i in match], "stuffing_risk": risk}))
            fy_inv = [i for i in linked if start <= i["invoice_date"] <= end]
            limit = f"{int(end[:4])}-11-30"
            if fy_inv and c["cn_date"] > limit:
                hits.append(_hit("D9", "CN_AFTER_SEC34_LIMIT", "credit_note", c["id"], 4, sum(
                    l["igst_paise"] + l["cgst_paise"] + l["sgst_paise"] for l in c["lines"]),
                                 f"{ref.capitalize()} credits FY supplies after 30 November of the next year: the GST "
                                 f"reduction is not allowed (CGST s.34(2)).", ev))
        if c["reason"] == "SALES_RETURN":
            m = P["movements"].get(c["return_movement_id"]) if c["return_movement_id"] else None
            ret_qty = sum(m["lines"].values()) if m else 0
            inv_qty = sum(l["qty"] for i in linked for l in i["lines"] if not l["item_id"].startswith("CHG"))
            cn_qty = sum(l["qty"] or 0 for l in c["lines"])
            if m is None or m["direction"] != "IN" or m["moved_on"] > c["cn_date"] or (inv_qty and cn_qty > inv_qty) \
                    or (cn_qty and ret_qty < cn_qty):
                hits.append(_hit("D9", "RETURN_WITHOUT_MOVEMENT", "credit_note", c["id"], 4, t,
                                 f"{ref.capitalize()} is a sales return but no matching inward movement of the goods is "
                                 f"recorded before it.", ev))
        if c["reason"] == "SCHEME_REBATE":
            s = P["schemes"].get(c["scheme_id"]) if c["scheme_id"] else None
            if s is None:
                hits.append(_hit("D9", "REBATE_WITHOUT_SCHEME", "credit_note", c["id"], 3, t,
                                 f"{ref.capitalize()} is a rebate with no scheme behind it.", ev))
            elif any(s["announced_on"] > i["invoice_date"] for i in linked):
                hits.append(_hit("D9", "SCHEME_AFTER_SALE", "credit_note", c["id"], 4, t,
                                 f"{ref.capitalize()} pays rebate under scheme {s['id']}, announced after the credited sale.", ev))
        if any(l["invoice_id"] is None for l in c["lines"]):
            hits.append(_hit("D9", "UNLINKED_CN", "credit_note", c["id"], 3, t,
                             f"{ref.capitalize()} does not say which invoice it credits.", ev))
        for l in c["lines"]:
            inv = P["invoices"].get(l["invoice_id"])
            rate = (inv["lines"][0]["gst_rate_bp"] if inv and inv["lines"] else 1800)
            if abs(money.tax_paise(l["taxable_paise"], rate) - (l["igst_paise"] + l["cgst_paise"] + l["sgst_paise"])) > 100:
                hits.append(_hit("D9", "CN_TAX_MISMATCH", "credit_note", c["id"], 3, 0,
                                 f"{ref.capitalize()} line {l['line_no']}: tax does not match the credited invoice's rate.", ev))
                break
        party = P["parties"].get(c["party_id"]) or {}
        unit = c["cn_no"].split("/")[1] if c["cn_no"].count("/") >= 2 else None
        gstin = config.UNITS.get(unit, {}).get("gstin")
        filed = gstin and (gstin, c["cn_date"][:4] + c["cn_date"][5:7]) in P["gstr1_periods"]
        if party.get("gstin") and filed and (gstin, c["cn_no"]) not in P["gstr1"]:
            hits.append(_hit("D9", "CN_NOT_IN_GSTR1", "credit_note", c["id"], 3, t,
                             f"{ref.capitalize()} to a registered customer is missing from GSTR-1 (CDNR).", ev))
    for iid, amt in credited.items():
        inv = P["invoices"].get(iid)
        if inv and amt > inv["taxable"]:
            hits.append(_hit("D9", "CN_EXCEEDS_INVOICE", "invoice", iid, 4, amt - inv["taxable"],
                             f"Credit notes against invoice {_ref(inv)} total {_inr(amt)}, more than its taxable value "
                             f"{_inr(inv['taxable'])}.", {"credited_paise": amt}))
    for inv in P["invoices"].values():
        if inv["status"] != "CANCELLED" or not (start <= inv["invoice_date"] <= end):
            continue
        row = P["einv"].get(inv["irn"]) if inv["irn"] else None
        late_irn = row is not None and row["status"] == "ACT"
        if (inv["cancelled_on"] and inv["cancelled_on"] > end) or late_irn:
            hits.append(_hit("D9", "LATE_CANCELLATION", "invoice", inv["id"], 4, inv["taxable"],
                             f"Invoice {_ref(inv)} of {inv['invoice_date']} was cancelled "
                             f"{'after the period end' if inv['cancelled_on'] and inv['cancelled_on'] > end else ''}"
                             f"{' and ' if late_irn and inv['cancelled_on'] and inv['cancelled_on'] > end else ''}"
                             f"{'more than 24 h after its IRN (the IRP still shows it active)' if late_irn else ''}.",
                             {"cancelled_on": inv["cancelled_on"]}))
    return hits

# ---------------------------------------------------------------- D13 backdating and sequence

def d13(P, eng):
    hits, start, end = [], eng["period_start"], eng["period_end"]
    docs = [("invoice", i["id"], i["invoice_date"], i) for i in P["invoices"].values()] + \
           [("credit_note", c["id"], c["cn_date"], c) for c in P["cns"].values()]
    after = [P["created"].get((t, i), (None,))[0] for t, i, d, _ in docs if d > end]
    first_after = min((s for s in after if s), default=P.get("first_after_seq"))
    if P.get("first_after_seq"):
        first_after = min(first_after, P["first_after_seq"])
    if first_after:
        for t, i, d, row in docs:
            seq = P["created"].get((t, i), (None,))[0]
            if start <= d <= end and seq and seq > first_after:
                when = P["created"][(t, i)][1][:10]
                hits.append(_hit("D13", "BACKDATED_ENTRY", t, i, 5, row.get("taxable") or 0,
                                 f"{'Invoice' if t == 'invoice' else 'Credit note'} {_ref(row)} is dated {d}, inside the "
                                 f"period, but was entered on {when}, after documents of the next year had been entered.",
                                 {"date": d, "entered_at": P["created"][(t, i)][1], "erp_seq": seq}))
    by_series = defaultdict(list)
    for i in ([] if P.get("narrow") else P["invoices"].values()):      # a series test needs the whole series
        m = re.fullmatch(r"([A-Z0-9]+)/(\d+)/(\d{2})", i["invoice_no"] or "")
        if m and start <= i["invoice_date"] <= end:
            by_series[(m[1], m[3])].append((int(m[2]), i))
    for (series, yy), rows in by_series.items():
        rows.sort(key=lambda r: r[0])
        for (n0, a), (n1, b) in zip(rows, rows[1:]):
            if b["invoice_date"] < a["invoice_date"]:
                hits.append(_hit("D13", "SEQUENCE_BREAK", "invoice", b["id"], 3, b["taxable"],
                                 f"Invoice {_ref(b)} is numbered after {_ref(a)} but dated earlier ({b['invoice_date']} vs "
                                 f"{a['invoice_date']}; Rule 46(b) consecutive series).", {"series": series}))
            elif n1 - n0 > 1:
                hits.append(_hit("D13", "SEQUENCE_BREAK", "invoice", b["id"], 3, 0,
                                 f"Series {series}/{yy}: {n1 - n0 - 1} number(s) missing before invoice {_ref(b)} "
                                 f"(Rule 46(b)).", {"series": series, "gap": [n0, n1]}))
    for inv in P["invoices"].values():
        row = P["einv"].get(inv["irn"]) if inv["irn"] else None
        if row and config.AATO_30_DAY_IRN and (_d(row["ack_at"]) - _d(inv["invoice_date"])).days > 30:
            hits.append(_hit("D13", "IRN_LATE", "invoice", inv["id"], 4, inv["taxable"],
                             f"Invoice {_ref(inv)}'s IRN was obtained {(_d(row['ack_at']) - _d(inv['invoice_date'])).days} "
                             f"days after the invoice date; the IRP rejects reporting after 30 days, so the IRN or the "
                             f"date is false.", {"ack_at": row["ack_at"]}))
    lo, hi = (_d(end) - timedelta(days=15)).isoformat(), (_d(end) + timedelta(days=15)).isoformat()
    for mid, rec in P["pod_recorded"].items():
        m = P["movements"].get(mid)
        if m and m["delivered_on"] and lo <= m["delivered_on"] <= hi and (_d(rec) - _d(m["delivered_on"])).days > 3:
            for iid in P["mov_inv"].get(mid, []):
                inv = P["invoices"].get(iid)
                if inv:
                    hits.append(_hit("D13", "POD_RECORDED_LATE", "invoice", iid, 3, inv["taxable"],
                                     f"Invoice {_ref(inv)}: the POD dated {m['delivered_on']} was only recorded on "
                                     f"{rec[:10]}, near the period end.", {"movement": mid}))
    return hits

# ---------------------------------------------------------------- D14 instruction text in client data

INSTRUCTION = re.compile(r"ignore (all|previous)|you are|system prompt|mark .* verified|auditor (ai|agent)|"
                         r"sign[- ]?off|do not (report|flag)", re.I)


def d14(P, eng):
    hits = []
    for p in P["parties"].values():
        if INSTRUCTION.search(f"{p['name']} {p['address']}"):
            hits.append(_hit("D14", "EVIDENCE_CONTAINS_INSTRUCTIONS", "party", p["id"], 3, 0,
                             f"Party {p['id']}'s master text contains instruction-like wording; it is treated as data only "
                             f"(OWASP LLM01).", {"field": "name/address"}))
    for c in P["cns"].values():
        if INSTRUCTION.search(c["reason_text"] or "") or str(c["reason_text"] or "").lstrip().startswith(("=", "+", "@")):
            hits.append(_hit("D14", "EVIDENCE_CONTAINS_INSTRUCTIONS", "credit_note", c["id"], 3, 0,
                             f"Credit note {_ref(c)}'s reason text contains instruction or formula-like content; treated "
                             f"as data only.", {"field": "reason_text"}))
    for j in P["journals"].values():
        if INSTRUCTION.search(j["narration"] or ""):
            hits.append(_hit("D14", "EVIDENCE_CONTAINS_INSTRUCTIONS", "journal", j["no"], 3, 0,
                             f"Journal {j['no']}'s narration contains instruction-like wording; treated as data only.",
                             {"field": "narration"}))
    for s in P["so"].values():
        if INSTRUCTION.search(f"{s['contact_name'] or ''} {s['customer_po_no'] or ''}"):
            hits.append(_hit("D14", "EVIDENCE_CONTAINS_INSTRUCTIONS", "sales_order", s["id"], 3, 0,
                             f"Sales order {s['id']} contains instruction-like contact text; treated as data only.", {}))
    return hits

# ---------------------------------------------------------------- run

# ---------------------------------------------------------------- D15 purchase to pay (vault/13 MT-2)

def d15(P, eng):
    """100% of purchase orders, goods receipts, bills and vendor payments. Explain first: received quantity counts
    every GRN to date (later deliveries included) net of returns; an advance under 30 days old is still pending; a GRN
    is accrued when a year-end journal credits the vendor. Impacts are at the PO rate (before tax and freight)."""
    hits, end, today = [], eng["period_end"], config.today()
    grn_by_po = defaultdict(list)
    for g in P["grns"]:
        grn_by_po[g["po_id"]].append(g)
    bills_by_po = defaultdict(list)
    for b in P["bills"].values():
        if b["po_id"]:
            bills_by_po[b["po_id"]].append(b)
    pay_by_bill, adv_by_po = defaultdict(list), defaultdict(list)
    for s in P["vendor_payments"]:
        if s["doc_type"] == "PURCHASE" and s["doc_id"]:
            pay_by_bill[s["doc_id"]].append(s)
        elif s["doc_type"] == "ADVANCE":
            adv_by_po[s["doc_id"]].append(s)
    received = lambda po_id, upto=None: sum((g["qty"] if g["kind"] == "RECEIPT" else -g["qty"]) for g in grn_by_po[po_id]
                                             if upto is None or g["received_on"] <= upto)
    for po in P["pos"].values():
        rate = po["rate_paise"]
        bills = bills_by_po[po["id"]]
        billed_qty = sum(b["qty"] or 0 for b in bills)
        paid = sum(s["amount_paise"] for b in bills for s in pay_by_bill[b["id"]]) + \
            sum(s["amount_paise"] for s in adv_by_po[po["id"]])
        # quantity paid for: the paid share of each bill's quantity (a bill paid at an inflated price is a PRICE_VARIANCE,
        # not a short receipt), plus advances against the PO at the PO rate
        paid_qty = 0
        for b in bills:
            total = b["taxable_paise"] + b["tax_paise"]
            settled = sum(s["amount_paise"] for s in pay_by_bill[b["id"]])
            paid_qty += min(b["qty"] or 0, (b["qty"] or 0) * settled // total) if total else 0
        if rate:
            paid_qty += sum(s["amount_paise"] for s in adv_by_po[po["id"]]) // rate
        got = received(po["id"])
        ev = {"po_id": po["id"], "vendor_id": po["vendor_id"], "po_qty": po["qty"], "rate_paise": rate,
              "received_qty": got, "billed_qty": billed_qty, "paid_paise": paid, "payment_terms": po["payment_terms"],
              "grns": [g["id"] for g in grn_by_po[po["id"]]], "bills": [b["id"] for b in bills]}
        advances = adv_by_po[po["id"]]
        pending = po["payment_terms"] == "ADVANCE" and advances and not bills and \
            all((_d(today) - _d(s["settled_on"])).days < 30 for s in advances)
        over = max(billed_qty, paid_qty) - got
        if over > 0 and (bills or advances) and not pending:
            hits.append(_hit("D15", "SHORT_RECEIPT", "purchase_order", po["id"], 5, over * rate,
                             f"Purchase order {po['id']} with vendor {po['vendor_id']}: {max(billed_qty, paid_qty)} units "
                             f"billed or paid for, {got} received to date (all goods receipts, net of returns); "
                             f"{_inr(over * rate)} at the PO rate is not supported by a receipt.", ev))
        for b in bills:
            if b["qty"] and rate and b["taxable_paise"] * 100 > b["qty"] * rate * 102:
                excess = b["taxable_paise"] - b["qty"] * rate
                hits.append(_hit("D15", "PRICE_VARIANCE", "purchase_bill", b["id"], 4, excess,
                                 f"Bill {b['id']} charges {_inr(b['taxable_paise'] // b['qty'])} a unit against the PO rate "
                                 f"of {_inr(rate)} (more than 2% over); {_inr(excess)} in excess.",
                                 {**ev, "bill_id": b["id"], "bill_rate_paise": b["taxable_paise"] // b["qty"]}))
        if po["payment_terms"] != "ADVANCE" and not grn_by_po[po["id"]]:
            for b in bills:
                for s in pay_by_bill[b["id"]]:
                    hits.append(_hit("D15", "PAYMENT_WITHOUT_RECEIPT", "settlement", s["id"], 5, s["amount_paise"],
                                     f"Payment {s['id']} settles bill {b['id']} of PO {po['id']}, but nothing has been "
                                     f"received against that order and the terms are not advance.", ev))
        # received on or before the period end, billed only after it, and not accrued
        recv_in = received(po["id"], end)
        if recv_in > 0 and bills and all(b["bill_date"] > end for b in bills):
            first = min((g for g in grn_by_po[po["id"]] if g["received_on"] <= end and g["kind"] == "RECEIPT"),
                        key=lambda g: g["received_on"])
            accrued = any(a["party_id"] == po["vendor_id"] and first["received_on"] <= a["voucher_date"] <= end
                          for a in P["accruals"])
            if not accrued:
                hits.append(_hit("D15", "UNRECORDED_LIABILITY", "goods_receipt", first["id"], 4, recv_in * rate,
                                 f"Goods receipt {first['id']} ({first['received_on']}) puts {recv_in} units of PO {po['id']} "
                                 f"in the period, but the vendor's bill is dated after the period end and no accrual "
                                 f"was booked: {_inr(recv_in * rate)} of liabilities (and purchases) is unrecorded.", ev))
    # duplicate payments: one bill settled twice, or the same vendor paid the same amount twice within 7 days
    for bid, pays in pay_by_bill.items():
        b = P["bills"].get(bid)
        if b and len(pays) > 1 and sum(s["amount_paise"] for s in pays) > b["taxable_paise"] + b["tax_paise"]:
            for s in pays[1:]:
                hits.append(_hit("D15", "DUPLICATE_PAYMENT", "settlement", s["id"], 5, s["amount_paise"],
                                 f"Payment {s['id']} settles bill {bid} a second time (first paid by {pays[0]['id']}).",
                                 {"bill_id": bid, "payments": [p["id"] for p in pays], "vendor_id": b["vendor_id"]}))
    by_vendor = defaultdict(list)
    for s in P["vendor_payments"]:
        by_vendor[(s["party_id"], s["amount_paise"])].append(s)
    flagged = {h["object_id"] for h in hits if h["code"] == "DUPLICATE_PAYMENT"}
    for (vendor, amt), pays in by_vendor.items():
        bills_same = [b for b in P["bills"].values() if b["vendor_id"] == vendor and b["taxable_paise"] + b["tax_paise"] == amt]
        for a, b in zip(pays, pays[1:]):
            if (_d(b["settled_on"]) - _d(a["settled_on"])).days <= 7 and len(bills_same) < len(pays) and \
                    b["id"] not in flagged and not (a["doc_type"] == "PURCHASE" and b["doc_type"] == "PURCHASE"
                                                   and a["doc_id"] != b["doc_id"]):
                hits.append(_hit("D15", "DUPLICATE_PAYMENT", "settlement", b["id"], 5, amt,
                                 f"Vendor {vendor} was paid {_inr(amt)} twice within 7 days ({a['id']}, {b['id']}) with no "
                                 f"second bill for that amount.", {"payments": [a["id"], b["id"]], "vendor_id": vendor}))
                flagged.add(b["id"])
    for s in P["vendor_payments"]:
        bank = P["bank"].get(s["bank_txn_id"]) or {}
        master = _digits((P["parties"].get(s["party_id"]) or {}).get("bank_account"))
        paid_to = _digits(bank.get("cp_account"))
        if paid_to and master and paid_to != master:
            hits.append(_hit("D15", "BENEFICIARY_MISMATCH", "settlement", s["id"], 5, s["amount_paise"],
                             f"Payment {s['id']} to vendor {s['party_id']} went to a bank account that is not the vendor's "
                             f"(bank line {bank.get('id')}; account ending {paid_to[-4:]}).",
                             {"vendor_id": s["party_id"], "bank_txn": bank.get("id")}))
        if s["doc_type"] == "ADVANCE" and (_d(today) - _d(s["settled_on"])).days > 90 and \
                (not s["doc_id"] or received(s["doc_id"]) <= 0):
            hits.append(_hit("D15", "ADVANCE_UNSETTLED", "settlement", s["id"], 3, s["amount_paise"],
                             f"Advance {s['id']} of {_inr(s['amount_paise'])} to vendor {s['party_id']} is more than 90 "
                             f"days old with no goods received against it.", {"vendor_id": s["party_id"], "po_id": s["doc_id"]}))
    return _dedup(hits)


DETECTORS = {"D3": d3, "D4": d4, "D5": d5, "D6": d6, "D7": d7, "D9": d9, "D13": d13, "D14": d14, "D15": d15}


def _self_related(e):
    """Every party reachable from SELF through party_links (directors, KMP, their relatives and entities)."""
    adj = defaultdict(set)
    for a, b in e.execute("SELECT from_party, to_party FROM party_links"):
        adj[a].add(b)
        adj[b].add(a)
    seen, todo = {"SELF"}, ["SELF"]
    while todo:
        for n in adj[todo.pop()]:
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return seen - {"SELF"}


def run_all(engagement_id, detectors=None, incremental=False):
    """Run the population procedures; write risk_hits; -> {run_id, counts: {detector: {code: n}}, top: [hit] (20)}.
    `incremental` is accepted for the n8n schedule; a full run over 7,000 invoices takes seconds, so it re-runs all."""
    from app import intake, related_parties
    if engagement_id == config.ENGAGEMENT_ID:
        intake.ensure_engagement()
    want = set(detectors or ALL)
    bad = want - set(ALL)
    if bad:
        raise ValueError(f"INVALID_ARGUMENT: detectors are {', '.join(ALL)} (D0 runs with reconcile_register_to_system, "
                         f"D8 inside test_sample, D10 in the risk graph)")
    run_id = f"RUN-{config.now()}"
    with db.borrow("audit", "system") as a:
        eng = dict(a.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone())
        confirmed = {r[0] for r in a.execute("SELECT id FROM findings WHERE engagement_id = ? AND status IN"
                                             " ('CONFIRMED', 'MODIFIED')", (engagement_id,))}
    rp = {}
    if want & {"D1", "D2"}:
        related_parties.run_d1_d2(engagement_id)
    try:
        rp = {k: v for k, v in related_parties.rp_map(engagement_id).items() if v.get("independent") or v.get("declared")}
    except ValueError:
        rp = {}
    with db.borrow("erp", "system") as e, db.borrow("ext", "system") as x:
        P = load_population(e, x)
        related = _self_related(e) | set(rp)
    rp_acc = {_digits(P["parties"][pid]["bank_account"]): pid for pid in sorted(related)
              if pid in P["parties"] and _digits(P["parties"][pid]["bank_account"])}
    hits = []
    for d, fn in DETECTORS.items():
        if d not in want:
            continue
        if d == "D4":
            hits += fn(P, eng, rp_acc)
        elif d == "D7":
            hits += fn(P, eng, confirmed)
        elif d == "D9":
            hits += fn(P, eng, rp)
        else:
            hits += fn(P, eng)
    det = want & set(DETECTORS)
    if det:
        save_hits(engagement_id, run_id, hits, det)
    from app import risk_graph                       # full run: D10 cycles + re-baselined scores and snapshots (19.6)
    company = risk_graph.build(engagement_id, persist=True)["company"]
    with db.borrow("audit", "system") as a:
        counts = defaultdict(dict)
        for d, c, n in a.execute("SELECT detector, code, count(*) FROM risk_hits WHERE engagement_id = ? GROUP BY"
                                 " detector, code ORDER BY detector, code", (engagement_id,)):
            counts[d][c] = n
        top = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ? ORDER BY severity DESC,"
                                          " impact_paise DESC, id LIMIT 20", (engagement_id,))]
    return {"run_id": run_id, "counts": dict(counts), "top": top, "company": company}
