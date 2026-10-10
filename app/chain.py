"""Hash chain for erp_log and audit_trail (03 §6). STUB until IB-1: copy the 03 §6 code exactly."""
STUB = True
GENESIS = "0" * 64


def canon(d):
    raise NotImplementedError("chain.canon: IB-1")


def h(d):
    raise NotImplementedError("chain.h: IB-1")


def append(conn, table, row):
    """-> (seq, hash). Caller holds BEGIN IMMEDIATE; row = every column except seq/prev_hash/hash."""
    return 0, GENESIS


def verify(conn, table, anchors=()):
    """-> {valid, broken_at_seq, anchor_mismatch_at}. anchors: [(seq, hash)] stored in audit.db."""
    return {"valid": True, "broken_at_seq": None, "anchor_mismatch_at": None}
