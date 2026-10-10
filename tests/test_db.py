"""SH-1/SH-2 done-when: role-bound handles (03 §0, §6), schema guards, clock, unit master."""
import pytest

from app import config, db, seed


def raises(fn, *fragments):
    with pytest.raises(Exception) as e:
        fn()
    assert all(f in str(e.value) for f in fragments), str(e.value)


def test_audit_role_cannot_write_business_data(world):
    for role in ("audit_staff", "engagement_partner", "system"):
        c = db.connect("erp", role)
        raises(lambda: c.execute("INSERT INTO accounts(code,name,type) VALUES ('X','x','ASSET')"),
               "attempt to write a readonly database")
        assert c.execute("PRAGMA query_only").fetchone()[0] == 1
        c.close()
        e = db.connect("ext", role)
        raises(lambda: e.execute("DELETE FROM einvoices"), "readonly database")
        e.close()


def test_client_roles_have_no_audit_handle(world):
    for role in ("sales", "warehouse", "accounts", "client_admin"):
        raises(lambda: db.connect("audit", role), "PERMISSION_DENIED", "audit workpapers")
    raises(lambda: db.connect("erp", "orchestrator"), "PERMISSION_DENIED")
    raises(lambda: db.connect("erp", "nobody"), "PERMISSION_DENIED")
    o = db.connect("audit", "orchestrator")
    raises(lambda: o.execute("INSERT INTO events(kind,at) VALUES ('SIGNED_OFF','t')"), "readonly")
    o.close()


def test_only_portal_writes_ext(world):
    c = db.connect("ext", "client_admin")
    raises(lambda: c.execute("INSERT INTO bank_txns(id,account_no,value_date,amount_paise)"
                             " VALUES ('B','1','2025-04-01',1)"), "readonly")
    c.close()
    p = db.connect("ext", "portal")
    with db.tx(p):
        p.execute("INSERT INTO bank_txns(id,account_no,value_date,amount_paise) VALUES ('B','1','2025-04-01',-1)")
    assert p.execute("SELECT amount_paise FROM bank_txns").fetchone()[0] == -1
    p.close()


def test_tx_commits_rolls_back_and_nests(world):
    c = db.connect("erp", "client_admin")
    with pytest.raises(RuntimeError):
        with db.tx(c):
            c.execute("INSERT INTO accounts(code,name,type) VALUES ('A1','a','ASSET')")
            raise RuntimeError
    with db.tx(c):
        c.execute("INSERT INTO accounts(code,name,type) VALUES ('A2','a','ASSET')")
        with db.tx(c):                                     # joins the outer transaction
            c.execute("INSERT INTO accounts(code,name,type) VALUES ('A3','a','ASSET')")
    assert [r[0] for r in c.execute("SELECT code FROM accounts WHERE code LIKE 'A_' ORDER BY code")] == ["A2", "A3"]
    c.close()


def test_missing_database_is_actionable(tmp_path):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path / "empty")
    try:
        raises(lambda: db.connect("erp", "sales"), "PRECONDITION_FAILED", "app.seed --reset")
    finally:
        config.set_data_dir(default)


def test_schema_guards(world):
    c = db.connect("erp", "client_admin")
    c.execute("INSERT INTO parties(id,kind,name,recorded_by,recorded_at) VALUES ('P','ENTITY','x','a','t')")
    c.execute("INSERT INTO invoices(id,invoice_no,series,supplier_gstin,invoice_date,party_id,place_of_supply)"
              " VALUES ('I','G2/1/25','G2','g','2025-04-01','P','27')")
    raises(lambda: c.execute("UPDATE invoices SET party_id='P'"), "financial document")
    c.execute("UPDATE invoices SET status='CANCELLED', cancelled_on='2025-04-02'")
    c.execute("INSERT INTO accounts(code,name,type) VALUES ('X','x','ASSET')")
    c.execute("INSERT INTO journals(voucher_date,voucher_type,narration,posted_by,recorded_at)"
              " VALUES ('2025-04-01','JOURNAL','n','a','t')")
    raises(lambda: c.execute("INSERT INTO journal_lines(journal_no,line_no,account_code,dr_paise,cr_paise)"
                             " VALUES (1,1,'X',5,5)"), "CHECK constraint failed")   # single-sided lines only
    raises(lambda: c.execute("UPDATE journals SET narration='m'"), "append-only: journals")
    c.close()
    a = db.connect("audit", "audit_staff")
    a.execute("INSERT INTO engagements(id,entity_name,period_start,period_end,status)"
              " VALUES ('E','x','2025-04-01','2026-03-31','SIGNED_OFF')")
    a.execute("INSERT INTO findings(id,engagement_id,category,title,explanation,confidence,prepared_by,prepared_at)"
              " VALUES ('F-001','E','c','t','x','HIGH','aud','t')")
    raises(lambda: a.execute("UPDATE findings SET status='CONFIRMED'"), "signed off")
    a.execute("INSERT INTO risk_snapshots(run_id,at,object_type,object_id,R,band) VALUES ('r','t','COMPANY','SELF',61000,'MODERATE')")
    raises(lambda: a.execute("UPDATE risk_snapshots SET band='LOW'"), "append-only: risk_snapshots")
    a.execute("INSERT INTO sample_runs(id,engagement_id,kind,seed,size,as_of_seq,population_json,population_sha256,"
              "algo_version,run_by,run_at) VALUES ('R','E','SALES_TOD',?,30,0,'[]','x','v1','aud','t')",
              (str(2 ** 64 - 1),))                                           # a full 64-bit seed fits
    a.close()


def test_clock_and_units():
    config.set_clock("2026-03-31T20:00:00+00:00")       # 01:30 IST on 1 Apr belongs to April (05 D3)
    assert config.now() == "2026-04-01T01:30:00+05:30" and config.today() == "2026-04-01"
    config.set_clock(None)
    assert config.now().endswith("+05:30")
    with pytest.raises(ValueError):
        config.set_clock("31-03-2026")
    assert config.UNITS == seed.UNITS                    # seed should import config.UNITS (PROGRESS request)
    assert config.risk_weight("FORMAT_ONLY") == 0.2 and config.risk_weight("END_WINDOW_SHARE") == 0.5
    assert config.risk_weight("NOT_IN_SOR") == 1.0
