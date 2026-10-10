"""AuditGraph: the risk engine over the detectors (05 §19). It ranks, propagates, tracks risk over time and flags the
company; it never replaces D0-D14 (they produce the findings the PS judges). Wording: "risk of material misstatement".

- Temporal multigraph (networkx MultiDiGraph) of SELF, parties and people: SALE / PURCHASE / PAYMENT_IN / PAYMENT_OUT
  transaction edges (amount, date, doc) and CONTROL / DIRECTOR / RELATIVE / SHARED_ID identity edges (inferred).
- Circular flows (19.4): time-ordered cycles through SELF within 90 days, cut by MINIMUM-SPAN DECOMPOSITION
  (Kumar et al. 2017): circular value = min residual along the cycle, subtracted into an analytical residual view,
  repeated until no cycle remains. Hits (D10) only when the circular value >= clearly trivial and not explained.
- Engine A (transaction anomaly, noisy-OR over the entry's own hits), Engine B (entity risk E, five factors), fusion R
  with a hard-evidence floor, confidence C, bands, company flag (SA 315), append-only risk_snapshots.
- on_event(): per-document update after every ERP commit (05 §19.6), best-effort, reading neighbours' E from the
  latest stored snapshot only (no self-inflation).
Limitations (19.10): simulated "independent" sources, partial network visibility, provisional weights, synthetic
evaluation. Scores rank risk; they are not calibrated fraud probabilities.
"""
import json
import statistics
from collections import defaultdict
from datetime import date, timedelta

from app import config, db, money

WINDOW_DAYS = 90
MAX_LEN = 5
MAX_ID_HOPS = 3
FAMILY = {  # 05 §18 rows -> the PS irregularity families
    "D0": "K", "INVALID_GSTIN": "K", "UNDISCLOSED_RP": "A", "PAN_GSTIN_MISMATCH": "A", "CUSTOMER_CLUSTER": "A",
    "RP_PERIOD_MISSTATED": "B", "D3": "C", "BACKDATED_ENTRY": "C", "POD_RECORDED_LATE": "C",
    "NO_MOVEMENT": "D", "QTY_SHORT": "D", "DISPATCH_PARTY_MISMATCH": "D", "EWB_REQUIRED_MISSING": "D",
    "SPLIT_BELOW_THRESHOLD": "D", "VEHICLE_DOUBLE_BOOKED": "D", "EWB_NOT_FOUND": "D", "D5": "E", "D6": "F",
    "D7": "G", "D8": "H", "D14": "H", "D9": "I", "D10": "J", "D11": "L", "D12": "L", "D13": "C",
    "UNPAID_90D": "D", "THIRD_PARTY_PAYER": "A", "PAYER_IS_RP": "A", "LR_VEHICLE_MISMATCH": "D",
    "EWB_REASON_NOT_SUPPLY": "D", "LATE_CANCELLATION": "I", "IRN_LATE": "C", "SEQUENCE_BREAK": "C",
    "D15": "P",                                       # purchase to pay (vault/13 MT-2)
}
# portal / bank / register-sourced deterministic hits: hard evidence is never diluted by averaging (19.5 FLOOR)
HARD = {"NOT_IN_SOR", "MISSING_FROM_REGISTER", "TAXABLE_DIFF", "DATE_DIFF", "FY_DIFF", "CANCELLED_BUT_LISTED",
        "EWB_NOT_FOUND", "NO_MOVEMENT", "EWB_REQUIRED_MISSING", "EWB_VALUE_MISMATCH", "EWB_DOC_MISMATCH", "IRN_MISMATCH",
        "IRN_SIGNATURE_BAD", "IRN_NOT_ON_PORTAL", "NOT_IN_GSTR1", "GSTR1_VALUE_DIFF", "REVENUE_WITHOUT_SALE",
        "REVENUE_POSTING_DIFF", "DUPLICATE_POSTING", "PREMATURE", "POST_PERIOD_REVERSAL", "PAYER_IS_RP",
        "BELONGS_TO_OTHER_TXN", "EWB_NOT_ON_PORTAL", "DOC_FIELD_MISMATCH", "QTY_SHORT", "BACKDATED_ENTRY",
        "CIRCULAR_FLOW", "ROUND_TRIP_GOODS", "ROUND_TRIP_CASH",
        # D15: bank-line and goods-receipt sourced
        "SHORT_RECEIPT", "PAYMENT_WITHOUT_RECEIPT", "DUPLICATE_PAYMENT", "BENEFICIARY_MISMATCH", "UNRECORDED_LIABILITY"}
INDEPENDENT = {"D0", "D6", "D8"}                       # register / IRP / EWB / GSTN / document evidence
HEURISTIC = {"D5", "D14"}


def family(hit):
    return FAMILY.get(hit["code"]) or FAMILY.get(hit["detector"])


def band(r):
    return next(b for t, b in config.RISK_BANDS if r >= t)

# ---------------------------------------------------------------- minimum-span decomposition (19.4)

def decompose(tx_edges, identity, start="SELF", window_days=WINDOW_DAYS, max_len=MAX_LEN, max_id_hops=MAX_ID_HOPS):
    """Minimum-span decomposition of time-ordered cycles.

    tx_edges: [{id, a, b, amount, ts, kind, ...}] transaction edges (a -> b), amount > 0, ts 'YYYY-MM-DD'.
    identity: {node: {neighbour, ...}} undirected identity links (no amount, no time; at most max_id_hops in a row).
    A cycle leaves `start` on a transaction edge, returns to it on a transaction edge, has >= 2 transaction edges in
    non-decreasing time within window_days of the first, and at most max_len edges. Each found cycle carries
    circular = min residual over its transaction edges, which is subtracted along the cycle (the residual view; the
    original amounts are untouched), and the search repeats until no cycle with positive residual remains.
    -> (cycles [{edges, members, circular, span_days, id_hops}], residual {edge id: paise})."""
    residual = {e["id"]: e["amount"] for e in tx_edges}
    out_of = defaultdict(list)
    for e in tx_edges:
        out_of[e["a"]].append(e)
    for v in out_of.values():
        v.sort(key=lambda e: (e["ts"], e["id"]))
    # prune: only nodes that can get back to `start` within max_len - 1 steps (transaction or identity, time ignored)
    back = defaultdict(set)
    for e in tx_edges:
        back[e["b"]].add(e["a"])
    for a, ns in identity.items():
        for b in ns:
            back[a].add(b)
    can_return, frontier = {start}, [start]
    for _ in range(max_len - 1):
        frontier = [p for n in frontier for p in back.get(n, ()) if p not in can_return]
        can_return.update(frontier)

    def find():
        for first in out_of.get(start, []):
            if residual[first["id"]] <= 0 or first["b"] not in can_return:
                continue
            b = first["b"]
            limit = (date.fromisoformat(first["ts"]) + timedelta(days=window_days)).isoformat()
            stack = [(b, [first], [start, b], first["ts"], 0)]
            while stack:
                node, path, nodes, t, hops = stack.pop()
                if len(path) >= max_len:
                    continue
                for e in out_of.get(node, []):              # transaction edges, later in time, inside the window
                    if residual[e["id"]] <= 0 or e["ts"] < t or e["ts"] > limit:
                        continue
                    if e["b"] == start:
                        return path + [e], nodes, hops
                    if e["b"] not in nodes:
                        stack.append((e["b"], path + [e], nodes + [e["b"]], e["ts"], 0))
                if hops < max_id_hops:
                    for g in sorted(identity.get(node, ())):
                        if g not in nodes and g != start:
                            stack.append((g, path + [{"id": None, "a": node, "b": g, "kind": "IDENTITY"}],
                                          nodes + [g], t, hops + 1))
        return None

    cycles = []
    while True:
        got = find()
        if not got:
            break
        path, nodes, hops = got
        tx = [e for e in path if e["id"] is not None]
        if len(tx) < 2:
            break
        c = min(residual[e["id"]] for e in tx)
        for e in tx:
            residual[e["id"]] -= c
        cycles.append({"edges": [{k: e.get(k) for k in ("id", "a", "b", "kind", "ts", "amount", "doc_id")} for e in path],
                       "members": nodes, "circular": c,
                       "span_days": (date.fromisoformat(tx[-1]["ts"]) - date.fromisoformat(tx[0]["ts"])).days,
                       "id_hops": sum(1 for e in path if e["id"] is None)})
    return cycles, residual

# ---------------------------------------------------------------- graph

def _digits(s):
    import re
    return re.sub(r"\D", "", str(s or "")).lstrip("0")


def build_edges(P, e):
    """Transaction edges (sales, purchases, payments in/out) and identity adjacency from the books."""
    from app import related_parties
    owner = {_digits(p["bank_account"]): pid for pid, p in P["parties"].items() if _digits(p["bank_account"])}
    tx = []
    for inv in P["invoices"].values():
        if inv["status"] == "ISSUED" and inv["taxable"] > 0:
            tx.append({"id": f"S:{inv['id']}", "a": "SELF", "b": inv["party_id"], "amount": inv["taxable"],
                       "ts": inv["invoice_date"], "kind": "SALE", "doc_id": inv["id"],
                       "items": {l["item_id"]: l["qty"] for l in inv["lines"] if not l["item_id"].startswith("CHG")},
                       "hsn": sorted({str(l["hsn"])[:4] for l in inv["lines"] if not l["item_id"].startswith("CHG")})})
    for r in e.execute("SELECT p.*, i.hsn FROM purchase_bills p LEFT JOIN items i ON i.id = p.item_id"):
        tx.append({"id": f"P:{r['id']}", "a": r["vendor_id"], "b": "SELF", "amount": r["taxable_paise"], "ts": r["bill_date"],
                   "kind": "PURCHASE", "doc_id": r["id"], "items": {r["item_id"]: r["qty"]} if r["item_id"] else {},
                   "hsn": [str(r["hsn"])[:4]] if r["hsn"] else []})
    for r in e.execute("SELECT * FROM settlements WHERE direction = 'PAYMENT'"):
        tx.append({"id": f"PO:{r['id']}", "a": "SELF", "b": r["party_id"], "amount": r["amount_paise"], "ts": r["settled_on"],
                   "kind": "PAYMENT_OUT", "doc_id": r["id"]})
    seen_bt = set()
    for r in e.execute("SELECT * FROM settlements WHERE direction = 'RECEIPT' ORDER BY id"):
        if r["bank_txn_id"] in seen_bt:
            continue                                    # one bank line can settle many invoices: one money edge
        seen_bt.add(r["bank_txn_id"])
        b = P["bank"].get(r["bank_txn_id"]) or {}
        payer = owner.get(_digits(b.get("cp_account"))) or r["party_id"]
        tx.append({"id": f"PI:{r['bank_txn_id']}", "a": payer, "b": "SELF", "amount": abs(b.get("amount_paise") or r["amount_paise"]),
                   "ts": r["settled_on"], "kind": "PAYMENT_IN", "doc_id": r["bank_txn_id"], "for_party": r["party_id"]})
    identity, kinds = defaultdict(set), {}
    for r in e.execute("SELECT * FROM party_links"):
        identity[r["from_party"]].add(r["to_party"])
        identity[r["to_party"]].add(r["from_party"])
        kinds[frozenset((r["from_party"], r["to_party"]))] = r["relation"]
    holders = defaultdict(set)
    for p in P["parties"].values():
        for kind, strength, key in related_parties.keys(p):
            if strength in ("STRONG", "MEDIUM") and kind != "SELF_DOMAIN":
                holders[(kind, key)].add(p["id"])
    for (kind, _k), ps in holders.items():
        if 1 < len(ps) <= 3:                               # the same fan-out guard as D1
            for a in ps:
                for b in ps:
                    if a != b:
                        identity[a].add(b)
                        kinds.setdefault(frozenset((a, b)), f"SHARED_{kind}")
    return tx, identity, kinds


def find_cycles(P, e, trivial):
    """Goods and cash cycles through SELF, each decomposed; classified per 05 D10 / 19.4."""
    tx, identity, kinds = build_edges(P, e)
    out = []
    for flow, keep in (("GOODS", {"SALE", "PURCHASE"}), ("CASH", {"PAYMENT_OUT", "PAYMENT_IN"})):
        edges = [x for x in tx if x["kind"] in keep]
        cycles, residual = decompose(edges, identity)
        for c in cycles:
            t = [x for x in c["edges"] if x["id"]]
            full = {x["id"]: x for x in edges}
            first, last = full[t[0]["id"]], full[t[-1]["id"]]
            codes = []
            if flow == "GOODS":
                same = set(first.get("hsn", [])) & set(last.get("hsn", []))
                q1 = sum(first.get("items", {}).values()) or 0
                q2 = sum(last.get("items", {}).values()) or 0
                matched = bool(same) and q1 and abs(q1 - q2) <= 0.1 * max(q1, q2) and c["span_days"] <= 60
                codes = ["ROUND_TRIP_GOODS"] if matched else ["RECIPROCAL_EXPLAINED"]
            else:
                close = abs(first["amount"] - last["amount"]) <= 0.02 * max(first["amount"], last["amount"])
                if close and c["span_days"] <= 15:
                    codes = ["ROUND_TRIP_CASH"] + (["MONEY_PATH"] if c["id_hops"] >= 2 else [])
                else:
                    codes = ["UNMATCHED_FLOW"]
            c.update(flow=flow, codes=codes, flagged=c["circular"] >= trivial and codes[0] not in
                     ("RECIPROCAL_EXPLAINED", "UNMATCHED_FLOW"),
                     links=[kinds.get(frozenset((x["a"], x["b"]))) for x in c["edges"] if not x["id"]],
                     residuals={x["id"]: residual[x["id"]] for x in t})
            out.append(c)
    return out, tx, identity, kinds

# ---------------------------------------------------------------- scores (19.2 - 19.7)

def _engine_a(hits):
    p = 1.0
    for h in hits:
        p *= 1 - min(1.0, config.risk_weight(h["code"]) * h["severity"] / 5)
    return round(100 * (1 - p))


def _confidence(hits, tested=None):
    if not hits:
        return 1.0 if tested else 0.0
    dets = {h["detector"] for h in hits}
    base = 0.9 if dets & INDEPENDENT or any(h["code"] in HARD for h in hits) else (
        0.4 if dets <= HEURISTIC else 0.7)
    c = base + 0.1 * (len(dets) - 1)
    if tested == "EXCEPTION":
        c += 0.2
    elif tested == "MISSING":
        c -= 0.3
    return round(max(0.0, min(1.0, c)), 2)


def _h_term(n):
    return 0 if n == 0 else 30 if n == 1 else 50 if n == 2 else 70 if n == 3 else 85 if n == 4 else 100


def score(P, hits_by_obj, cycles, eng, pm, prev_e, rp_edges, last_window, circular=None):
    """-> (invoices {id: {A, R, C, band, reasons}}, parties {id: {E, C, band, terms, reasons}}).
    circular: {party: paise} from the last full build, used by per-event updates instead of `cycles`."""
    end = eng["period_end"]
    inv_scores = {}
    by_party = defaultdict(list)
    for inv in P["invoices"].values():
        if inv["status"] != "ISSUED":
            continue
        hs = hits_by_obj.get(("invoice", inv["id"]), [])
        inv_scores[inv["id"]] = {"A": _engine_a(hs), "hits": hs}
        by_party[inv["party_id"]].append(inv)
    circ = defaultdict(int, circular or {})
    for c in cycles:
        if c["flagged"]:
            for m in set(c["members"]) - {"SELF"}:
                circ[m] += c["circular"]
    parties = {}
    for pid, p in P["parties"].items():
        if pid == "SELF":
            continue
        invs = by_party.get(pid, [])
        own = hits_by_obj.get(("party", pid), [])
        C = min(100, round(100 * circ.get(pid, 0) / pm)) if pm else 0
        F = min(100, round(100 * sum(i["taxable"] for i in invs if inv_scores[i["id"]]["A"] >= 30) / pm)) if pm else 0
        tot = sum(i["taxable"] for i in invs)
        share = sum(i["taxable"] for i in invs if last_window[0] <= i["invoice_date"] <= last_window[1]) / tot if tot else 0
        T = min(100, round(200 * share))
        n_open = len(own) + sum(len(inv_scores[i["id"]]["hits"]) for i in invs)
        H = _h_term(n_open)
        neigh = [(prev_e.get(nb, 0), 1.0 if strength == "STRONG" else 0.5) for nb, strength in rp_edges.get(pid, [])]
        N = max((ev * s for ev, s in neigh), default=0)
        E = 0.35 * C + 0.25 * F + 0.15 * T + 0.15 * H + 0.10 * N
        floor = 60 if (circ.get(pid) or any(h["code"] in ("UNDISCLOSED_RP", "CUSTOMER_CLUSTER") for h in own)) else 0
        weak_only = E - 0.10 * N < 60 <= E and all(s < 1 for _e, s in neigh)
        E = max(E, floor)
        if weak_only and not floor:
            E = 59                                    # one weak link can't lift a party above Review
        reasons = [f"{h['code']}" for h in own] + ([f"circular {money.fmt_inr(circ[pid])}"] if circ.get(pid) else [])
        parties[pid] = {"E": round(E), "C": _confidence(own) if own else (0.9 if circ.get(pid) else 0.0),
                        "band": band(E), "terms": {"C": C, "F": F, "T": T, "H": H, "N": round(N)},
                        "reasons": reasons, "circular_paise": circ.get(pid, 0)}
    out = {}
    for iid, s in inv_scores.items():
        inv = P["invoices"][iid]
        e_before = prev_e.get(inv["party_id"], parties.get(inv["party_id"], {}).get("E", 0))
        floor = 60 if any(h["code"] in HARD and h["severity"] >= 4 for h in s["hits"]) else 0
        R = max(0.70 * s["A"] + 0.30 * e_before, floor)
        if R <= 0:
            continue
        out[iid] = {"A": s["A"], "E": round(e_before), "R": round(R), "C": _confidence(s["hits"]), "band": band(R),
                    "reasons": sorted({h["code"] for h in s["hits"]}) + ([f"party {inv['party_id']} E={round(e_before)}"]
                                                                          if e_before >= 30 else [])}
    return out, parties


def company_flag(P, inv_scores, hits, cycles, eng, pm):
    """SA 315 company band (19.7): exposure vs PM, PS families hit (severity >= 4), circular value."""
    start, end = eng["period_start"], eng["period_end"]
    # entries in Review or High only: Low-band scores are "log" (19.5) and would otherwise add up as noise
    exposure = sum(s["R"] * P["invoices"][iid]["taxable"] // 100 for iid, s in inv_scores.items()
                   if s["R"] >= 30 and start <= P["invoices"][iid]["invoice_date"] <= end)
    fams = sorted({family(h) for h in hits if h["severity"] >= 4 and family(h)})
    circular = sum(c["circular"] for c in cycles if c["flagged"])
    if exposure >= pm or len(fams) >= 4 or circular >= pm:
        b = "HIGH"
    elif exposure >= pm / 2 or len(fams) >= 2:
        b = "MODERATE"
    else:
        b = "LOW"
    return {"band": b, "exposure_paise": exposure, "families": fams, "circular_paise": circular,
            "performance_materiality_paise": pm, "sales_tod_size": config.SALES_TOD_SIZE[b]}

# ---------------------------------------------------------------- build / snapshots / on_event

def _hits(a, eid):
    by = defaultdict(list)
    rows = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ?", (eid,))]
    for h in rows:
        oid = h["object_id"]
        if h["object_type"] == "register_row":
            ev = json.loads(h["evidence_json"] or "{}") or {}
            sid = (ev.get("sor") or {}).get("id")
            if sid:
                by[("invoice", sid)].append(h)
            continue
        by[(h["object_type"], oid)].append(h)
    return rows, by


def _latest_e(a, eid=None):
    return {r[0]: r[1] / 1000 for r in a.execute(
        "SELECT object_id, E FROM risk_snapshots WHERE object_type = 'PARTY' AND rowid IN"
        " (SELECT MAX(rowid) FROM risk_snapshots WHERE object_type = 'PARTY' GROUP BY object_id)")}


def _context(eng, e):
    from app import sampling
    pm = sampling.performance_materiality(eng, e)
    om = eng["materiality_paise"] or pm * 10000 // config.PERFORMANCE_MATERIALITY_BP_OF_OM
    trivial = eng["trivial_paise"] or om * config.TRIVIAL_BP_OF_OM // 10000
    end = date.fromisoformat(eng["period_end"])
    d, bd = end, []
    while len(bd) < 10:
        if d.weekday() != 6:
            bd.append(d)
        d -= timedelta(days=1)
    return pm, trivial, (bd[-1].isoformat(), end.isoformat())


def _rp_edges(identity, kinds):
    out = defaultdict(list)
    for a, ns in identity.items():
        for b in ns:
            k = kinds.get(frozenset((a, b)), "")
            out[a].append((b, "MEDIUM" if k in ("SHARED_PHONE", "SHARED_EMAIL") else "STRONG"))
    return out


def build(engagement_id, as_of_run=None, persist=False):
    """-> {nodes: [{id, type, label, E|R, C, band}], edges: [{a, b, kind, amount_paise, ts}], cycles: [...],
    company: {band, exposure_paise, families, circular_paise}}. persist=True (run_analytics) also writes D10 hits and
    a full set of risk_snapshots (run 'RG-<time>'); as_of_run rebuilds the node view from a stored run."""
    from app import analytics
    with db.borrow("audit", "system") as a:
        eng = a.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
        if eng is None:
            return {"nodes": [], "edges": [], "cycles": [],
                    "company": {"band": "LOW", "exposure_paise": 0, "families": [], "circular_paise": 0}}
        eng = dict(eng)
        if as_of_run:
            snaps = [dict(r) for r in a.execute("SELECT * FROM risk_snapshots WHERE run_id = ?", (as_of_run,))]
            comp = next((json.loads(s["reasons_json"] or "{}") for s in snaps if s["object_type"] == "COMPANY"), {})
            return {"nodes": [{"id": s["object_id"], "type": s["object_type"].lower(), "label": s["object_id"],
                               "R" if s["object_type"] in ("INVOICE", "CN") else "E":
                                   round((s["R"] if s["object_type"] in ("INVOICE", "CN") else s["E"]) / 1000),
                               "C": (s["C"] or 0) / 1000, "band": s["band"]} for s in snaps if s["object_type"] != "COMPANY"],
                    "edges": [], "cycles": [], "company": comp}
        prev_e = _latest_e(a)
    with db.borrow("erp", "system") as e, db.borrow("ext", "system") as x:
        P = analytics.load_population(e, x)
        pm, trivial, last_window = _context(eng, e)
        cycles, tx, identity, kinds = find_cycles(P, e, trivial)
    d10 = _d10_hits(cycles, P)
    if persist:
        analytics.save_hits(engagement_id, f"D10-{config.now()}", d10, {"D10"})
    with db.borrow("audit", "system") as a:
        hits, by_obj = _hits(a, engagement_id)
    if not persist:                                    # a read-only view: today's cycles replace the stored D10 hits
        hits = [h for h in hits if h["detector"] != "D10"] + d10
        by_obj = defaultdict(list, {k: [h for h in v if h["detector"] != "D10"] for k, v in by_obj.items()})
        for h in d10:
            by_obj[(h["object_type"], h["object_id"])].append(h)
    inv_scores, parties = score(P, by_obj, cycles, eng, pm, prev_e, _rp_edges(identity, kinds), last_window)
    company = company_flag(P, inv_scores, hits, cycles, eng, pm)
    if persist:
        _snapshot(f"RG-{config.now()}", inv_scores, parties, company)
    return _view(P, tx, identity, kinds, cycles, inv_scores, parties, company)


def _d10_hits(cycles, P):
    hits = []
    for c in cycles:
        if not c["flagged"]:
            continue
        members = [m for m in c["members"] if m != "SELF"]
        ev = {"members": c["members"], "circular_paise": c["circular"], "span_days": c["span_days"], "flow": c["flow"],
              "codes": c["codes"], "links": c["links"], "docs": [x["doc_id"] for x in c["edges"] if x["id"]],
              "residuals": c["residuals"]}
        what = "goods" if c["flow"] == "GOODS" else "money"
        reason = (f"Circular {what} flow through the company: {' -> '.join(c['members'] + ['SELF'])} within "
                  f"{c['span_days']} days; {money.fmt_inr(c['circular'])} goes round (minimum-span decomposition).")
        for code in ["CIRCULAR_FLOW"] + c["codes"]:
            for m in members:
                if m in P["parties"] and P["parties"][m]["kind"] == "ENTITY":
                    hits.append({"detector": "D10", "code": code, "object_type": "party", "object_id": m, "severity": 4,
                                 "impact_paise": c["circular"], "reason": reason, "evidence": ev})
        for x in c["edges"]:
            if x["id"] and x["kind"] == "SALE":
                hits.append({"detector": "D10", "code": c["codes"][0], "object_type": "invoice", "object_id": x["doc_id"],
                             "severity": 4, "impact_paise": c["circular"], "reason": reason, "evidence": ev})
    seen, out = set(), []
    for h in hits:
        k = (h["code"], h["object_type"], h["object_id"])
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out


def _snapshot(run_id, inv_scores, parties, company, only_changed=False):
    at = config.now()
    rows = [(run_id, at, "INVOICE", iid, s["A"] * 1000, s["E"] * 1000, s["R"] * 1000, round(s["C"] * 1000), s["band"],
             json.dumps(s["reasons"])) for iid, s in inv_scores.items()]
    rows += [(run_id, at, "PARTY", pid, None, p["E"] * 1000, None, round(p["C"] * 1000), p["band"],
              json.dumps({"reasons": p["reasons"], "terms": p["terms"], "circular_paise": p["circular_paise"]}))
             for pid, p in parties.items() if p["E"] > 0 or not only_changed]
    if company is not None:
        rows.append((run_id, at, "COMPANY", "SELF", None, None, None, None, company["band"], json.dumps(company)))
    with db.borrow("audit", "system") as a, db.tx(a):
        a.executemany("INSERT OR IGNORE INTO risk_snapshots(run_id, at, object_type, object_id, A, E, R, C, band, reasons_json)"
                      " VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return rows


def _view(P, tx, identity, kinds, cycles, inv_scores, parties, company):
    nodes = [{"id": "SELF", "type": "self", "label": config.ENTITY_NAME, "E": None, "C": None, "band": company["band"]}]
    for pid, p in parties.items():
        if p["E"] > 0 or pid in identity:
            nodes.append({"id": pid, "type": "person" if P["parties"][pid]["kind"] == "PERSON" else "party",
                          "label": P["parties"][pid]["name"], "E": p["E"], "C": p["C"], "band": p["band"],
                          "reasons": p["reasons"], "terms": p["terms"]})
    for iid, s in sorted(inv_scores.items(), key=lambda kv: -kv[1]["R"])[:300]:
        nodes.append({"id": iid, "type": "invoice", "label": P["invoices"][iid]["invoice_no"], "R": s["R"], "C": s["C"],
                      "band": s["band"], "reasons": s["reasons"], "party": P["invoices"][iid]["party_id"]})
    agg = defaultdict(lambda: {"amount_paise": 0, "count": 0, "ts": ""})
    for x in tx:
        k = (x["a"], x["b"], x["kind"])
        agg[k]["amount_paise"] += x["amount"]
        agg[k]["count"] += 1
        agg[k]["ts"] = max(agg[k]["ts"], x["ts"])
    edges = [{"a": a, "b": b, "kind": k, **v} for (a, b, k), v in agg.items()]
    seen = set()
    for a, ns in identity.items():
        for b in ns:
            if frozenset((a, b)) not in seen:
                seen.add(frozenset((a, b)))
                edges.append({"a": a, "b": b, "kind": kinds.get(frozenset((a, b)), "IDENTITY"), "amount_paise": None,
                              "ts": None, "observed": False})
    cyc = [{"members": c["members"], "circular_paise": c["circular"], "span_days": c["span_days"], "flow": c["flow"],
            "codes": c["codes"], "flagged": c["flagged"], "residuals": c["residuals"]} for c in cycles]
    return {"nodes": nodes, "edges": edges, "cycles": cyc, "company": company}


def company_band(engagement_id):
    """The latest stored company flag (cheap; get_engagement_status reads this)."""
    with db.borrow("audit", "system") as a:
        r = a.execute("SELECT reasons_json, at FROM risk_snapshots WHERE object_type = 'COMPANY' ORDER BY rowid DESC LIMIT 1"
                      ).fetchone()
    return {**json.loads(r[0]), "as_of": r[1]} if r else None


def _affected_parties(e, doc_type, doc_id):
    q = {"invoice": "SELECT party_id FROM invoices WHERE id = ?", "credit_note": "SELECT party_id FROM credit_notes WHERE id = ?",
         "movement": "SELECT party_id FROM movements WHERE id = ?", "settlement": "SELECT party_id FROM settlements WHERE id = ?",
         "party": "SELECT id FROM parties WHERE id = ?", "sales_order": "SELECT party_id FROM sales_orders WHERE id = ?",
         "purchase_bill": "SELECT vendor_id FROM purchase_bills WHERE id = ?"}
    if doc_type == "journal":
        r = e.execute("SELECT source_type, source_id FROM journals WHERE no = ?", (doc_id,)).fetchone()
        if r and r[0] in ("invoice", "credit_note"):
            return _affected_parties(e, r[0], r[1])
        return []
    if doc_type not in q:
        return []
    return [r[0] for r in e.execute(q[doc_type], (doc_id,)) if r[0]]


def on_event(doc_type, doc_id, erp_seq):
    """Per-document update after an ERP commit (05 §19.6): re-run the per-document detectors (D3, D4, D6, D7, D9,
    D13) for the touched customer's documents, recompute A/R for its invoices and E for the party, and append a
    snapshot per changed object (run 'EV-<erp_seq>'). Neighbours' E come from their latest stored snapshot only.
    A crossing into HIGH emits RISK_ESCALATED. No engagement yet (e.g. while seeding) = nothing to do."""
    from app import analytics, notify
    with db.borrow("audit", "system") as a:
        eng = a.execute("SELECT * FROM engagements WHERE id = ?", (config.ENGAGEMENT_ID,)).fetchone()
        if eng is None or eng["status"] == "SIGNED_OFF":
            return []
        eng = dict(eng)
        prev_e = _latest_e(a)
        prev = {(r[0], r[1]): r[2] for r in a.execute(
            "SELECT object_type, object_id, band FROM risk_snapshots WHERE rowid IN (SELECT MAX(rowid) FROM risk_snapshots"
            " GROUP BY object_type, object_id)")}
    with db.borrow("erp", "system") as e, db.borrow("ext", "system") as x:
        parties = _affected_parties(e, doc_type, doc_id)
        if not parties:
            return []
        P = analytics.load_population(e, x, party_ids=parties, period_end=eng["period_end"])
        pm, _trivial, last_window = _context(eng, e)
        _tx, identity, kinds = build_edges(P, e)
    hits = []
    for fn in (analytics.d3, analytics.d6, analytics.d13):
        hits += fn(P, eng)
    hits += analytics.d4(P, eng, None) + analytics.d7(P, eng) + analytics.d9(P, eng)
    objs = {("invoice", i) for i in P["invoices"]} | {("credit_note", c) for c in P["cns"]} | \
           {("journal", str(j)) for j, jr in P["journals"].items() if jr["source_type"] in ("invoice", "credit_note")}
    hits = [h for h in hits if (h["object_type"], h["object_id"]) in objs]
    with db.borrow("audit", "system") as a, db.tx(a):
        for ot, oid in objs:
            a.execute("DELETE FROM risk_hits WHERE engagement_id = ? AND object_type = ? AND object_id = ? AND detector IN"
                      " ('D3','D4','D6','D7','D9','D13')", (eng["id"], ot, oid))
        at = config.now()
        a.executemany("INSERT INTO risk_hits(engagement_id, analytics_run, detector, code, object_type, object_id, severity,"
                      " impact_paise, reason, evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      [(eng["id"], f"EV-{erp_seq}", h["detector"], h["code"], h["object_type"], h["object_id"], h["severity"],
                        h["impact_paise"], h["reason"], json.dumps(h["evidence"], default=str), at) for h in hits])
    with db.borrow("audit", "system") as a:
        _all, by_obj = _hits(a, eng["id"])
        circular = {r[0]: (json.loads(r[1] or "{}") or {}).get("circular_paise", 0) for r in a.execute(
            "SELECT object_id, reasons_json FROM risk_snapshots WHERE object_type = 'PARTY' AND rowid IN"
            " (SELECT MAX(rowid) FROM risk_snapshots WHERE object_type = 'PARTY' GROUP BY object_id)")}
    inv_scores, party_scores = score(P, by_obj, [], eng, pm, prev_e, _rp_edges(identity, kinds), last_window,
                                     circular=circular)       # cycles come from the last full build
    party_scores = {p: s for p, s in party_scores.items() if p in parties}
    changed_inv = {i: s for i, s in inv_scores.items() if prev.get(("INVOICE", i)) != s["band"] or
                   ("INVOICE", i) not in prev}
    changed_party = {p: s for p, s in party_scores.items() if prev.get(("PARTY", p)) != s["band"] or s["E"] > 0}
    if not changed_inv and not changed_party:
        return []
    rows = _snapshot(f"EV-{erp_seq}", changed_inv, changed_party, None, only_changed=True)
    for iid, s in changed_inv.items():
        if s["band"] == "HIGH" and prev.get(("INVOICE", iid)) != "HIGH":
            notify.emit("RISK_ESCALATED", {"object_type": "INVOICE", "object_id": iid, "R": s["R"], "reasons": s["reasons"],
                                           "erp_seq": erp_seq}, eng["id"])
    return [{"object_type": r[2], "object_id": r[3], "band": r[8]} for r in rows]
