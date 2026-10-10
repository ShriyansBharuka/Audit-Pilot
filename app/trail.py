"""audit_trail rows (hash-chained, with the erp_log head as anchor) and explicit anchors (03 §5-6). STUB until IB-4."""
STUB = True


def trail(principal, role, tool, args, outcome, result=None, transport="HTTP"):
    """Append one audit_trail row: OK | DENIED | ERROR. Tokens are never logged; evidence bytes become sha256."""
    return None


def anchor(engagement_id, label):
    """-> {id, label, erp_seq, erp_hash, trail_seq, trail_hash, at}."""
    return {"id": 0, "label": label, "erp_seq": 0, "erp_hash": "", "trail_seq": 0, "trail_hash": "", "at": ""}
