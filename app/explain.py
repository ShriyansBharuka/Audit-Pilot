"""Exact SHAP (Shapley value) attribution of an invoice's AuditGraph risk score R (05 §19.5).

Players: every risk hit on the invoice, plus the customer's entity risk E. The value function v(S) is the real
scoring formula with only the players in S present: R = max(0.7 A + 0.3 E, 60 if a hard-evidence hit of severity
>= 4 is present), A = noisy-OR of the present hits, E = the customer's E if present, else 0. So v(empty) = 0 (a clean
invoice of a clean customer) and, by Shapley efficiency, the attributions sum to v(all players) = R exactly.
E's attribution is then split over its five weighted terms (0.35C + 0.25F + 0.15T + 0.15H + 0.10N, plus the
related-party / circular floor when it binds) in proportion to their value: an Owen value with blocks {hits}, {E}.

No model is trained and nothing is sampled: the 2^n coalitions are enumerated (n <= MAX_PLAYERS; above that the hits
are grouped by code). Reasons cite codes and ids only, never client text.
"""
import json
from itertools import combinations
from math import factorial

from app import config, db, risk_graph

MAX_PLAYERS = 12
E_WEIGHTS = {"C": 0.35, "F": 0.25, "T": 0.15, "H": 0.15, "N": 0.10}
E_LABELS = {"C": "Circular trading through this customer (C)", "F": "Customer's other flagged sales (F)",
            "T": "Customer's year-end concentration (T)", "H": "Open exceptions on this customer (H)",
            "N": "Risk of related neighbours (N)", "floor": "Related-party / circular-trading floor (E >= 60)"}


def shapley(n, v):
    """Exact Shapley values for players 0..n-1 of the set function v(frozenset) -> float."""
    cache = {}

    def val(s):
        if s not in cache:
            cache[s] = v(s)
        return cache[s]
    phi = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        total = 0.0
        for k in range(n):
            w = factorial(k) * factorial(n - k - 1) / factorial(n)
            for s in combinations(others, k):
                s = frozenset(s)
                total += w * (val(s | {i}) - val(s))
        phi.append(total)
    return phi


def _r(hits, e):
    """The AuditGraph invoice score (risk_graph.score) for these hits and this entity risk."""
    floor = 60 if any(h["code"] in risk_graph.HARD and h["severity"] >= 4 for h in hits) else 0
    return max(0.70 * risk_graph._engine_a(hits) + 0.30 * e, floor)


def explain_invoice(ref, engagement_id=None):
    """-> {invoice, R, A, E, band, base_value, contributions [...], entity_terms [...], check, ...} or None."""
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("erp", "system") as e:
        inv = e.execute("SELECT id, invoice_no, invoice_date, party_id FROM invoices WHERE id = ? OR invoice_no = ?",
                        (ref, ref)).fetchone()
        if inv is None:
            return None
        inv = dict(inv)
        pname = (e.execute("SELECT name FROM parties WHERE id = ?", (inv["party_id"],)).fetchone() or [None])[0]
    with db.borrow("audit", "system") as a:
        snap = a.execute("SELECT A, E, R, band FROM risk_snapshots WHERE object_type = 'INVOICE' AND object_id = ?"
                         " ORDER BY rowid DESC LIMIT 1", (inv["id"],)).fetchone()
        party = a.execute("SELECT E, reasons_json FROM risk_snapshots WHERE object_type = 'PARTY' AND object_id = ?"
                          " ORDER BY rowid DESC LIMIT 1", (inv["party_id"],)).fetchone()
        hits = risk_graph._hits(a, eid)[1].get(("invoice", inv["id"]), [])
    e_val = (snap["E"] or 0) / 1000 if snap else ((party["E"] or 0) / 1000 if party else 0.0)

    # players: hits (grouped by code if there are too many to enumerate) + the entity risk E
    groups = [[h] for h in hits]
    if len(groups) + 1 > MAX_PLAYERS:
        by_code = {}
        for h in hits:
            by_code.setdefault(h["code"], []).append(h)
        groups = list(by_code.values())
    n_hit = len(groups)
    players = groups + ([None] if e_val else [])

    def v(s):
        present = [h for i in s if i < n_hit for h in groups[i]]
        return _r(present, e_val if n_hit in s else 0.0)
    phi = shapley(len(players), v)
    model_r = v(frozenset(range(len(players))))

    contributions = []
    for i, g in enumerate(groups):
        h = g[0]
        label = f"{h['code']} ({h['detector']}, severity {h['severity']})" + (f" x{len(g)}" if len(g) > 1 else "")
        contributions.append({"feature": label, "kind": "hit", "detector": h["detector"], "code": h["code"],
                              "severity": h["severity"], "value": round(phi[i], 2)})
    entity_terms = []
    if e_val:
        phi_e = phi[n_hit]
        terms = (json.loads(party["reasons_json"] or "{}").get("terms") or {}) if party else {}
        parts = {k: E_WEIGHTS[k] * terms.get(k, 0) for k in E_WEIGHTS if terms.get(k)}
        lin = sum(parts.values())
        if e_val > lin + 0.5:
            parts["floor"] = e_val - lin
        tot = sum(parts.values()) or 1
        for k, p in parts.items():
            entity_terms.append({"term": k, "feature": E_LABELS[k], "value": round(phi_e * p / tot, 2),
                                 "term_value": terms.get(k)})
        contributions.append({"feature": f"Customer entity risk E = {e_val:.0f}", "kind": "entity", "detector": None,
                              "code": None, "severity": None, "value": round(phi_e, 2)})
    total = sum(phi)
    stored_r = (snap["R"] or 0) / 1000 if snap else 0.0
    contributions.sort(key=lambda c: -c["value"])
    return {"invoice_id": inv["id"], "invoice_no": inv["invoice_no"], "invoice_date": inv["invoice_date"],
            "party_id": inv["party_id"], "party_name": pname,
            "risk_score": round(model_r, 1), "stored_risk_score": round(stored_r, 1),
            "risk_band": risk_graph.band(model_r), "A": risk_graph._engine_a(hits), "E": round(e_val, 1),
            "base_value": 0.0, "contributions": contributions, "entity_terms": entity_terms,
            "check": {"sum_of_attributions": round(total, 2), "model_output": round(model_r, 2),
                      "exact": abs(total - model_r) < 1e-6,
                      "note": "attributions sum to the score exactly (Shapley efficiency); the stored score is the "
                              "same value rounded, or older if the invoice changed since the last AuditGraph run"},
            "method": f"exact Shapley values over {len(players)} players (2^{len(players)} coalitions enumerated), "
                      "baseline = a clean invoice of a clean customer (score 0)",
            "explanation_text": _prose(inv, model_r, contributions, entity_terms)}


def _prose(inv, r, contributions, entity_terms):
    if not contributions:
        return f"{inv['invoice_no']} has no risk hits and its customer carries no entity risk: score 0."
    top = [c for c in contributions if c["value"] > 0][:3]
    parts = [f"{c['code'] or 'customer entity risk'} (+{c['value']:.1f})" for c in top]
    s = f"{inv['invoice_no']} scores {r:.1f} of 100. Largest contributions: {', '.join(parts)}."
    if entity_terms:
        t = max(entity_terms, key=lambda x: x["value"])
        s += f" The customer's share comes mostly from: {t['feature']}."
    return s


def summary(engagement_id=None, min_r=30, limit=200):
    """Global importance (mean |SHAP| per code) over the invoices scored >= min_r: a SHAP summary view."""
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("audit", "system") as a:
        ids = [r[0] for r in a.execute(
            "SELECT object_id FROM risk_snapshots WHERE object_type = 'INVOICE' AND rowid IN (SELECT MAX(rowid)"
            " FROM risk_snapshots WHERE object_type = 'INVOICE' GROUP BY object_id) AND R >= ? ORDER BY R DESC LIMIT ?",
            (min_r * 1000, limit))]
    agg, n = {}, len(ids)
    for iid in ids:
        x = explain_invoice(iid, eid)
        for c in x["contributions"]:
            key = c["code"] or "ENTITY_RISK_E"
            s = agg.setdefault(key, {"feature": key, "detector": c["detector"], "sum_abs": 0.0, "invoices": 0})
            s["sum_abs"] += abs(c["value"])
            s["invoices"] += 1
    rows = sorted(({**s, "mean_abs": round(s["sum_abs"] / n, 2) if n else 0, "sum_abs": round(s["sum_abs"], 1)}
                   for s in agg.values()), key=lambda s: -s["mean_abs"])
    return {"invoices": n, "min_risk": min_r, "features": rows}
