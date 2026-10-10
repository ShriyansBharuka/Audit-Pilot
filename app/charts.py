"""Analytics charts (EX-2): daily volume with z-scores, Benford first digits, risk distribution. Read-only ERP / audit
handles; money stays integer paise; z-scores, chi-square and proportions are derived statistics (floats are fine)."""
import json
import statistics
from collections import defaultdict
from datetime import date, timedelta

from app import analytics, config, db, findings

Z_FLAG = 3.0
WINDOW_DAYS = 10
SCATTER_CAP = 2000
HIGH_RISK = 70


def daily_volume(rows, period_end, window_days=WINDOW_DAYS):
    """rows: [(iso_date, total_paise)] -> {days: [{date, count, total_paise, z, flagged, period_end_window}], mean_paise,
    stdev_paise}. Statistics over days with at least one invoice; z = (total - mean) / stdev."""
    per = defaultdict(lambda: [0, 0])
    for d, total in rows:
        per[d][0] += 1
        per[d][1] += int(total)
    totals = [v[1] for v in per.values()]
    mean = statistics.fmean(totals) if totals else 0.0
    sd = statistics.pstdev(totals) if len(totals) > 1 else 0.0
    start = (date.fromisoformat(period_end) - timedelta(days=window_days - 1)).isoformat() if period_end else None
    days = []
    for d in sorted(per):
        z = (per[d][1] - mean) / sd if sd else 0.0
        days.append({"date": d, "count": per[d][0], "total_paise": per[d][1], "z": round(z, 3), "flagged": z >= Z_FLAG,
                     "period_end_window": bool(start and start <= d <= period_end)})
    return {"days": days, "mean_paise": round(mean), "stdev_paise": round(sd), "z_flag": Z_FLAG}


def charts(engagement_id=None, role="audit_staff"):
    """-> {volume, benford, risk} for the engagement's financial year."""
    eid = engagement_id or config.ENGAGEMENT_ID
    with db.borrow("audit", role) as a:
        eng = a.execute("SELECT period_start, period_end FROM engagements WHERE id = ?", (eid,)).fetchone()
        start, end = (eng[0], eng[1]) if eng else (config.PERIOD_START, config.PERIOD_END)
        risk = {r[0]: r[1] for r in a.execute(
            "SELECT object_id, R FROM risk_snapshots WHERE object_type = 'INVOICE' AND rowid IN"
            " (SELECT MAX(rowid) FROM risk_snapshots WHERE object_type = 'INVOICE' GROUP BY object_id)")}
        hits = defaultdict(list)
        for r in a.execute("SELECT detector, code, object_type, object_id, severity, impact_paise, evidence_json FROM"
                           " risk_hits WHERE engagement_id = ?", (eid,)):
            oid = r["object_id"]
            if r["object_type"] == "register_row":
                oid = ((json.loads(r["evidence_json"] or "{}") or {}).get("sor") or {}).get("id")
            elif r["object_type"] != "invoice":
                continue
            if oid:
                hits[oid].append(r)
    with db.borrow("erp", role) as e:
        inv = [dict(r) for r in e.execute(
            "SELECT i.id, i.invoice_no, i.invoice_date, i.round_off_paise + COALESCE(SUM(l.taxable_paise + l.igst_paise +"
            " l.cgst_paise + l.sgst_paise), 0) AS total FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id = i.id"
            " WHERE i.status = 'ISSUED' AND i.invoice_date BETWEEN ? AND ? GROUP BY i.id ORDER BY i.invoice_date, i.id",
            (start, end))]
    volume = daily_volume([(i["invoice_date"], i["total"]) for i in inv], end)
    b = analytics.benford([i["total"] for i in inv if i["total"] > 0])
    benford = {"n": b["n"], "chi2": round(b["chi2"], 3), "critical": analytics.BENFORD_CHI2_CRIT, "flagged": b["flagged"],
               "mad": round(b["mad"], 5),
               "digits": [{"digit": d, "count": b["counts"][d], "actual": (b["counts"][d] / b["n"]) if b["n"] else 0.0,
                           "expected": b["expected"][d]} for d in range(1, 10)]}
    bands = {"<30": 0, "30-69": 0, ">=70": 0}
    points = []
    for i in inv:
        r = round((risk.get(i["id"]) or 0) / 1000)
        bands["<30" if r < 30 else "30-69" if r < HIGH_RISK else ">=70"] += 1
        top = max(hits.get(i["id"], []), key=lambda h: (h["severity"], h["impact_paise"] or 0), default=None)
        points.append({"invoice_no": i["invoice_no"], "total_paise": i["total"], "risk_score": r,
                       "category": findings.CATEGORY.get(top["detector"], top["detector"]) if top else "No hits",
                       "code": top["code"] if top else None})
    high = [p for p in points if p["risk_score"] >= HIGH_RISK]
    rest = [p for p in points if p["risk_score"] < HIGH_RISK]
    room = max(0, SCATTER_CAP - len(high))
    step = max(1, -(-len(rest) // room)) if room else len(rest) + 1
    scatter = high + rest[::step][:room]
    return {"period": {"start": start, "end": end}, "volume": volume, "benford": benford,
            "risk": {"histogram": [{"band": k, "count": v} for k, v in bands.items()], "scatter": scatter,
                     "scatter_total": len(points), "scatter_shown": len(scatter)}}
