"""Tamper demo (09 demo step 4): edit the SQLite files behind the application's back and watch D12 catch it.

    python scripts/tamper_demo.py --data-dir <a seeded demo data dir> --yes

1. a direct UPDATE of an invoice date with its [F] trigger dropped        -> OUT_OF_BAND_EDIT
2. DROP the erp_log guards, edit a logged row and re-chain everything after -> the chain verifies, but the auditor's
   anchor (held in audit.db, which the client can't open) no longer matches  -> ANCHOR_MISMATCH
DESTRUCTIVE for the data dir it is pointed at: run it on a demo copy only.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--yes", action="store_true", help="confirm: this edits the databases in --data-dir")
    a = ap.parse_args(argv)
    if not a.yes:
        raise SystemExit("refusing to tamper without --yes (it edits the databases in --data-dir)")
    os.environ["DATA_DIR"] = a.data_dir
    from app import chain, config, evidence, intake, trail
    config.set_data_dir(a.data_dir)
    eid = intake.ensure_engagement()
    trail.anchor(eid, "PERIODIC")                       # the auditor's checkpoint before the tampering
    print("before:", _summary(evidence.verify_integrity(eid)))

    raw = sqlite3.connect(str(config.DB_PATHS["erp"]), isolation_level=None)
    raw.row_factory = sqlite3.Row
    inv = raw.execute("SELECT id, invoice_date FROM invoices WHERE status = 'ISSUED' ORDER BY invoice_date DESC LIMIT 1"
                      ).fetchone()
    raw.execute("DROP TRIGGER IF EXISTS invoices_f")
    raw.execute("UPDATE invoices SET invoice_date = '2026-04-02' WHERE id = ?", (inv["id"],))
    print(f"1. moved {inv['id']} from {inv['invoice_date']} to 2026-04-02 directly in SQLite")
    print("   after:", _summary(evidence.verify_integrity(eid)))

    for t in ("erp_log_no_update", "erp_log_no_delete"):
        raw.execute(f"DROP TRIGGER IF EXISTS {t}")
    first = raw.execute("SELECT MIN(seq) FROM erp_log WHERE doc_type = 'invoice'").fetchone()[0]
    rows = [dict(r) for r in raw.execute("SELECT * FROM erp_log WHERE seq >= ? ORDER BY seq", (first,))]
    raw.execute("DELETE FROM erp_log WHERE seq >= ?", (first,))
    prev = raw.execute("SELECT hash FROM erp_log WHERE seq = ?", (first - 1,)).fetchone()
    prev = prev[0] if prev else chain.GENESIS
    for d in rows:
        d.pop("hash")
        d["prev_hash"] = prev
        if d["seq"] == first:
            d["actor"] = "someone.else"
        d["hash"] = prev = chain.h(d)
        raw.execute(f"INSERT INTO erp_log ({','.join(d)}) VALUES ({','.join('?' * len(d))})", list(d.values()))
    raw.close()
    print(f"2. rewrote erp_log from seq {first} and re-chained {len(rows)} rows")
    print("   after:", _summary(evidence.verify_integrity(eid)))


def _summary(v):
    return "OK" if v["ok"] else ", ".join(sorted({p["code"] for p in v["problems"]}))


if __name__ == "__main__":
    main()
