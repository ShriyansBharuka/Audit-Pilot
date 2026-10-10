"""Hash chain for erp_log and audit_trail (03 §6; port of ReliefNet backend/app/ledger.py).

Canonical-JSON SHA-256 over the whole row (every column except hash), linked by prev_hash. Tampering is detected,
not prevented: a rewritten tail re-chains cleanly, so verify() also checks the auditor's anchors held in audit.db.
"""
import hashlib, json
GENESIS = '0' * 64
def canon(d): return json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
def h(d): return hashlib.sha256(canon(d).encode()).hexdigest()

def append(conn, table, row):  # caller holds BEGIN IMMEDIATE; row = every column except seq/prev_hash/hash
    last = conn.execute(f'SELECT seq, hash FROM {table} ORDER BY seq DESC LIMIT 1').fetchone()
    row = {**row, 'seq': last[0] + 1 if last else 1, 'prev_hash': last[1] if last else GENESIS}
    row['hash'] = h(row)
    conn.execute(f'INSERT INTO {table} ({",".join(row)}) VALUES ({",".join("?" * len(row))})', list(row.values()))
    return row['seq'], row['hash']

def verify(conn, table, anchors=()):  # anchors: [(seq, hash)] stored in audit.db
    prev, by_seq = GENESIS, {}
    for r in conn.execute(f'SELECT * FROM {table} ORDER BY seq'):
        d = dict(r); stored = d.pop('hash')
        if d['prev_hash'] != prev or h(d) != stored:
            return {'valid': False, 'broken_at_seq': d['seq'], 'anchor_mismatch_at': None}
        prev = by_seq[d['seq']] = stored
    bad = next((s for s, hh in anchors if by_seq.get(s) != hh), None)
    return {'valid': bad is None, 'broken_at_seq': None, 'anchor_mismatch_at': bad}


def head(conn, table):
    """(seq, hash) of the newest row, or (0, GENESIS) for an empty chain: what anchors and trail rows record."""
    r = conn.execute(f'SELECT seq, hash FROM {table} ORDER BY seq DESC LIMIT 1').fetchone()
    return (r[0], r[1]) if r else (0, GENESIS)
