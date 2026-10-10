"""Events -> audit.events + optional n8n webhook (10 §1).

The events row is the record ("the system is notified of the upload"); the webhook is best-effort: a down n8n
never breaks the audit. Body {kind, engagement_id, payload, at}; header X-AuditPilot-Signature: sha256=<HMAC>.
"""
import hashlib
import hmac
import json
import logging
import urllib.request

from app import config, db

log = logging.getLogger("auditpilot.notify")
KINDS = ("REGISTER_UPLOADED", "RP_LIST_UPLOADED", "SAMPLES_SELECTED", "EVIDENCE_RECEIVED", "STALE_DETECTED",
         "INTEGRITY_ALERT", "READY_FOR_REVIEW", "SIGNED_OFF", "RISK_ESCALATED")


def emit(kind, payload, engagement_id=None):
    """Write an events row; POST it to N8N_WEBHOOK_URL when set (signed), and mark notified_at on a 2xx."""
    if kind not in KINDS:
        raise ValueError(f"INVALID_ARGUMENT: event kind must be one of {', '.join(KINDS)}")
    at = config.now()
    with db.borrow("audit", "system") as a, db.tx(a):
        eid = a.execute("INSERT INTO events(engagement_id, kind, payload_json, at) VALUES (?,?,?,?)",
                        (engagement_id, kind, json.dumps(payload, sort_keys=True, default=str), at)).lastrowid
    if not config.N8N_WEBHOOK_URL:
        return None
    body = json.dumps({"id": eid, "kind": kind, "engagement_id": engagement_id, "payload": payload, "at": at},
                      sort_keys=True, default=str).encode()
    sig = hmac.new(config.N8N_SECRET.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(config.N8N_WEBHOOK_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-AuditPilot-Signature": f"sha256={sig}"})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            if 200 <= r.status < 300:
                with db.borrow("audit", "system") as a, db.tx(a):
                    a.execute("UPDATE events SET notified_at = ? WHERE id = ?", (config.now(), eid))
    except Exception as e:  # noqa: BLE001 - n8n is optional (10: the core never depends on an integration)
        log.warning("n8n webhook failed for event %s: %s", eid, e)
    return None
