"""Population procedures D3-D7, D9, D10, D13, D14 -> audit.risk_hits (05). run_all is a STUB until AA-2;
save_hits is the shared writer every detector (D0 in register.py, D1/D2 in related_parties.py) uses."""
import json

from app import config, db

STUB = True


def save_hits(engagement_id, run_id, hits, detectors):
    """Replace this engagement's hits for `detectors` with `hits` (risk_hit dicts, 07 §4). Returns the count."""
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute(f"DELETE FROM risk_hits WHERE engagement_id = ? AND detector IN ({','.join('?' * len(detectors))})",
                  (engagement_id, *sorted(detectors)))
        at = config.now()
        a.executemany("INSERT INTO risk_hits(engagement_id, analytics_run, detector, code, object_type, object_id, severity,"
                      " impact_paise, reason, evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      [(engagement_id, run_id, h["detector"], h["code"], h["object_type"], str(h["object_id"]),
                        h["severity"], int(h.get("impact_paise") or 0), h["reason"],
                        json.dumps(h.get("evidence"), sort_keys=True, default=str), at) for h in hits])
    return len(hits)


def run_all(engagement_id, detectors=None, incremental=False):
    """-> {run_id, counts: {detector: {code: n}}, top: [risk_hit, ...] (max 20)}."""
    return {"run_id": "", "counts": {}, "top": []}
