"""Evaluation for the PPT (05 §19.8): precision / recall per PS family, false-positive rate, items prioritised, and
the ablation (transaction features only -> + graph features -> + entity risk) as recall of planted invoices in the top
k by risk. Uses data/answer_key.json, which app code never reads otherwise. Report it as prototype performance on
our synthetic data, never as real-world accuracy (05 §19.10).

    python -m app.evaluate [--answer-key data/answer_key.json] [--k 30]

answer_key.json: {"plants": [{"family": "C", "code": "PREMATURE", "object_type": "invoice", "object_id": "INV-000123"}]}
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from app import config, db, risk_graph


def evaluate(plants, k=30):
    """-> {per_family: {family: {plants, caught, recall}}, precision, fp_rate, prioritised, ablation, latency}."""
    with db.borrow("audit", "system") as a:
        hits = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ?", (config.ENGAGEMENT_ID,))]
        latest = {r[0]: dict(zip(("A", "E", "R", "band"), r[1:])) for r in a.execute(
            "SELECT object_id, A, E, R, band FROM risk_snapshots WHERE object_type = 'INVOICE' AND rowid IN"
            " (SELECT MAX(rowid) FROM risk_snapshots WHERE object_type = 'INVOICE' AND run_id LIKE 'RG-%'"
            " GROUP BY object_id)")}
        first_high = {r[0]: r[1] for r in a.execute(
            "SELECT object_id, MIN(CAST(substr(run_id, 4) AS INTEGER)) FROM risk_snapshots WHERE object_type = 'INVOICE'"
            " AND band = 'HIGH' AND run_id LIKE 'EV-%' GROUP BY object_id")}
    with db.borrow("erp", "system") as e:
        created = {r[0]: r[1] for r in e.execute("SELECT doc_id, MIN(seq) FROM erp_log WHERE doc_type = 'invoice'"
                                                 " GROUP BY doc_id")}
    by_obj = defaultdict(list)
    for h in hits:
        by_obj[(h["object_type"], h["object_id"])].append(h)
        ev = json.loads(h["evidence_json"] or "{}") or {}
        sid = (ev.get("sor") or {}).get("id") if isinstance(ev, dict) else None
        if sid:
            by_obj[("invoice", sid)].append(h)
    fam = defaultdict(lambda: {"plants": 0, "caught": 0})
    planted_objs = set()
    for p in plants:
        key = (p["object_type"], p["object_id"])
        planted_objs.add(key)
        got = by_obj.get(key, [])
        ok = any(h["code"] == p.get("code") or risk_graph.family(h) == p["family"] for h in got)
        fam[p["family"]]["plants"] += 1
        fam[p["family"]]["caught"] += int(ok)
    serious = [h for h in hits if h["severity"] >= 4]
    fp = [h for h in serious if (h["object_type"], h["object_id"]) not in planted_objs]
    planted_inv = {p["object_id"] for p in plants if p["object_type"] == "invoice"}
    models = {"baseline_A (transaction features)": lambda s: s["A"] or 0,
              "baseline_B (+ graph features)": lambda s: max(s["A"] or 0, 60_000 if s["E"] and s["E"] >= 60_000 else 0),
              "proposed (+ entity risk)": lambda s: s["R"] or 0}
    ablation = {}
    for name, fn in models.items():
        top = [iid for iid, _s in sorted(latest.items(), key=lambda kv: -fn(kv[1]))[:k]]
        ablation[name] = round(len(set(top) & planted_inv) / max(1, min(k, len(planted_inv))), 3)
    latency = [first_high[i] - created[i] for i in planted_inv if i in first_high and i in created]
    return {"per_family": {f: {**v, "recall": round(v["caught"] / v["plants"], 3)} for f, v in sorted(fam.items())},
            "recall": round(sum(v["caught"] for v in fam.values()) / max(1, len(plants)), 3),
            "precision_sev4": round(1 - len(fp) / max(1, len(serious)), 3), "false_positive_hits_sev4": len(fp),
            "prioritised_invoices_R60": sum(1 for s in latest.values() if (s["R"] or 0) >= 60_000),
            "ablation_recall_at_k": ablation, "k": k,
            "replay_latency_events": {"median": sorted(latency)[len(latency) // 2], "n": len(latency)} if latency else None,
            "note": "prototype performance on our synthetic data, not real-world accuracy"}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.evaluate", description=__doc__.split("\n\n")[0])
    ap.add_argument("--answer-key", default=str(config.DATA_DIR / "answer_key.json"))
    ap.add_argument("--k", type=int, default=30)
    a = ap.parse_args(argv)
    path = Path(a.answer_key)
    if not path.exists():
        raise SystemExit(f"no answer key at {path}: plant irregularities first (DA-1) so the key exists")
    r = evaluate(json.loads(path.read_text(encoding="utf-8"))["plants"], a.k)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    sys.exit(main())
