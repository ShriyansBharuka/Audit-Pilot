"""Related parties: D1 identifier graph + GSTIN validity, D2 RP windows / statuses (05 D1, D2).

Pure core over plain dicts (parties and party_links as in 03, RP-list rows as mapped_json, invoices with a
control date); run_d1_d2 / rp_status feed it from the DBs once db.py lands. RP status is a sampling weight and a
Sheet 1 column, never a finding by itself (05 D2). Reasons cite party ids, link ids, regex-validated PANs and the
last 4 digits of accounts only; names, emails and addresses are client text and stay in evidence.
"""
import re
from collections import defaultdict, deque

# ---------------------------------------------------------------- GSTIN validity [REG]

_C36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_PAN = re.compile(r"[A-Z]{5}\d{4}[A-Z]")

def gstin_ok(g):  # 05 D1, verbatim
    if not re.fullmatch(r'\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]', g or ''): return False
    t = 0
    for i, ch in enumerate(g[:14]):
        p = _C36.index(ch) * (2 if i % 2 else 1); t += p // 36 + p % 36
    return _C36[(36 - t % 36) % 36] == g[14]


def _g(s):
    return re.sub(r"\s", "", str(s or "")).upper()


def pan_of(p):
    """party.pan, else the PAN embedded in the GSTIN (03 #1)."""
    pan = _g(p.get("pan"))
    if _PAN.fullmatch(pan):
        return pan
    g = _g(p.get("gstin"))
    return g[2:12] if gstin_ok(g) else None


def _state(s):
    s = str(s if s is not None else "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(2) if s.isdigit() else s


SEVERITY = {"UNDISCLOSED_RP": 5, "INVALID_GSTIN": 4, "PAN_GSTIN_MISMATCH": 4, "GSTIN_STATE_MISMATCH": 3,
            "RP_PERIOD_MISSTATED": 4, "CUSTOMER_CLUSTER": 2, "DECLARED_UNSUPPORTED": 1,
            "SERVICE_PROVIDER_IDENTIFIER": 1}
STANDARDS = "SA 550; Ind AS 24 paras 9, 18 / AS 18; Companies Act 2013 s.2(76), s.184 (MBP-1), s.188"


def _hit(detector, code, otype, oid, reason, evidence, impact=0):
    return {"detector": detector, "code": code, "object_type": otype, "object_id": str(oid),
            "severity": SEVERITY[code], "impact_paise": impact, "reason": reason, "evidence": evidence}


def gstin_hits_parties(parties):
    out = []
    for p in parties:
        g = _g(p.get("gstin"))
        if not g:
            continue
        ev = {"party_id": p["id"], "gstin": p.get("gstin"), "pan": p.get("pan"), "state_code": p.get("state_code")}
        if not gstin_ok(g):
            out.append(_hit("D1", "INVALID_GSTIN", "party", p["id"],
                            f"Party {p['id']} has a GSTIN that fails the format or check-digit test.", ev))
            continue
        pan = _g(p.get("pan"))
        if pan and pan != g[2:12]:
            out.append(_hit("D1", "PAN_GSTIN_MISMATCH", "party", p["id"],
                            f"Party {p['id']}: the PAN embedded in its GSTIN ({g[2:12]}) is not the PAN on the master"
                            f"{f' ({pan})' if _PAN.fullmatch(pan) else ''}.", ev))
        if p.get("state_code") not in (None, "") and _state(p["state_code"]) != g[:2]:
            out.append(_hit("D1", "GSTIN_STATE_MISMATCH", "party", p["id"],
                            f"Party {p['id']}: GSTIN state {g[:2]} differs from the master's state code.", ev))
    return out


def gstin_hits_register(mapped):
    """[REG] checks on register rows (register.map_row output): works on a judge's Fig. 1 file alone."""
    out = []
    for m in mapped:
        g = _g(m.get("gstin"))
        if m.get("kind") != "ROW" or not g:
            continue
        r = m["row_no"]
        ev = {"register_row": r, "gstin": m.get("gstin"), "state_code": m.get("state_code")}
        if not gstin_ok(g):
            out.append(_hit("D1", "INVALID_GSTIN", "register_row", r,
                            f"Register row {r}: the GSTIN fails the format or check-digit test.", ev))
        elif m.get("state_code") not in (None, "") and _state(m["state_code"]) != g[:2]:
            out.append(_hit("D1", "GSTIN_STATE_MISMATCH", "register_row", r,
                            f"Register row {r}: the State Code column does not match GSTIN state {g[:2]}.", ev))
    return out

# ---------------------------------------------------------------- identifier keys

_BOILER = {"ROAD", "RD", "NEAR", "OPP", "OPPOSITE", "MIDC", "INDUSTRIAL", "AREA", "ESTATE", "FLOOR", "PLOT", "NO",
           "GALA", "UNIT", "SHED", "FLAT", "BLDG", "BUILDING", "LANE", "STREET", "ST", "MARG", "OFF", "BEHIND", "THE",
           "AND", "SURVEY", "SY", "GAT", "SECTOR", "PHASE", "FL", "GROUND", "FIRST", "SECOND", "SHOP", "OFFICE"}

def address_key(address, pincode):
    """WEAK key (05 D1): pincode + first house/plot/flat number + first street token after boilerplate."""
    pin = re.sub(r"\D", "", str(pincode or ""))
    toks = re.findall(r"[A-Z0-9]+", str(address or "").upper())
    house = next((t for t in toks if any(ch.isdigit() for ch in t) and t != pin), None)
    after = toks[toks.index(house) + 1:] if house else toks
    street = next((t for t in after if t.isalpha() and t not in _BOILER and len(t) > 1), None)
    return f"{pin}|{house.lstrip('0')}|{street}" if pin and house and street else None


def phone_key(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d[-10:] if len(d) >= 10 else None


def bank_key(acct, ifsc):
    d = re.sub(r"\D", "", str(acct or "")).lstrip("0")
    return f"{_g(ifsc)[:4]}:{d}" if len(d) >= 6 else None


def keys(p, self_domain=None):
    """[(kind, strength, key)] for one party; SELF's own domain on another party's email is MEDIUM (05 D1)."""
    out = []
    pan = pan_of(p)
    if pan:
        out.append(("PAN", "STRONG", pan))
    g = _g(p.get("gstin"))
    if gstin_ok(g) and g[2:12] != pan:                       # GSTIN embeds a different PAN (05 D1, plant A2)
        out.append(("PAN", "STRONG", g[2:12]))
    b = bank_key(p.get("bank_account"), p.get("ifsc"))
    if b:
        out.append(("BANK", "STRONG", b))
    ph = phone_key(p.get("phone"))
    if ph:
        out.append(("PHONE", "MEDIUM", ph))
    em = str(p.get("email") or "").strip().lower()
    if "@" in em:
        out.append(("EMAIL", "MEDIUM", em))
        if self_domain and em.split("@", 1)[1] == self_domain and p["id"] != "SELF":
            out.append(("SELF_DOMAIN", "MEDIUM", self_domain))
    if p["id"] == "SELF" and self_domain:
        out.append(("SELF_DOMAIN", "MEDIUM", self_domain))
    a = address_key(p.get("address"), p.get("pincode"))
    if a:
        out.append(("ADDRESS", "WEAK", a))
    return out

# ---------------------------------------------------------------- D1 graph

def _within(on, frm, to):
    return (not frm or frm <= on) and (not to or on <= to)


def _rp_list_party(row, by_pan, by_gstin, by_name):
    """The party an RP-list row names. Identifier matches first; a PAN/GSTIN shared by several parties (itself a
    plant, A1) is broken by name, so a planted customer can't absorb its director's declaration."""
    from app.register import name_key
    nk = name_key(row.get("name"))
    cands = by_pan.get(_g(row.get("pan")), []) + by_gstin.get(_g(row.get("gstin")), [])
    if cands:
        return next((pid for pid in cands if pid in by_name.get(nk, [])), cands[0])
    named = by_name.get(nk, [])
    return named[0] if nk and named else None


def analyse(parties, links, rp_rows, period_start, period_end, invoices=(), identifier_since=None):
    """D1 + D2 over the whole population.

    parties:  03 #1 rows. links: 03 #2 rows (truth with dates). rp_rows: the client's RP list (rp_list_rows
    mapped_json + row_no: name, pan?, gstin?, relation?, effective_from?, effective_to?).
    invoices: [{id, party_id, control_date, taxable_paise}] (control date from D3; invoice date until D3 exists).
    identifier_since: {(party_id, kind): 'YYYY-MM-DD'} from erp_log, when an identifier first appeared (B4).
    Returns {"hits": [...], "rp": {party_id: {"declared": window|None, "independent": window|None,
             "basis": str, "path": [...]}}}. A window is (from, to) with None = open."""
    from app.register import name_key
    identifier_since = identifier_since or {}
    by_id = {p["id"]: p for p in parties}
    self_p = by_id.get("SELF", {})
    self_domain = str(self_p.get("email") or "").split("@")[-1].lower() or None
    hits = gstin_hits_parties(parties)

    # 1. declared: RP-list rows matched to parties (by PAN, GSTIN, then normalised name)
    by_pan, by_gstin, by_name = defaultdict(list), defaultdict(list), defaultdict(list)
    for p in parties:
        if pan_of(p):
            by_pan[pan_of(p)].append(p["id"])
        if p.get("gstin"):
            by_gstin[_g(p["gstin"])].append(p["id"])
        by_name[name_key(p["name"])].append(p["id"])
    declared = {}
    for row in rp_rows:
        pid = _rp_list_party(row, by_pan, by_gstin, by_name)
        if pid:
            declared[pid] = (row.get("effective_from"), row.get("effective_to"), row["row_no"])

    # 2. independent truth: every party reachable from SELF through party_links; window = the path's overlap
    adj = defaultdict(list)
    for ln in links:
        adj[ln["from_party"]].append((ln["to_party"], ln))
        adj[ln["to_party"]].append((ln["from_party"], ln))
    core = {"SELF": {"window": (None, None), "path": []}}
    q = deque(["SELF"])
    while q:
        u = q.popleft()
        fu, tu = core[u]["window"]
        for v, ln in adj[u]:
            f = max(x for x in (fu, ln.get("effective_from")) if x) if (fu or ln.get("effective_from")) else None
            t = min(x for x in (tu, ln.get("effective_to")) if x) if (tu or ln.get("effective_to")) else None
            if f and t and f > t:
                continue
            cur = core.get(v)
            if cur is None or (f or "") < (cur["window"][0] or ""):
                core[v] = {"window": (f, t), "path": core[u]["path"] + [ln["id"]]}
                q.append(v)

    # 3. identifier edges, with the fan-out guard on MEDIUM/WEAK keys
    holders = defaultdict(set)
    kinds = {}
    for p in parties:
        for kind, strength, key in keys(p, self_domain):
            holders[(kind, key)].add(p["id"])
            kinds[(kind, key)] = strength
    for row in rp_rows:                                     # declared people/entities not in the master
        pid = f"RPL-{row['row_no']}"
        for kind, strength, key in keys({"id": pid, "pan": row.get("pan"), "gstin": row.get("gstin")}):
            holders[(kind, key)].add(pid)
            kinds[(kind, key)] = strength
    edges = defaultdict(lambda: defaultdict(set))           # edges[a][b] = {kind, ...}
    for (kind, key), ps in holders.items():
        if len(ps) < 2:
            continue
        if kinds[(kind, key)] != "STRONG" and kind != "SELF_DOMAIN" and len(ps) > 3:
            ids = sorted(ps)
            hits.append(_hit("D1", "SERVICE_PROVIDER_IDENTIFIER", "identifier", f"{kind}:{len(ids)}",
                             f"One {kind.lower()} is shared by {len(ids)} otherwise unrelated parties "
                             f"({', '.join(ids[:8])}); treated as a service provider's identifier, no link drawn.",
                             {"kind": kind, "party_ids": ids}))
            continue
        for a in ps:
            for b in ps:
                if a != b:
                    edges[a][b].add(kind)

    def kinds_strength(k):
        return "STRONG" if k in ("PAN", "BANK") else ("WEAK" if k == "ADDRESS" else "MEDIUM")

    def linked(kset):   # >= 1 STRONG, or >= 2 MEDIUM/WEAK of different kinds (05 D1)
        return any(kinds_strength(k) == "STRONG" for k in kset) or len(kset) >= 2

    rpl_window = {f"RPL-{r['row_no']}": (r.get("effective_from"), r.get("effective_to")) for r in rp_rows}
    rp_anchor = set(core) | set(declared) | set(rpl_window)
    customers = [p for p in parties if "CUSTOMER" in str(p.get("tags", "")).split(",")]
    inv_by_party = defaultdict(list)
    for inv in invoices:
        inv_by_party[inv["party_id"]].append(inv)
    rp = {}
    for c in customers:
        cid = c["id"]
        indep, basis, path = None, None, []
        if cid in core and cid != "SELF":
            indep, path = core[cid]["window"], core[cid]["path"]
            basis = f"link path {' > '.join(path)} (party_links)"
        best = None
        for other, kset in sorted(edges[cid].items()):
            if other not in rp_anchor or not linked(kset):
                continue
            w = (core[other]["window"] if other in core else rpl_window.get(other)
                 or (declared[other][:2] if other in declared else (None, None)))
            since = max((identifier_since.get((cid, k)) for k in kset if identifier_since.get((cid, k))), default=None)
            f = max(x for x in (w[0], since) if x) if (w[0] or since) else None
            if best is None or (f or "") < (best[0][0] or ""):
                best = ((f, w[1]), other, sorted(kset))
        if best and (indep is None or (best[0][0] or "") < (indep[0] or "")):
            indep, other, ks = best
            basis = _edge_basis(cid, other, ks, by_id, core)
            path = core.get(other, {}).get("path", [])
        dec = declared.get(cid)
        rp[cid] = {"declared": dec[:2] if dec else None, "declared_row": dec[2] if dec else None,
                   "independent": indep, "basis": basis, "path": path}
        if indep and not dec:
            gap = [i for i in inv_by_party[cid] if _within(i["control_date"], *indep)
                   and period_start <= i["control_date"] <= period_end]
            hits.append(_hit("D1", "UNDISCLOSED_RP", "party", cid,
                             f"Customer {cid} is not on the client's related-party list but is related: {basis}"
                             f"{f' from {indep[0]}' if indep[0] else ''}. {len(gap)} FY invoice(s) fall in the "
                             f"relationship window.",
                             {"party_id": cid, "window": indep, "path": path, "invoice_ids": [i["id"] for i in gap]},
                             sum(i["taxable_paise"] for i in gap)))

    # CUSTOMER_CLUSTER: customers sharing STRONG/MEDIUM keys among themselves, with no RP link (risk points only)
    cust_ids = {c["id"] for c in customers}
    seen = set()
    for c in customers:
        cid = c["id"]
        if rp[cid]["independent"] or rp[cid]["declared"]:
            continue
        mates = sorted(o for o, ks in edges[cid].items() if o in cust_ids and o != cid and not rp[o]["independent"]
                       and not rp[o]["declared"] and any(kinds_strength(k) != "WEAK" for k in ks))
        group = tuple(sorted([cid] + mates))
        if mates and group not in seen:
            seen.add(group)
            hits.append(_hit("D1", "CUSTOMER_CLUSTER", "party", cid,
                             f"Customers {', '.join(group)} share identifiers with each other but have no "
                             f"related-party link; possible common control (risk points only).",
                             {"party_ids": list(group)}))

    # D2: declared vs independent windows
    for pid, (f, t, row_no) in declared.items():
        r = rp.setdefault(pid, {"declared": (f, t), "declared_row": row_no, "independent": None,
                                "basis": None, "path": []})
        ind = r["independent"] or (core[pid]["window"] if pid in core and pid != "SELF" else None)
        r["independent"] = ind
        if ind is None:
            hits.append(_hit("D2", "DECLARED_UNSUPPORTED", "rp_list_row", row_no,
                             f"RP-list row {row_no} matches party {pid}, but no link or shared identifier in the "
                             f"system supports the relationship (information only).", {"party_id": pid}))
            continue
        if _clip(ind, period_start, period_end) != _clip((f, t), period_start, period_end):
            gap = [i for i in inv_by_party[pid] if period_start <= i["control_date"] <= period_end
                   and _within(i["control_date"], *ind) != _within(i["control_date"], f, t)]
            hits.append(_hit("D2", "RP_PERIOD_MISSTATED", "party", pid,
                             f"Party {pid}: the client's list (row {row_no}) dates the relationship "
                             f"{f or 'open'} to {t or 'open'}, but the system shows {ind[0] or 'open'} to "
                             f"{ind[1] or 'open'} ({r['basis'] or 'party_links'}). {len(gap)} FY invoice(s) fall "
                             f"in the gap.", {"party_id": pid, "declared": (f, t), "independent": ind,
                                              "invoice_ids": [i["id"] for i in gap]},
                             sum(i["taxable_paise"] for i in gap)))
    return {"hits": hits, "rp": rp}


def _clip(w, lo, hi):
    f, t = w
    return (max(f or lo, lo), min(t or hi, hi))


def _edge_basis(cid, other, ks, by_id, core):
    p, o = by_id.get(cid, {}), by_id.get(other, {})
    parts = []
    for k in ks:
        if k == "PAN":
            mine = {key for kind, _s, key in keys(p) if kind == "PAN"}
            shared = sorted(mine & {key for kind, _s, key in keys(o) if kind == "PAN"}) if o else sorted(mine)
            pan = shared[0] if shared else pan_of(p)
            via = "GSTIN embeds" if gstin_ok(_g(p.get("gstin"))) and _g(p.get("gstin"))[2:12] == pan else "has"
            parts.append(f"{via} PAN {pan} = PAN of {other}")
        elif k == "BANK":
            last4 = re.sub(r"\D", "", str(p.get("bank_account") or ""))[-4:]
            parts.append(f"same bank account (ending {last4}) as {other}")
        elif k == "PHONE":
            parts.append(f"same phone (ending {phone_key(p.get('phone'))[-4:]}) as {other}")
        elif k == "EMAIL":
            parts.append(f"same email address as {other}")
        elif k == "SELF_DOMAIN":
            parts.append("an email on the company's own domain")
        elif k == "ADDRESS":
            parts.append(f"same address key as {other}")
    rel = core.get(other, {}).get("path")
    tail = f" ({other} is related via {' > '.join(rel)})" if rel else (" (on the client's RP list)" if other.startswith("RPL-")
                                                                        else "")
    return f"customer {cid} " + " and ".join(parts) + tail


def status_on(r, on):
    """(status, basis) for one party on a control date: DECLARED_RP | UNDISCLOSED_RP | NRP_BEFORE_RELATIONSHIP |
    NRP_AFTER_CESSATION | NRP (05 D2; Sheet 1 RP_Status, sampling RP stratum)."""
    if not r:
        return "NRP", ""
    dec, ind = r.get("declared"), r.get("independent")
    if dec and _within(on, *dec):
        return "DECLARED_RP", f"RP list row {r.get('declared_row')}"
    if ind and _within(on, *ind):
        return "UNDISCLOSED_RP", f"from {ind[0] or 'before the period'}: {r.get('basis') or ''}".strip()
    w = ind or dec
    if w and w[0] and on < w[0]:
        return "NRP_BEFORE_RELATIONSHIP", f"relationship starts {w[0]}"
    if w and w[1] and on > w[1]:
        return "NRP_AFTER_CESSATION", f"relationship ended {w[1]}"
    return "NRP", ""


def run_d1_d2(engagement_id):
    raise NotImplementedError("related_parties.run_d1_d2: waiting for app.db (SH-2); pure core is analyse()")


def rp_status(party_id, on_date):
    raise NotImplementedError("related_parties.rp_status: waiting for app.db (SH-2); pure core is status_on()")
