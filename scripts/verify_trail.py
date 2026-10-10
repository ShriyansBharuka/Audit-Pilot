"""Verify an exported audit trail offline (06 §8). Standard library only, so a partner or judge can run it anywhere:

    python scripts/verify_trail.py audit_trail.jsonl [erp_log_head.json]

Recomputes the hash chain (canonical JSON, SHA-256, prev_hash links) and checks that every anchor in
erp_log_head.json sits at its seq with its hash. Exit code 0 = OK, 1 = broken.
"""
import hashlib
import json
import sys
from pathlib import Path

GENESIS = "0" * 64


def canon(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify(lines, anchors=()):
    prev, by_seq = GENESIS, {}
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        d = json.loads(line)
        stored = d.pop("hash")
        if d.get("prev_hash") != prev or hashlib.sha256(canon(d).encode()).hexdigest() != stored:
            return False, f"BROKEN at seq {d.get('seq')} (line {n})"
        prev = by_seq[d["seq"]] = stored
    for a in anchors:
        if a.get("trail_seq") and by_seq.get(a["trail_seq"]) != a.get("trail_hash"):
            return False, f"ANCHOR MISMATCH at seq {a['trail_seq']} ({a.get('label')} anchor of {a.get('at')})"
    return True, f"OK: {len(by_seq)} rows, head seq {max(by_seq) if by_seq else 0} {prev[:12]}, {len(anchors)} anchor(s) checked"


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    lines = Path(argv[0]).read_text(encoding="utf-8").splitlines()
    anchors = []
    if len(argv) > 1:
        head = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        anchors = [a for a in head.get("anchors", []) if a.get("trail_seq")]
    ok, msg = verify(lines, anchors)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
