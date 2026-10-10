"""Sample selection (05 §15; SA 530): Sales TOD strata, Cut-off TOD, Credit Note TOD, and reproduce.

Analytics find (100% of the population); samples prove what only documents can. The seed is random and recorded
(unpredictable beforehand, reproducible afterwards; SA 240), the population is frozen into sample_runs, and every
selection is a pure function of (population, seed, params) using only rng.random(), so reproduce() re-runs it
exactly. The first selection starts testing: TESTING_START anchor, testing_started_seq, per-sample bundle snapshots,
and evidence requests to the client (opaque refs, no reasons).
"""
import hashlib
import json
import random
import secrets
from collections import Counter, defaultdict
from datetime import date, timedelta

from app import chain, config, db, money

ALGO = "v1"
KINDS = {"sales_tod": "SALES_TOD", "cutoff": "CUTOFF_TOD", "credit_note": "CN_TOD"}


def pps(items, k, rng):  # items: [(invoice_id, weight)] sorted by invoice_id; move items with w >= step to HIGH_VALUE first
    step = sum(w for _, w in items) / k
    start, picks, cum, j = rng.random() * step, [], 0, 0
    for id_, w in items:
        cum += w
        while j < k and start + j * step < cum:
            if not picks or picks[-1] != id_: picks.append(id_)
            j += 1
    return picks

# ---------------------------------------------------------------- populations (frozen into sample_runs)

def _quarter(d):
    m = int(d[5:7])
    return f"Q{((m - 4) % 12) // 3 + 1}"


def _hits_by_invoice(a, eid):
    """{invoice_id: [(detector, code, severity, impact)]} incl. D0 hits on register rows paired to an invoice."""
    out = defaultdict(list)
    for r in a.execute("SELECT detector, code, object_type, object_id, severity, impact_paise, evidence_json FROM risk_hits"
                       " WHERE engagement_id = ?", (eid,)):
        iid = r["object_id"] if r["object_type"] == "invoice" else None
        if r["object_type"] == "register_row":
            ev = json.loads(r["evidence_json"] or "{}") or {}
            iid = (ev.get("sor") or {}).get("id")
        if iid:
            out[iid].append((r["detector"], r["code"], r["severity"], r["impact_paise"]))
    return out


def _sales_population(eng, a, e):
    """Register rows paired to SoR invoices (or every FY invoice when no register is uploaded yet)."""
    from app import register, related_parties
    rows = {}
    if eng["register_submission_id"]:
        for r in a.execute("SELECT row_no, mapped_json FROM register_rows WHERE submission_id = ?",
                           (eng["register_submission_id"],)):
            m = json.loads(r[1])
            if m.get("kind") == "ROW" and not m.get("is_cn"):
                rows.setdefault(m["doc_key"], r[0])
    hits = _hits_by_invoice(a, eng["id"])
    rp = related_parties.rp_map(eng["id"])
    pop = []
    for r in e.execute("SELECT i.id, i.invoice_no, i.invoice_date, i.party_id, i.series, COALESCE(SUM(l.taxable_paise), 0)"
                       " FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id = i.id WHERE i.status = 'ISSUED'"
                       " AND i.invoice_date BETWEEN ? AND ? GROUP BY i.id ORDER BY i.id",
                       (eng["period_start"], eng["period_end"])):
        key = register.doc_key(r[1])
        if rows and key not in rows:
            continue                                  # not in the register: a D0 hit, not a sampling unit
        h = hits.get(r[0], [])
        status, _b = related_parties.status_on(rp.get(r[3]), r[2])
        pop.append({"id": r[0], "no": r[1], "date": r[2], "party": r[3], "unit": r[4], "taxable": r[5],
                    "row": rows.get(key), "rp": status in ("DECLARED_RP", "UNDISCLOSED_RP"), "rp_status": status,
                    "points": sum(s for _d, _c, s, _i in h), "max_sev": max((s for _d, _c, s, _i in h), default=0),
                    "impact": max((i for _d, _c, _s, i in h), default=0),
                    "codes": sorted({c for _d, c, s, _i in h if s >= 4})})
    return pop


def _cutoff_population(eng, a, e):
    """The last 10 invoices on/before the period end and the first 15 after it (whatever their dates), plus every
    invoice within 30 days of the period end (for the D3/D13 ANALYTICS additions)."""
    hits = _hits_by_invoice(a, eng["id"])
    end = eng["period_end"]
    lo = (date.fromisoformat(end) - timedelta(days=30)).isoformat()
    hi = (date.fromisoformat(end) + timedelta(days=30)).isoformat()
    q = ("SELECT i.id, i.invoice_no, i.invoice_date, i.party_id, i.series, COALESCE(SUM(l.taxable_paise), 0)"
         " FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id = i.id WHERE i.status = 'ISSUED' AND {} GROUP BY i.id"
         " ORDER BY i.invoice_date {d}, i.invoice_no {d} LIMIT {n}")
    rows = {}
    for cond, args, d, n in (("i.invoice_date <= ?", (end,), "DESC", 10), ("i.invoice_date > ?", (end,), "ASC", 15),
                             ("i.invoice_date BETWEEN ? AND ?", (lo, hi), "ASC", -1)):
        for r in e.execute(q.format(cond, d=d, n=n), args):
            rows[r[0]] = r
    pop = []
    for r in sorted(rows.values(), key=lambda r: (r[2], r[1])):
        h = [c for det, c, _s, _i in hits.get(r[0], []) if det in ("D3", "D13")]
        pop.append({"id": r[0], "no": r[1], "date": r[2], "party": r[3], "unit": r[4], "taxable": r[5], "codes": sorted(set(h))})
    return pop


def _cn_population(eng, a, e):
    from app import related_parties
    hits = defaultdict(list)
    for r in a.execute("SELECT object_id, code FROM risk_hits WHERE engagement_id = ? AND detector = 'D9'"
                       " AND object_type = 'credit_note'", (eng["id"],)):
        hits[r[0]].append(r[1])
    rp = related_parties.rp_map(eng["id"])
    pop = []
    for r in e.execute("SELECT n.id, n.cn_no, n.cn_date, n.party_id, COALESCE(SUM(l.taxable_paise), 0) FROM credit_notes n"
                       " LEFT JOIN cn_lines l ON l.cn_id = n.id WHERE n.status = 'ISSUED' AND n.cn_date >= ?"
                       " GROUP BY n.id ORDER BY n.id", (eng["period_start"],)):
        status, _b = related_parties.status_on(rp.get(r[3]), r[2])
        pop.append({"id": r[0], "no": r[1], "date": r[2], "party": r[3], "taxable": r[4],
                    "rp": status in ("DECLARED_RP", "UNDISCLOSED_RP"), "codes": sorted(set(hits.get(r[0], [])))})
    return pop

# ---------------------------------------------------------------- selections (pure: population + seed + params)

def _inr(p):
    return money.fmt_inr(p)


def select_sales(pop, size, seed, pm):
    """05 §15 strata: KEY (severity >= 4 hits, by severity x impact, cap n/2) -> HIGH_VALUE (>= PM or >= the PPS
    interval) -> RP (>= 3, undisclosed first) -> REPRESENTATIVE (systematic PPS on taxable x (1 + risk points), <= 3 per
    customer, coverage of both units and every quarter). -> [{id, stratum, reason}]"""
    rng = random.Random(int(seed))
    pop = sorted(pop, key=lambda p: p["id"])
    picks, taken, per_cust = [], set(), Counter()

    def take(p, stratum, reason):
        picks.append({"id": p["id"], "no": p["no"], "row": p.get("row"), "stratum": stratum, "reason": reason,
                      "points": p.get("points", 0)})
        taken.add(p["id"])
        per_cust[p["party"]] += 1

    key = sorted([p for p in pop if p["max_sev"] >= 4], key=lambda p: (-p["max_sev"] * max(p["impact"], 1), p["id"]))
    for p in key[:size // 2]:
        take(p, "KEY", f"KEY: {' + '.join(p['codes'][:3])}; taxable {_inr(p['taxable'])}")
    rest = [p for p in pop if p["id"] not in taken]
    budget = size - len(picks)
    rp_min = min(3, sum(1 for p in rest if p["rp"]))
    step = sum(p["taxable"] * (1 + p["points"]) for p in rest) / max(1, budget - rp_min) if rest else 0
    high = sorted([p for p in rest if p["taxable"] >= pm or (step and p["taxable"] * (1 + p["points"]) >= step)],
                  key=lambda p: (-p["taxable"], p["id"]))
    for p in high[:max(0, (budget - rp_min) // 3)]:
        take(p, "HIGH_VALUE", f"HIGH_VALUE: taxable {_inr(p['taxable'])} >= "
                              f"{'performance materiality' if p['taxable'] >= pm else 'the PPS interval'} "
                              f"({_inr(int(pm if p['taxable'] >= pm else step))})")
    is_rp = {p["id"] for p in pop if p["rp"]}
    have_rp = sum(1 for x in picks if x["id"] in is_rp)
    undisclosed = [p for p in pop if p["rp_status"] == "UNDISCLOSED_RP" and p["id"] not in taken]
    declared = [p for p in pop if p["rp_status"] == "DECLARED_RP" and p["id"] not in taken]
    while have_rp < 3 and (undisclosed or declared):            # undisclosed first, then a random declared one
        p = undisclosed.pop(0) if undisclosed else declared.pop(int(rng.random() * len(declared)))
        take(p, "RP", f"RP: {p['rp_status'].replace('_', ' ').lower()} customer {p['party']}; taxable {_inr(p['taxable'])}")
        have_rp += 1
    k = size - len(picks)
    cand = [(p["id"], p["taxable"] * (1 + p["points"])) for p in pop if p["id"] not in taken and p["taxable"] > 0]
    if k > 0 and cand:
        by_id = {p["id"]: p for p in pop}
        interval = sum(w for _, w in cand) / k
        order = [c[0] for c in cand]
        drawn = pps(cand, k, rng)
        n_draw = 0
        for pid in drawn:
            # <= 3 per customer: overflow moves to the next eligible item in population order
            j = order.index(pid)
            while j < len(order) and (order[j] in taken or per_cust[by_id[order[j]]["party"]] >= 3):
                j += 1
            if j >= len(order):
                continue
            p = by_id[order[j]]
            n_draw += 1
            take(p, "REPRESENTATIVE", f"REPRESENTATIVE: PPS draw {n_draw} of {k} (interval {_inr(int(interval))})"
                                      f"{'; moved from an over-sampled customer' if order[j] != pid else ''}")
        # coverage: every unit and every quarter appears at least once (swap the last representative picks)
        reps = [x for x in picks if x["stratum"] == "REPRESENTATIVE"]
        for dim, values in (("unit", sorted({p["unit"] for p in pop})), ("q", sorted({_quarter(p["date"]) for p in pop}))):
            got = {(by_id[x["id"]]["unit"] if dim == "unit" else _quarter(by_id[x["id"]]["date"])) for x in picks}
            for v in values:
                if v in got or not reps:
                    continue
                pool = [p for p in pop if p["id"] not in taken and per_cust[p["party"]] < 3
                        and (p["unit"] if dim == "unit" else _quarter(p["date"])) == v]
                if not pool:
                    continue
                p = pool[int(rng.random() * len(pool))]
                old = reps.pop()
                picks.remove(old)
                taken.discard(old["id"])
                per_cust[by_id[old["id"]]["party"]] -= 1
                take(p, "REPRESENTATIVE", f"REPRESENTATIVE: coverage pick for {'unit' if dim == 'unit' else 'quarter'} {v}")
    return picks


def select_cutoff(pop, end):
    """Last 10 invoices on/before the period end, first 15 after (ties by number), + every D3/D13 hit within 30 days."""
    before = [p for p in pop if p["date"] <= end][-10:]
    after = [p for p in pop if p["date"] > end][:15]
    picks, seen = [], set()
    for p in before:
        picks.append({"id": p["id"], "no": p["no"], "stratum": "CUTOFF_BEFORE",
                      "reason": f"CUTOFF_BEFORE: among the last 10 invoices up to the period end ({p['date']})"})
        seen.add(p["id"])
    for p in after:
        picks.append({"id": p["id"], "no": p["no"], "stratum": "CUTOFF_AFTER",
                      "reason": f"CUTOFF_AFTER: among the first 15 invoices after the period end ({p['date']})"})
        seen.add(p["id"])
    for p in pop:
        if p["codes"] and p["id"] not in seen:
            picks.append({"id": p["id"], "no": p["no"], "stratum": "ANALYTICS",
                          "reason": f"ANALYTICS: {' + '.join(p['codes'][:3])} within 30 days of the period end"})
    return picks


def select_cn(pop, end, pm, today):
    """Every CN after the period end (to the run date), CNs >= PM/10 in the last 15 days, CNs to RPs, every D9 hit."""
    picks = []
    last15 = (date.fromisoformat(end) - timedelta(days=15)).isoformat()
    for p in pop:
        if end < p["date"] <= today:
            s, r = "CN_POST_PERIOD", f"CN_POST_PERIOD: dated {p['date']}, after the period end (SA 560, Ind AS 10)"
        elif last15 <= p["date"] <= end and p["taxable"] >= pm / 10:
            s, r = "CN_LARGE", f"CN_LARGE: {_inr(p['taxable'])} in the last 15 days of the period"
        elif p["rp"]:
            s, r = "RP", "RP: credit note to a related party"
        elif p["codes"]:
            s, r = "ANALYTICS", f"ANALYTICS: {' + '.join(p['codes'][:3])}"
        else:
            continue
        picks.append({"id": p["id"], "no": p["no"], "stratum": s, "reason": r})
    return picks


def _run(kind, pop, seed, params):
    if kind == "SALES_TOD":
        return select_sales(pop, params["size"], seed, params["pm"])
    if kind == "CUTOFF_TOD":
        return select_cutoff(pop, params["period_end"])
    return select_cn(pop, params["period_end"], params["pm"], params["run_date"])

# ---------------------------------------------------------------- select / reproduce

_DOCS = {"SALES_TOD": ("INVOICE", "EWAY_BILL", "LR", "POD"), "CUTOFF_TOD": ("INVOICE", "LR", "POD", "EWAY_BILL"),
         "CN_TOD": ("CREDIT_NOTE", "RETURN_PROOF", "INVOICE")}


def performance_materiality(eng, e):
    """PM (SA 320): the engagement's figure, else 75% of OM, OM = 0.5% of the period's invoiced revenue."""
    if eng["performance_materiality_paise"]:
        return eng["performance_materiality_paise"]
    revenue = e.execute("SELECT COALESCE(SUM(l.taxable_paise), 0) FROM invoices i JOIN invoice_lines l ON l.invoice_id ="
                        " i.id WHERE i.status = 'ISSUED' AND i.invoice_date BETWEEN ? AND ?",
                        (eng["period_start"], eng["period_end"])).fetchone()[0]
    om = eng["materiality_paise"] or revenue * config.OVERALL_MATERIALITY_BP_OF_REVENUE // 10000
    return max(1, om * config.PERFORMANCE_MATERIALITY_BP_OF_OM // 10000)


def select(engagement_id, kind, size=30, seed=None, actor=""):
    """kind in sales_tod | cutoff | credit_note. First call = testing start (anchor + snapshots + requests).
    -> {run_id, kind, seed, size, population, items: [{sample_no, doc_type, doc_id, stratum, reason}], requests_sent}."""
    from app import evidence, intake, notify, trail
    if kind not in KINDS:
        raise ValueError(f"INVALID_ARGUMENT: kind must be one of {', '.join(KINDS)}")
    run_kind = KINDS[kind]
    if run_kind == "SALES_TOD" and not (25 <= int(size) <= 35):
        raise ValueError("INVALID_ARGUMENT: a Sales TOD selects 25 to 35 samples (PS); default 30")
    seed = str(int(seed)) if seed not in (None, "") else str(secrets.randbits(64))
    intake.ensure_engagement()
    with db.borrow("audit", "system") as a, db.borrow("erp", "system") as e:
        eng = dict(a.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone())
        head_seq, _h = chain.head(e, "erp_log")
        pop = {"SALES_TOD": _sales_population, "CUTOFF_TOD": _cutoff_population, "CN_TOD": _cn_population}[run_kind](eng, a, e)
        pm = performance_materiality(eng, e)
    if not pop:
        raise ValueError("PRECONDITION_FAILED: the population for this selection is empty (no invoices / credit notes in "
                         "range); check get_engagement_status")
    params = {"size": int(size), "pm": pm, "period_end": eng["period_end"], "run_date": config.today(), "kind": run_kind}
    picks = _run(run_kind, pop, seed, params)
    pop_json = json.dumps(pop, sort_keys=True, separators=(",", ":"))
    # first selection starts testing
    if eng["testing_started_seq"] is None:
        with db.borrow("audit", "system") as a, db.tx(a):
            a.execute("UPDATE engagements SET testing_started_seq = ?, testing_started_at = ?, status = 'TESTING'"
                      " WHERE id = ?", (head_seq, config.now(), engagement_id))
        trail.anchor(engagement_id, "TESTING_START")
    with db.borrow("audit", "system") as a, db.tx(a):
        n = a.execute("SELECT count(*) FROM sample_runs WHERE engagement_id = ?", (engagement_id,)).fetchone()[0] + 1
        run_id = f"RUN-{run_kind}-{n:02d}"
        a.execute("INSERT INTO sample_runs(id, engagement_id, kind, seed, size, params_json, as_of_seq, population_json,"
                  " population_sha256, algo_version, run_by, run_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (run_id, engagement_id, run_kind, seed, len(picks), json.dumps(params, sort_keys=True), head_seq,
                   pop_json, hashlib.sha256(pop_json.encode()).hexdigest(), ALGO, actor or "system", config.now()))
        for i, p in enumerate(picks, 1):
            doc_type = "credit_note" if run_kind == "CN_TOD" else "invoice"
            bundle_json, snap_hash = evidence.snapshot(p["id"])          # D11: what this conclusion depends on, now
            a.execute("INSERT INTO samples(run_id, sample_no, doc_type, doc_id, register_row_no, stratum, reason, risk_points,"
                      " snapshot_seq, bundle_json, snapshot_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (run_id, i, doc_type, p["id"], p.get("row"), p["stratum"], p["reason"], p.get("points", 0), head_seq,
                       bundle_json, snap_hash))
    sent = _requests(engagement_id, run_kind, picks)
    notify.emit("SAMPLES_SELECTED", {"run_id": run_id, "kind": run_kind, "samples": len(picks), "requests": sent},
                engagement_id)
    items = [{"sample_no": i, "doc_type": "credit_note" if run_kind == "CN_TOD" else "invoice", "doc_id": p["id"],
              "doc_no": p["no"], "stratum": p["stratum"], "reason": p["reason"]} for i, p in enumerate(picks, 1)]
    return {"run_id": run_id, "kind": run_kind, "seed": seed, "size": len(picks), "population": len(pop),
            "strata": dict(Counter(p["stratum"] for p in picks)), "items": items, "requests_sent": sent,
            "next_steps": [{"tool": "reproduce_selection", "example_args": {"run_id": run_id},
                            "why": "prove the selection is reproducible from its seed"},
                           {"tool": "list_evidence_requests", "example_args": {"status": "OPEN"},
                            "why": "the documents now requested from the client"}]}


def _requests(eid, run_kind, picks):
    """One pbc.evidence_requests row per required document; refs are opaque (S-014) and carry no reasons."""
    with db.borrow("erp", "system") as e:
        meta = {}
        for p in picks:
            if run_kind == "CN_TOD":
                c = e.execute("SELECT reason FROM credit_notes WHERE id = ?", (p["id"],)).fetchone()
                inv = e.execute("SELECT i.invoice_no FROM cn_lines l JOIN invoices i ON i.id = l.invoice_id WHERE l.cn_id = ?"
                                " LIMIT 1", (p["id"],)).fetchone()
                meta[p["id"]] = {"reason": c[0] if c else None, "invoice": inv[0] if inv else None}
            else:
                r = e.execute("SELECT COALESCE(SUM(taxable_paise + igst_paise + cgst_paise + sgst_paise), 0),"
                              " SUM(CASE WHEN hsn NOT LIKE '99%' AND item_id NOT LIKE 'CHG%' THEN 1 ELSE 0 END)"
                              " FROM invoice_lines WHERE invoice_id = ?", (p["id"],)).fetchone()
                meta[p["id"]] = {"value": r[0], "goods": (r[1] or 0) > 0}
    due = (date.fromisoformat(config.today()) + timedelta(days=7)).isoformat()
    n = 0
    with db.borrow("pbc", "system") as pb, db.tx(pb):
        last = pb.execute("SELECT id FROM evidence_requests WHERE id >= 'REQ-0' AND id < 'REQ-:' ORDER BY id DESC"
                          " LIMIT 1").fetchone()
        rid = int(last[0][4:]) if last else 0
        refs = pb.execute("SELECT count(DISTINCT sample_ref) FROM evidence_requests WHERE engagement_id = ?", (eid,)).fetchone()[0]
        for p in picks:
            refs += 1
            m = meta[p["id"]]
            if run_kind == "CN_TOD":
                kinds = ["CREDIT_NOTE", "RETURN_PROOF" if m["reason"] == "SALES_RETURN" else "OTHER"] + \
                        (["INVOICE"] if m["invoice"] else [])
                docs = {"CREDIT_NOTE": p["no"], "RETURN_PROOF": p["no"], "OTHER": p["no"], "INVOICE": m["invoice"]}
            else:
                kinds = ["INVOICE"]
                if m["goods"]:
                    kinds += ["LR", "POD"] + (["EWAY_BILL"] if m["value"] > config.EWB_THRESHOLD_PAISE else [])
                docs = {k: p["no"] for k in kinds}
            for k in kinds:
                rid += 1
                pb.execute("INSERT INTO evidence_requests(id, engagement_id, sample_ref, doc_kind, about_doc_no, requested_at,"
                           " due_on, status) VALUES (?,?,?,?,?,?,?,'OPEN')",
                           (f"REQ-{rid:06d}", eid, f"S-{refs:03d}", k, docs[k], config.now(), due))
                n += 1
    return n


def reproduce(run_id):
    """Re-run a selection on its stored population with its stored seed -> {run_id, identical, diff}."""
    with db.borrow("audit", "system") as a:
        run = a.execute("SELECT * FROM sample_runs WHERE id = ?", (run_id,)).fetchone()
        if run is None:
            raise LookupError("NOT_FOUND: no sample run with that id; list them with list_audit_items(kind='selections')")
        stored = [(r["doc_id"], r["stratum"]) for r in a.execute("SELECT doc_id, stratum FROM samples WHERE run_id = ?"
                                                                  " ORDER BY sample_no", (run_id,))]
    pop = json.loads(run["population_json"])
    if hashlib.sha256(run["population_json"].encode()).hexdigest() != run["population_sha256"]:
        return {"run_id": run_id, "identical": False, "diff": ["population snapshot does not match its sha256"]}
    again = [(p["id"], p["stratum"]) for p in _run(run["kind"], pop, run["seed"], json.loads(run["params_json"]))]
    diff = [{"sample_no": i + 1, "stored": s, "rerun": r} for i, (s, r) in
            enumerate(zip(stored + [None] * (len(again) - len(stored)), again + [None] * (len(stored) - len(again))))
            if s != r]
    return {"run_id": run_id, "seed": run["seed"], "algo_version": run["algo_version"], "identical": not diff,
            "diff": diff[:20]}
