"""Money trail (vault/13 MT-3): where the books say money went (CLAIMED) vs where independent records prove it went
(VERIFIED), plus identity inferences (INFERRED), for one invoice, credit note, PO, GRN, bill, payment, bank line or party.

Rules (vault/13 §1): every edge carries its provenance; the numbers describe the traced documents only (hop 1), so a
transfer seen further out is shown but never attributed (A pays B and B pays C does not mean A's money reached C);
circular value is the minimum-span value from the D10 hits, never a sum of the cycle's edges. Deterministic only:
an agent may explain these numbers, never compute them.
"""
import json
from collections import defaultdict

from app import config, db, money, related_parties

SELF = "SELF"
MAX_EDGES = 400


def _digits(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _acct_node(digits):
    return f"ACCT:{digits}"


class _Trail:
    def __init__(self, e, x):
        self.e, self.x = e, x
        self.parties = {r["id"]: dict(r) for r in e.execute("SELECT * FROM parties")}
        self.owner = {}
        for pid, p in self.parties.items():
            d = _digits(p["bank_account"])
            if d:
                self.owner.setdefault(d, pid)
        self.nodes, self.edges = {}, []

    # ---- graph
    def node(self, nid, hop):
        if nid in self.nodes:
            self.nodes[nid]["hop"] = min(self.nodes[nid]["hop"], hop)
            return nid
        if nid.startswith("ACCT:"):
            n = {"id": nid, "type": "bank_account", "label": f"account ending {nid[-4:]}"}
        else:
            p = self.parties.get(nid) or {}
            n = {"id": nid, "type": "company" if nid == SELF else "party", "label": p.get("name") or nid}
        self.nodes[nid] = {**n, "hop": hop}
        return nid

    def edge(self, a, b, kind, amount, on, doc_ids, source, status, refs, hop, **extra):
        self.node(a, hop if a != SELF else 0)
        self.node(b, hop if b != SELF else 0)
        self.edges.append({"from": a, "to": b, "kind": kind, "amount_paise": int(amount or 0),
                           "amount_formatted": money.fmt_inr(int(amount or 0)), "date": on,
                           "doc_ids": list(doc_ids), "source": source, "status": status,
                           "evidence_refs": [r for r in refs if r], "hop": hop, **extra})

    def payee(self, bank_row, fallback):
        """The node the bank line names: the master owner of its counterparty account, else the bare account."""
        d = _digits((bank_row or {}).get("cp_account"))
        if not d:
            return fallback, False
        return (self.owner.get(d) or _acct_node(d)), True

    # ---- documents
    def one(self, sql, args=()):
        r = self.e.execute(sql, args).fetchone()
        return dict(r) if r else None

    def invoice_total(self, iid):
        r = self.e.execute("SELECT COALESCE(SUM(taxable_paise + igst_paise + cgst_paise + sgst_paise), 0) FROM invoice_lines"
                           " WHERE invoice_id = ?", (iid,)).fetchone()[0]
        return r + (self.one("SELECT round_off_paise FROM invoices WHERE id = ?", (iid,)) or {}).get("round_off_paise", 0)


def _resolve(t, oid):
    """-> (object_type, id). Accepts ids and the human numbers (invoice_no, cn_no, po_no, grn_no)."""
    oid = str(oid or "").strip()
    probes = (("invoice", "SELECT id FROM invoices WHERE id = ? OR invoice_no = ?"),
              ("credit_note", "SELECT id FROM credit_notes WHERE id = ? OR cn_no = ?"),
              ("purchase_order", "SELECT id FROM purchase_orders WHERE id = ? OR po_no = ?"),
              ("goods_receipt", "SELECT id FROM goods_receipts WHERE id = ? OR grn_no = ?"),
              ("purchase_bill", "SELECT id FROM purchase_bills WHERE id = ? OR id = ?"),
              ("settlement", "SELECT id FROM settlements WHERE id = ? OR id = ?"),
              ("party", "SELECT id FROM parties WHERE id = ? OR id = ?"))
    for kind, sql in probes:
        r = t.e.execute(sql, (oid, oid)).fetchone()
        if r:
            return kind, r[0]
    if t.x.execute("SELECT 1 FROM bank_txns WHERE id = ?", (oid,)).fetchone():
        return "bank_txn", oid
    raise LookupError(f"NOT_FOUND: no invoice, credit note, PO, GRN, bill, settlement, bank line or party '{oid}'. "
                      f"Use an id from list_audit_items or query_records. Example: trace_money(object_id='PO-000001')")


def _scope(t, kind, oid):
    """The root's documents: {doc_type: set(ids)}. A purchase document pulls in its whole PO chain; a settlement pulls in
    every settlement on the same bank line (one movement of money) and the documents they settle."""
    s = defaultdict(set)

    def po_chain(po_id):
        s["purchase_order"].add(po_id)
        s["goods_receipt"] |= {r[0] for r in t.e.execute("SELECT id FROM goods_receipts WHERE po_id = ?", (po_id,))}
        bills = {r[0] for r in t.e.execute("SELECT id FROM purchase_bills WHERE po_id = ?", (po_id,))}
        s["purchase_bill"] |= bills
        s["settlement"] |= {r[0] for r in t.e.execute(
            "SELECT id FROM settlements WHERE direction = 'PAYMENT' AND doc_type = 'ADVANCE' AND doc_id = ?", (po_id,))}
        for b in bills:
            bill(b, chain=False)

    def bill(bid, chain=True):
        b = t.one("SELECT * FROM purchase_bills WHERE id = ?", (bid,))
        if chain and b["po_id"]:
            return po_chain(b["po_id"])
        s["purchase_bill"].add(bid)
        s["settlement"] |= {r[0] for r in t.e.execute(
            "SELECT id FROM settlements WHERE direction = 'PAYMENT' AND doc_type = 'PURCHASE' AND doc_id = ?", (bid,))}

    def invoice(iid):
        s["invoice"].add(iid)
        s["settlement"] |= {r[0] for r in t.e.execute(
            "SELECT id FROM settlements WHERE direction = 'RECEIPT' AND doc_type = 'INVOICE' AND doc_id = ?", (iid,))}
        s["credit_note"] |= {r[0] for r in t.e.execute("SELECT DISTINCT cn_id FROM cn_lines WHERE invoice_id = ?", (iid,))}

    def settlement(sid):
        st = t.one("SELECT * FROM settlements WHERE id = ?", (sid,))
        sibs = [dict(r) for r in t.e.execute("SELECT * FROM settlements WHERE bank_txn_id = ?", (st["bank_txn_id"],))] \
            if st["bank_txn_id"] else [st]
        for r in sibs:
            s["settlement"].add(r["id"])
            if r["doc_type"] == "INVOICE" and r["doc_id"]:
                invoice(r["doc_id"])
            elif r["doc_type"] == "PURCHASE" and r["doc_id"]:
                bill(r["doc_id"])
            elif r["doc_type"] == "ADVANCE" and r["direction"] == "PAYMENT" and r["doc_id"]:
                po_chain(r["doc_id"])

    if kind == "invoice":
        invoice(oid)
    elif kind == "credit_note":
        s["credit_note"].add(oid)
        for r in t.e.execute("SELECT DISTINCT invoice_id FROM cn_lines WHERE cn_id = ? AND invoice_id IS NOT NULL", (oid,)):
            invoice(r[0])
    elif kind == "purchase_order":
        po_chain(oid)
    elif kind == "goods_receipt":
        po_chain(t.one("SELECT po_id FROM goods_receipts WHERE id = ?", (oid,))["po_id"])
    elif kind == "purchase_bill":
        bill(oid)
    elif kind == "settlement":
        settlement(oid)
    elif kind == "bank_txn":
        for r in t.e.execute("SELECT id FROM settlements WHERE bank_txn_id = ?", (oid,)):
            settlement(r[0])
    elif kind == "party":
        for r in t.e.execute("SELECT id FROM invoices WHERE party_id = ?", (oid,)):
            invoice(r[0])
        for r in t.e.execute("SELECT id FROM credit_notes WHERE party_id = ?", (oid,)):
            s["credit_note"].add(r[0])
        for r in t.e.execute("SELECT id FROM purchase_orders WHERE vendor_id = ?", (oid,)):
            po_chain(r[0])
        for r in t.e.execute("SELECT id FROM purchase_bills WHERE vendor_id = ?", (oid,)):
            bill(r[0])
        s["settlement"] |= {r[0] for r in t.e.execute("SELECT id FROM settlements WHERE party_id = ?", (oid,))}
    return s


def _doc_edges(t, s, hop=1):
    """Hop-1 edges from the root's documents. Returns the facts the numbers are computed from."""
    facts = {"recorded": 0, "verified": 0, "received": None, "po_value": 0}
    for iid in sorted(s["invoice"]):
        inv = t.one("SELECT * FROM invoices WHERE id = ?", (iid,))
        if inv["status"] != "ISSUED":
            continue
        total = t.invoice_total(iid)
        facts["recorded"] += total
        t.edge(SELF, inv["party_id"], "SALE", total, inv["invoice_date"], [iid], "BOOKS", "CLAIMED", [inv["invoice_no"]], hop)
        ein = t.x.execute("SELECT * FROM einvoices WHERE irn = ? AND status = 'ACT'", (inv["irn"] or "",)).fetchone()
        if ein:
            t.edge(SELF, inv["party_id"], "EINVOICE", ein["total_paise"], ein["doc_date"], [iid], "PORTAL", "VERIFIED",
                   [f"IRN ack {ein['ack_no']}"], hop)
        for m in t.e.execute("SELECT m.*, im.ewb_no FROM invoice_movements im JOIN movements m ON m.id = im.movement_id"
                             " WHERE im.invoice_id = ?", (iid,)):
            ewb = t.x.execute("SELECT * FROM ewaybills WHERE ewb_no = ? AND status = 'ACT'", (m["ewb_no"] or "",)).fetchone()
            if ewb:
                t.edge(SELF, inv["party_id"], "DISPATCH", ewb["value_paise"], m["moved_on"], [iid, m["id"]], "PORTAL",
                       "VERIFIED", [f"EWB {ewb['ewb_no']}", m["lr_no"]], hop)
            else:
                t.edge(SELF, inv["party_id"], "DISPATCH", 0, m["moved_on"], [iid, m["id"]], "BOOKS", "CLAIMED", [m["lr_no"]], hop)
    for cid in sorted(s["credit_note"]):
        cn = t.one("SELECT * FROM credit_notes WHERE id = ?", (cid,))
        if cn["status"] != "ISSUED":
            continue
        amt = t.e.execute("SELECT COALESCE(SUM(taxable_paise + igst_paise + cgst_paise + sgst_paise), 0) FROM cn_lines"
                          " WHERE cn_id = ?", (cid,)).fetchone()[0]
        t.edge(SELF, cn["party_id"], "CREDIT_NOTE", amt, cn["cn_date"], [cid], "BOOKS", "CLAIMED", [cn["cn_no"]], hop)
    rate = {}
    for pid in sorted(s["purchase_order"]):
        po = t.one("SELECT * FROM purchase_orders WHERE id = ?", (pid,))
        rate[pid] = po["rate_paise"]
        facts["po_value"] += po["qty"] * po["rate_paise"]
        t.edge(SELF, po["vendor_id"], "ORDER", po["qty"] * po["rate_paise"], po["po_date"], [pid], "BOOKS", "CLAIMED",
               [po["po_no"], po["payment_terms"]], hop, qty=po["qty"])
    if s["purchase_order"]:
        facts["received"] = 0
    for gid in sorted(s["goods_receipt"]):
        g = t.one("SELECT g.*, p.vendor_id FROM goods_receipts g JOIN purchase_orders p ON p.id = g.po_id WHERE g.id = ?", (gid,))
        value = g["qty"] * rate.get(g["po_id"], 0)
        sign = 1 if g["kind"] == "RECEIPT" else -1
        facts["received"] += sign * value
        a, b = (g["vendor_id"], SELF) if sign > 0 else (SELF, g["vendor_id"])
        t.edge(a, b, "GOODS_RECEIPT" if sign > 0 else "GOODS_RETURN", value, g["received_on"], [gid, g["po_id"]], "BOOKS",
               "CLAIMED", [g["grn_no"]], hop, qty=g["qty"])
    for bid in sorted(s["purchase_bill"]):
        b = t.one("SELECT * FROM purchase_bills WHERE id = ?", (bid,))
        facts["recorded"] += b["taxable_paise"] + b["tax_paise"]
        t.edge(b["vendor_id"], SELF, "BILL", b["taxable_paise"] + b["tax_paise"], b["bill_date"], [bid] + ([b["po_id"]] if b["po_id"] else []),
               "BOOKS", "CLAIMED", [b["bill_no"]], hop, qty=b["qty"])
    if not s["invoice"] and not s["purchase_bill"]:
        facts["recorded"] += facts["po_value"]          # ordered and (perhaps) paid, never billed: the PO is the record
    # money: one edge per bank line (a line can settle several documents)
    by_line = defaultdict(list)
    for sid in sorted(s["settlement"]):
        st = t.one("SELECT * FROM settlements WHERE id = ?", (sid,))
        by_line[st["bank_txn_id"] or f"none:{sid}"].append(st)
    for line, sts in sorted(by_line.items()):
        party, out = sts[0]["party_id"], sts[0]["direction"] == "PAYMENT"
        amt = sum(r["amount_paise"] for r in sts)
        ids = [r["id"] for r in sts]
        on = sts[0]["settled_on"]
        bank = t.x.execute("SELECT * FROM bank_txns WHERE id = ?", (line,)).fetchone()
        if not s["invoice"] and not s["purchase_bill"] and not s["purchase_order"]:
            facts["recorded"] += amt                    # a bare settlement / advance: the settlement is the record
        if bank is None:
            a, b = (SELF, party) if out else (party, SELF)
            t.edge(a, b, "PAYMENT_OUT" if out else "PAYMENT_IN", amt, on, ids, "BOOKS", "CLAIMED", [], hop)
            continue
        bank = dict(bank)
        who, named = t.payee(bank, party)
        a, b = (SELF, who) if out else (who, SELF)
        t.edge(a, b, "PAYMENT_OUT" if out else "PAYMENT_IN", abs(bank["amount_paise"]), bank["value_date"], ids, "BANK",
               "VERIFIED", [bank["id"], bank["utr"]], hop)
        if who == party:
            facts["verified"] += amt
        else:                                           # the bank names someone else: the books' version is a claim
            a, b = (SELF, party) if out else (party, SELF)
            t.edge(a, b, "PAYMENT_OUT" if out else "PAYMENT_IN", amt, on, ids, "BOOKS", "CLAIMED", [bank["id"]], hop,
                   mismatch="bank counterparty differs from the recorded party")
    return facts


def _identity(t):
    """Undirected identity adjacency: party_links plus shared strong/medium identifiers (the D1 fan-out guard)."""
    adj = defaultdict(dict)
    for r in t.e.execute("SELECT * FROM party_links"):
        adj[r["from_party"]][r["to_party"]] = r["relation"]
        adj[r["to_party"]][r["from_party"]] = r["relation"]
    holders = defaultdict(set)
    for p in t.parties.values():
        for kind, strength, key in related_parties.keys(p):
            if strength in ("STRONG", "MEDIUM") and kind != "SELF_DOMAIN":
                holders[(kind, key)].add(p["id"])
    for (kind, _k), ps in holders.items():
        if 1 < len(ps) <= 3:
            for a in ps:
                for b in ps:
                    if a != b:
                        adj[a].setdefault(b, f"SHARED_{kind}")
    return adj


def _party_money(t, pid, hop):
    """A context party's own money with the company, aggregated per direction (bank-verified where the bank names it)."""
    d = _digits(t.parties[pid]["bank_account"])
    rows = [dict(r) for r in t.x.execute("SELECT * FROM bank_txns WHERE cp_account IS NOT NULL")] if d else []
    lines = [r for r in rows if _digits(r["cp_account"]) == d]
    for out in (True, False):
        mine = [r for r in lines if (r["amount_paise"] < 0) == out]
        if mine:
            a, b = (SELF, pid) if out else (pid, SELF)
            t.edge(a, b, "PAYMENT_OUT" if out else "PAYMENT_IN", sum(abs(r["amount_paise"]) for r in mine),
                   max(r["value_date"] for r in mine), [], "BANK", "VERIFIED", [r["id"] for r in mine][:20], hop,
                   lines=len(mine))


def _expand(t, hops):
    """Hops 2..n: identity neighbours of the parties already on the trail (INFERRED) and those neighbours' own bank
    flows with the company. Shown as context only: nothing here is added to the numbers."""
    if hops < 2:
        return
    adj = _identity(t)
    frontier = {n for n in t.nodes if n != SELF and n in t.parties}
    seen, pairs = set(frontier) | {SELF}, set()
    for hop in range(2, hops + 1):
        nxt = set()
        for pid in sorted(frontier):
            for other, rel in sorted(adj.get(pid, {}).items()):
                if other == SELF or frozenset((pid, other)) in pairs:
                    continue
                pairs.add(frozenset((pid, other)))
                t.edge(pid, other, "IDENTITY", 0, None, [], "IDENTITY", "INFERRED", [rel], hop)
                if other not in seen:
                    seen.add(other)
                    nxt.add(other)
        for pid in sorted(nxt):
            _party_money(t, pid, hop)
        frontier = nxt
        if not frontier or len(t.edges) > MAX_EDGES:
            break


def _affected(a, eid, s, kind, oid):
    """Potentially affected = per object the largest serious (sev >= 4) hit impact from the latest analytics run, summed
    over the traced documents (and the party itself for a party root); each D10 cycle counts once at its minimum-span
    value."""
    objs = {(t, i) for t, ids in s.items() for i in ids}
    if kind == "party":
        objs.add(("party", oid))
    rows = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ? AND severity >= 4", (eid,))]
    best, cycles = {}, {}
    for h in rows:
        ev = json.loads(h["evidence_json"] or "{}") or {}
        if h["detector"] == "D10":
            members = tuple(ev.get("members") or [])
            docs = set(ev.get("docs") or [])
            if (h["object_type"], h["object_id"]) in objs or docs & {i for _t, i in objs} or \
                    (kind == "party" and oid in members):
                cycles[members] = {"members": list(members), "circular_paise": h["impact_paise"],
                                   "circular_formatted": money.fmt_inr(h["impact_paise"]), "flow": ev.get("flow"),
                                   "codes": ev.get("codes"), "docs": sorted(docs)}
            continue
        key = (h["object_type"], h["object_id"])
        if key in objs and h["impact_paise"] > best.get(key, {}).get("impact_paise", -1):
            best[key] = {"object_type": key[0], "object_id": key[1], "code": h["code"], "impact_paise": h["impact_paise"]}
    basis = sorted(best.values(), key=lambda b: (-b["impact_paise"], b["object_id"]))
    total = sum(b["impact_paise"] for b in basis) + sum(c["circular_paise"] for c in cycles.values())
    return total, basis, list(cycles.values())


def _aggregate(edges):
    """A party root can have hundreds of documents: one edge per (from, to, kind, source, status)."""
    agg = {}
    for x in edges:
        k = (x["from"], x["to"], x["kind"], x["source"], x["status"])
        if k not in agg:
            agg[k] = {**x, "doc_ids": list(x["doc_ids"]), "evidence_refs": list(x["evidence_refs"]), "count": 0}
            agg[k]["amount_paise"] = 0
        g = agg[k]
        g["amount_paise"] += x["amount_paise"]
        g["count"] += 1
        g["date"] = max(filter(None, (g["date"], x["date"])), default=None)
        g["hop"] = min(g["hop"], x["hop"])
        if g["count"] > 1:
            g["doc_ids"] = (g["doc_ids"] + x["doc_ids"])[:50]
            g["evidence_refs"] = (g["evidence_refs"] + x["evidence_refs"])[:50]
    for g in agg.values():
        g["amount_formatted"] = money.fmt_inr(g["amount_paise"])
    return list(agg.values())


def trace(object_id, hops=2, engagement_id=None, role="audit_staff"):
    """-> {root, nodes, edges, numbers, cycles}. numbers = {recorded_paise (the books), verified_paise (bank lines that
    name the recorded counterparty), received_paise (goods received at the PO rate; None outside purchase-to-pay),
    affected_paise (needs investigation, not a loss), affected_basis, attribution: NOT_ESTABLISHED}. Read-only handles."""
    hops = max(1, min(3, int(hops or 2)))
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("erp", role) as e, db.borrow("ext", role) as x, db.borrow("audit", role) as a:
        t = _Trail(e, x)
        kind, oid = _resolve(t, object_id)
        t.node(SELF, 0)
        s = _scope(t, kind, oid)
        facts = _doc_edges(t, s)
        _expand(t, hops)
        affected, basis, cycles = _affected(a, eid, s, kind, oid)
    edges = _aggregate(t.edges) if kind == "party" else t.edges
    nums = {"recorded_paise": facts["recorded"], "verified_paise": facts["verified"],
            "received_paise": facts["received"], "affected_paise": affected}
    numbers = {**nums, **{k.replace("_paise", "_formatted"): money.fmt_inr(v) for k, v in nums.items() if v is not None},
               "affected_basis": basis, "attribution": "NOT_ESTABLISHED",
               "note": "Numbers cover the traced documents only. Transfers beyond hop 1 are context: nothing is attributed "
                       "downstream (only the company's own bank is held). Circular value is the minimum-span value."}
    return {"root": {"object_type": kind, "object_id": oid, "hops": hops,
                     "documents": {k: sorted(v) for k, v in s.items() if v}},
            "nodes": sorted(t.nodes.values(), key=lambda n: (n["hop"], n["id"])), "edges": edges[:MAX_EDGES],
            "numbers": numbers, "cycles": cycles}
