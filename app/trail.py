"""audit_trail (hash-chained, append-only) + anchors (03 §5-6).

Every MCP call, including every denial, is one trail row. Each row stores the erp_log head at that moment
(erp_seq, erp_hash): the auditor's copy of where the client's books stood, in a file the client can't open.
Tokens are never logged; evidence bytes / base64 payloads are replaced by their sha256.
"""
import hashlib
import json

from app import chain, config, db

_BIG = 2048            # any string argument longer than this is stored as its sha256 (evidence, CSV, base64)
_SECRET_KEYS = {"token", "authorization", "mcp_token", "password", "api_key", "secret"}


def _redact(v):
    if isinstance(v, dict):
        return {k: ("[redacted]" if str(k).lower() in _SECRET_KEYS else _redact(x)) for k, x in v.items()}
    if isinstance(v, list):
        return [_redact(x) for x in v[:200]]
    if isinstance(v, (bytes, bytearray)):
        return {"sha256": hashlib.sha256(v).hexdigest(), "bytes": len(v)}
    if isinstance(v, str) and len(v) > _BIG:
        return {"sha256": hashlib.sha256(v.encode()).hexdigest(), "chars": len(v)}
    return v


def erp_head():
    with db.borrow("erp", "system") as e:
        return chain.head(e, "erp_log")


def trail(principal, role, tool, args, outcome, result=None, transport="HTTP"):
    """Append one audit_trail row: OK | DENIED | ERROR, anchored to the current erp_log head."""
    try:
        seq, h = erp_head()
    except FileNotFoundError:
        seq, h = None, None
    res = None if result is None else hashlib.sha256(
        json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
    with db.borrow("audit", "system") as a, db.tx(a):
        chain.append(a, "audit_trail", {
            "at": config.now(), "principal": principal, "role": role, "transport": transport, "tool": tool,
            "args_json": json.dumps(_redact(args or {}), sort_keys=True, default=str), "outcome": outcome,
            "result_sha256": res, "erp_seq": seq, "erp_hash": h})
    return None


def anchor(engagement_id, label):
    """An explicit checkpoint: both chain heads, stored in audit.anchors. -> the anchor row."""
    erp_seq, erp_hash = erp_head()
    with db.borrow("audit", "system") as a, db.tx(a):
        t_seq, t_hash = chain.head(a, "audit_trail")
        at = config.now()
        aid = a.execute("INSERT INTO anchors(engagement_id, label, erp_seq, erp_hash, trail_seq, trail_hash, at)"
                        " VALUES (?,?,?,?,?,?,?)", (engagement_id, label, erp_seq, erp_hash, t_seq, t_hash, at)).lastrowid
    return {"id": aid, "label": label, "erp_seq": erp_seq, "erp_hash": erp_hash, "trail_seq": t_seq,
            "trail_hash": t_hash, "at": at}
