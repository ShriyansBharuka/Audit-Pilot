"""03 §6 required tamper tests: (a) raw edit, (b) edit + rehash, (c) rewritten tail vs anchor, (d) out-of-band edit."""
import sqlite3

from app import chain, config, db, erp


def _log(conn, n):
    with db.tx(conn):
        for i in range(n):
            conn.execute("INSERT INTO items(id,name,hsn,uom,gst_rate_bp) VALUES (?,?,?,?,1800)", (f"IT-{i}", "x", "8481", "NOS"))
            erp.write_doc(conn, "acc.neha", "client_admin", "create_item", "CREATE", "item", f"IT-{i}")
    erp.discard_events(conn)


def _raw(name):
    c = sqlite3.connect(str(config.DB_PATHS[name]), isolation_level=None)
    c.row_factory = sqlite3.Row
    return c


def _drop_guards(c, table):
    c.execute(f"DROP TRIGGER {table}_no_update")
    c.execute(f"DROP TRIGGER {table}_no_delete")


def test_clean_chain_verifies(world):
    c = db.connect("erp", "client_admin")
    _log(c, 5)
    n = c.execute("SELECT count(*) FROM erp_log").fetchone()[0]
    assert chain.verify(c, "erp_log") == {"valid": True, "broken_at_seq": None, "anchor_mismatch_at": None}
    assert chain.head(c, "erp_log")[0] == n
    c.close()


def test_a_raw_edit_without_rehash(world):
    c = db.connect("erp", "client_admin")
    _log(c, 5)
    n = c.execute("SELECT seq FROM erp_log WHERE doc_id = 'IT-2'").fetchone()[0]
    c.close()
    r = _raw("erp")
    _drop_guards(r, "erp_log")
    r.execute("UPDATE erp_log SET actor = 'someone.else' WHERE seq = ?", (n,))
    assert chain.verify(r, "erp_log")["broken_at_seq"] == n
    r.close()


def test_b_edit_and_rehash_breaks_the_next_row(world):
    c = db.connect("erp", "client_admin")
    _log(c, 5)
    n = c.execute("SELECT seq FROM erp_log WHERE doc_id = 'IT-2'").fetchone()[0]
    c.close()
    r = _raw("erp")
    _drop_guards(r, "erp_log")
    row = dict(r.execute("SELECT * FROM erp_log WHERE seq = ?", (n,)).fetchone())
    row.pop("hash")
    row["actor"] = "someone.else"
    r.execute("UPDATE erp_log SET actor = ?, hash = ? WHERE seq = ?", (row["actor"], chain.h(row), n))
    assert chain.verify(r, "erp_log")["broken_at_seq"] == n + 1
    r.close()


def test_c_rewritten_tail_is_caught_by_the_anchor(world):
    c = db.connect("erp", "client_admin")
    _log(c, 5)
    anchor = chain.head(c, "erp_log")               # what audit.anchors holds (the client can't touch it)
    first_item = c.execute("SELECT seq FROM erp_log WHERE doc_id = 'IT-0'").fetchone()[0]
    c.close()
    r = _raw("erp")
    _drop_guards(r, "erp_log")
    rows = [dict(x) for x in r.execute("SELECT * FROM erp_log WHERE seq >= ? ORDER BY seq", (first_item,))]
    r.execute("DELETE FROM erp_log WHERE seq >= ?", (first_item,))
    prev = r.execute("SELECT hash FROM erp_log WHERE seq = ?", (first_item - 1,)).fetchone()
    prev = prev[0] if prev else chain.GENESIS
    for d in rows:                                  # rewrite history: change an actor, re-chain everything after
        d.pop("hash")
        d["prev_hash"], d["actor"] = prev, "forger"
        d["hash"] = prev = chain.h(d)
        r.execute(f"INSERT INTO erp_log ({','.join(d)}) VALUES ({','.join('?' * len(d))})", list(d.values()))
    v = chain.verify(r, "erp_log", anchors=[anchor])
    assert v["broken_at_seq"] is None and v["valid"] is False and v["anchor_mismatch_at"] == anchor[0]
    assert chain.verify(r, "erp_log")["valid"] is True     # without the anchor the forgery would pass
    r.close()


def test_d_direct_update_with_triggers_dropped_is_out_of_band(world):
    c = db.connect("erp", "client_admin")
    with db.tx(c):
        c.execute("INSERT INTO parties(id,kind,name,recorded_by,recorded_at) VALUES ('P-1','ENTITY','x','a','t')")
        erp.write_doc(c, "sales.priya", "sales", "create_party", "CREATE", "party", "P-1")
        c.execute("INSERT INTO invoices(id,invoice_no,series,supplier_gstin,invoice_date,party_id,place_of_supply)"
                  " VALUES ('INV-1','G2/0001/25','G2','g','2026-03-30','P-1','27')")
        erp.write_doc(c, "acc.neha", "accounts", "issue_invoice", "CREATE", "invoice", "INV-1")
    erp.discard_events(c)
    assert erp.out_of_band(c) == []
    c.close()
    r = _raw("erp")
    r.execute("DROP TRIGGER invoices_f")
    r.execute("UPDATE invoices SET invoice_date = '2026-04-02' WHERE id = 'INV-1'")
    r.close()
    c = db.connect("erp", "audit_staff")
    oob = erp.out_of_band(c)
    assert [(o["doc_type"], o["doc_id"], o["kind"]) for o in oob] == [("invoice", "INV-1", "CHANGED")]
    assert oob[0]["fields"] == {"header.invoice_date": ["2026-03-30", "2026-04-02"]}
    assert oob[0]["last_logged_by"] == "acc.neha"
    c.close()
