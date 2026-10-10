"""End-to-end self-check: python -m app.selftest [--keep] (07 §8.6).

Runs in a throwaway data dir, so it never touches data/. Today it proves the platform (schema, role-bound handles,
append-only guards, clock), checks every 07 §4 contract signature, smoke-tests the pure cores that already exist,
and lists the 07 §8.6 end-to-end steps, marked SKIP while the module that owns each one is still a STUB.
SH-6 fills the E2E steps in as the queue lands. Exit code 1 if anything FAILs.
"""
import importlib
import inspect
import random
import shutil
import sqlite3
import sys
import tempfile
import traceback

from app import config

RESULTS = []


def step(name):
    def deco(fn):
        try:
            out = fn()
            RESULTS.append(("SKIP" if isinstance(out, str) and out.startswith("SKIP") else "PASS", name,
                            out if isinstance(out, str) else ""))
        except Exception as e:  # noqa: BLE001 - a selftest reports every failure and carries on
            RESULTS.append(("FAIL", name, f"{type(e).__name__}: {e}"))
            if "-v" in sys.argv:
                traceback.print_exc()
        return fn
    return deco


def expect_error(fn, *fragments):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        assert all(f in msg for f in fragments), f"wrong error: {msg!r}"
        return
    raise AssertionError(f"expected an error containing {fragments}")

# ---------------------------------------------------------------- contracts (07 §4)

ACTOR = ("actor", "role")
CONTRACTS = {
    "db": {"connect": ("db", "role"), "init_all": ("reset",), "tx": ("conn",)},
    "chain": {"append": ("conn", "table", "row"), "verify": ("conn", "table", "anchors")},
    "money": {"to_paise": ("s",), "fmt_inr": ("paise",), "tax_split": ("taxable_paise", "rate_bp", "inter_state")},
    "ledger": {"post_journal": ("conn", "voucher_date", "voucher_type", "lines", "narration", "actor", "role", "tool",
                                "source_type", "source_id", "reverses_no", "aje_ref"),
               "reverse_journal": ("conn", "journal_no", "date", "actor", "role", "tool", "reason"),
               "trial_balance": ("conn", "upto"), "seed_coa": ("conn",)},
    "erp": {"write_doc": ("conn", "actor", "role", "tool", "action", "doc_type", "doc_id", "reason"),
            **{s: ACTOR for s in ("create_party", "link_parties", "create_item", "create_lead", "create_scheme",
                                  "create_sales_order", "issue_invoice", "generate_eway_bill", "record_dispatch",
                                  "record_delivery", "issue_credit_note", "record_receipt", "record_payment",
                                  "record_purchase", "post_journal_entry", "file_gstr1", "file_gstr3b", "amend_record",
                                  "cancel_document", "import_records", "export_sales_register", "render_document")}},
    "portal": {"register_irn": ("supplier_gstin", "fy", "doc_type", "doc_no", "doc_date", "buyer_gstin",
                                "taxable_paise", "tax_paise"),
               "cancel_irn": ("irn",), "generate_eway_bill": (), "cancel_eway_bill": ("ewb_no",),
               "file_gstr1": ("gstin", "period", "omit", "changes"), "file_gstr3b": ("gstin", "period", "figures"),
               "bank_txn": ("account_no", "value_date", "amount_paise", "cp_name", "cp_account", "cp_ifsc", "utr",
                            "narration"),
               "verify_signature": ("einvoice_row",)},
    "trail": {"trail": ("principal", "role", "tool", "args", "outcome", "result", "transport"),
              "anchor": ("engagement_id", "label")},
    "notify": {"emit": ("kind", "payload", "engagement_id")},
    "intake": {"submit": ("kind", "content", "filename", "submitted_by", "request_id", "declared"),
               "on_client_upload": ("submission_id",)},
    "register": {"parse_verbatim": ("content", "filename"), "map_columns": ("headers",),
                 "reconcile": ("engagement_id",)},
    "related_parties": {"run_d1_d2": ("engagement_id",), "rp_status": ("party_id", "on_date")},
    "analytics": {"run_all": ("engagement_id", "detectors", "incremental")},
    "sampling": {"select": ("engagement_id", "kind", "size", "seed", "actor"), "reproduce": ("run_id",),
                 "pps": ("items", "k", "rng")},
    "risk_graph": {"build": ("engagement_id",)},
    "findings": {"from_hits": ("engagement_id",), "aje": ("finding",), "sa450_summary": ("engagement_id",)},
    "evidence": {"extract": ("submission_id",), "test_sample": ("run_id", "sample_no", "actor", "note"),
                 "bundle": ("invoice_id",), "check_for_changes": ("engagement_id",),
                 "verify_integrity": ("engagement_id",)},
    "workpaper": {"build": ("engagement_id",)},
    "memo": {"build": ("engagement_id",)},
}
OTHER_MODULES = ("config", "playbook", "gateway", "tools_client", "tools_audit", "mcp_server", "investigator", "seed")


def mod(name):
    return importlib.import_module(f"app.{name}")


def is_stub(name):
    return getattr(mod(name), "STUB", False)


def _params(fn):
    ps = [p for p in inspect.signature(fn).parameters.values() if p.kind not in (p.VAR_KEYWORD, p.VAR_POSITIONAL)]
    return ps


def check_signature(module, fname, want):
    fn = getattr(mod(module), fname, None)
    assert callable(fn), f"{module}.{fname} missing"
    ps = _params(inspect.unwrap(fn))
    got = tuple(p.name for p in ps[:len(want)])
    assert got == want, f"{module}.{fname}{got} != contract {want}"
    extra = [p.name for p in ps[len(want):] if p.default is inspect.Parameter.empty]
    assert not extra, f"{module}.{fname} has extra required params {extra}"

# ---------------------------------------------------------------- steps

def run():
    from app import db

    @step("imports: every app module loads")
    def _():
        for m in list(CONTRACTS) + list(OTHER_MODULES):
            mod(m)
        stubs = sorted(m for m in list(CONTRACTS) + list(OTHER_MODULES) if is_stub(m))
        return f"stubs: {', '.join(stubs)}" if stubs else ""

    @step("contracts: 07 §4 signatures")
    def _():
        n = 0
        for module, fns in CONTRACTS.items():
            for fname, want in fns.items():
                check_signature(module, fname, want)
                n += 1
        return f"{n} functions"

    @step("SH-2 init_all(reset=True): 4 databases, every 03 table, WAL")
    def _():
        db.init_all(reset=True)
        want = {"erp": 20, "ext": 6, "pbc": 3, "audit": 13}
        for name, n in want.items():
            c = sqlite3.connect(str(config.DB_PATHS[name]))
            tables = c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            mode = c.execute("PRAGMA journal_mode").fetchone()[0]
            c.close()
            assert tables == n, f"{name}.db has {tables} tables, 03 lists {n}"
            assert mode == "wal", f"{name}.db journal_mode={mode}"
        db.init_all(reset=False)                               # idempotent re-run
        return "erp 20 · ext 6 · pbc 3 · audit 13"

    @step("SH-2 independence: audit role cannot write erp/ext (readonly database)")
    def _():
        for name, sql in (("erp", "INSERT INTO accounts(code,name,type) VALUES ('X','x','ASSET')"),
                          ("ext", "INSERT INTO bank_txns(id,account_no,value_date,amount_paise) VALUES ('B','1','2025-04-01',1)")):
            for role in ("audit_staff", "engagement_partner", "system"):
                c = db.connect(name, role)
                expect_error(lambda: c.execute(sql), "readonly database")
                c.close()

    @step("SH-2 independence: client roles have no audit.db handle; orchestrator none on erp.db")
    def _():
        for role in ("sales", "warehouse", "accounts", "client_admin", "portal"):
            expect_error(lambda: db.connect("audit", role), "PERMISSION_DENIED")
        expect_error(lambda: db.connect("erp", "orchestrator"), "PERMISSION_DENIED")
        expect_error(lambda: db.connect("erp", "hacker"), "PERMISSION_DENIED")
        c = db.connect("audit", "orchestrator")
        expect_error(lambda: c.execute("INSERT INTO events(kind,at) VALUES ('SIGNED_OFF','x')"), "readonly")
        c.close()

    @step("SH-2 writers: client writes erp, portal writes ext, tx() rolls back on error")
    def _():
        c = db.connect("erp", "client_admin")
        try:
            with db.tx(c):
                c.execute("INSERT INTO accounts(code,name,type) VALUES ('ZZ_SELFTEST','x','ASSET')")
                raise RuntimeError("rollback")
        except RuntimeError:
            pass
        assert c.execute("SELECT count(*) FROM accounts WHERE code='ZZ_SELFTEST'").fetchone()[0] == 0
        c.close()
        p = db.connect("ext", "portal")
        with db.tx(p):
            p.execute("INSERT INTO bank_txns(id,account_no,value_date,amount_paise) VALUES ('B-ST','1','2025-04-01',-5)")
        p.close()
        c = db.connect("ext", "client_admin")
        expect_error(lambda: c.execute("DELETE FROM bank_txns"), "readonly database")
        c.close()

    @step("SH-2 guards: append-only + [F] triggers abort")
    def _():
        c = db.connect("erp", "client_admin")
        with db.tx(c):
            c.execute("INSERT INTO erp_log(recorded_at,actor,role,tool,action,doc_type,doc_id,after_json,prev_hash,hash)"
                      " VALUES ('t','a','r','t','CREATE','x','1','{}','p0','h1')")
            c.execute("INSERT INTO parties(id,kind,name,recorded_by,recorded_at) VALUES ('P-ST','ENTITY','x','a','t')")
            c.execute("INSERT INTO invoices(id,invoice_no,series,supplier_gstin,invoice_date,party_id,place_of_supply)"
                      " VALUES ('I-ST','G2/1/25','G2','g','2025-04-01','P-ST','27')")
        expect_error(lambda: c.execute("UPDATE erp_log SET actor='b'"), "append-only: erp_log")
        expect_error(lambda: c.execute("DELETE FROM erp_log"), "append-only: erp_log")
        expect_error(lambda: c.execute("UPDATE invoices SET invoice_date='2025-04-02'"), "financial document")
        expect_error(lambda: c.execute("DELETE FROM invoices"), "never deleted")
        c.execute("UPDATE invoices SET status='CANCELLED', cancelled_on='2025-04-02'")   # cancel is allowed
        c.close()
        a = db.connect("audit", "audit_staff")
        a.execute("INSERT INTO audit_trail(at,principal,role,transport,tool,outcome,prev_hash,hash)"
                  " VALUES ('t','p','audit_staff','SYSTEM','whoami','OK','p0','h1')")
        expect_error(lambda: a.execute("UPDATE audit_trail SET tool='x'"), "append-only: audit_trail")
        expect_error(lambda: a.execute("DELETE FROM audit_trail"), "append-only: audit_trail")
        a.close()
        db.init_all(reset=True)                                    # leave a clean world for the steps below

    @step("config: settable clock in IST, unit master, risk weights")
    def _():
        config.set_clock("2026-03-31T23:30:00+05:30")
        assert config.now() == "2026-03-31T23:30:00+05:30" and config.today() == "2026-03-31"
        config.set_clock("2026-03-31T20:00:00+00:00")             # 01:30 IST on 1 Apr is April (05 D3, C7)
        assert config.today() == "2026-04-01"
        config.set_clock(None)
        assert config.now().endswith("+05:30")
        from app.related_parties import gstin_ok
        assert all(gstin_ok(u["gstin"]) and u["gstin"][2:12] == config.SELF_PAN for u in config.UNITS.values())
        assert config.risk_weight("FORMAT_ONLY") == 0.2 and config.risk_weight("NO_MOVEMENT") == 1.0

    @step("pure cores: seed plan -> D1/D2 analyse, register parse + D0")
    def _():
        from app import register, related_parties, seed
        plan = seed.build_plan(50, 7)
        res = related_parties.analyse(plan["parties"], plan["links"], [], config.PERIOD_START, config.PERIOD_END)
        und = [h for h in res["hits"] if h["code"] == "UNDISCLOSED_RP"]
        assert und, "undeclared group companies should surface when the RP list is empty"
        headers, rows = register.parse_verbatim(b"Bill no.,Date,Total Cost\nG2/1/25,01-04-2025,100\n", "r.csv")
        hits, _p = register.diff_register([register.map_row(headers, r) for r in rows], [], *(
            config.PERIOD_START, config.PERIOD_END))
        assert [h["code"] for h in hits] == ["NOT_IN_SOR"]
        return f"{len(plan['parties'])} parties, {len(und)} undisclosed with an empty RP list"

    @step("stubs return their contract shapes")
    def _():
        checks = {
            "analytics": lambda m: set(m.run_all("E")) >= {"counts", "top"},
            "sampling": lambda m: set(m.select("E", "sales_tod")) >= {"run_id", "seed", "items"}
                                  and isinstance(m.pps([("I1", 1)], 1, random.Random(1)), list),
            "evidence": lambda m: set(m.verify_integrity("E")) >= {"ok", "checks"}
                                  and set(m.check_for_changes("E")) >= {"changes", "stale_samples"},
            "risk_graph": lambda m: set(m.build("E")) >= {"nodes", "edges", "cycles", "company"},
            "workpaper": lambda m: set(m.build("E")) >= {"path", "sha256", "download_key"},
            "memo": lambda m: set(m.build("E")) >= {"path", "sha256", "download_key"},
            "findings": lambda m: isinstance(m.from_hits("E"), list),
        }
        done = []
        for name, ok in checks.items():
            if is_stub(name):
                assert ok(mod(name)), f"{name} stub shape"
                done.append(name)
        return f"checked: {', '.join(done)}" if done else "no stubs left"

    @step("ERP: one sale end to end (SO -> invoice/IRN -> EWB -> dispatch -> POD -> GSTR-1 -> receipt), trace has no gaps")
    def _():
        from app import erp
        if is_stub("erp"):
            return "SKIP (stub: erp)"
        A, W, C = ("acc.neha", "accounts"), ("whs.ganesh", "warehouse"), ("adm.kiran", "client_admin")
        config.set_clock("2026-03-01T10:00:00+05:30")
        erp.create_party(*C, id="SELF", tags="SELF", name=config.ENTITY_NAME, gstin=config.UNITS["G2"]["gstin"],
                         bank_account="50100012345678", ifsc="HDFC0001234")
        erp.create_party(*C, id="P-0001", name="Selftest Customer Pvt Ltd", gstin="27AAPFU0939F1ZV", pincode="400001")
        erp.create_item(*C, id="IT-001", name="Valve", hsn="8481", list_rate_paise=680000)
        so = erp.create_sales_order("sales.priya", "sales", party_id="P-0001", confirmed_on="2026-03-05",
                                    lines=[{"item_id": "IT-001", "qty": 10}])["result"]["id"]
        inv = erp.issue_invoice(*A, so_id=so, invoice_date="2026-03-28")["result"]
        ewb = erp.generate_eway_bill(*W, invoice_id=inv["id"], vehicle_no="MH08AB1234", distance_km=300)["result"]
        mv = erp.record_dispatch(*W, invoice_nos=[inv["invoice_no"]], moved_on="2026-03-28", lr_no="LR-1",
                                 ewb_no=ewb["ewb_no"])["result"]["id"]
        erp.record_delivery(*W, movement_id=mv, delivered_on="2026-03-29")
        config.set_clock("2026-04-11T10:00:00+05:30")
        erp.file_gstr1(*A, period="202603")
        erp.record_receipt(*A, amount_paise=inv["total_paise"], invoice_nos=[inv["id"]], settled_on="2026-04-20")
        config.set_clock(None)
        gaps = erp.trace_sale("audit_staff", inv["invoice_no"])["gaps"]
        assert gaps == [], gaps
        db.init_all(reset=True)
        return inv["invoice_no"]

    # 07 §8.6 end to end, in order; each step needs the listed modules to be real
    e2e = [("seed 300 invoices through erp services", ("erp", "ledger", "portal", "chain")),
           ("export register (Fig. 1) + doctored upload", ("erp", "intake")),
           ("D0 reconcile + D1/D2 on the frozen register", ("intake",)),
           ("run_analytics", ("analytics",)),
           ("select_samples x3 + reproduce identical", ("sampling", "trail")),
           ("render/upload evidence (one forged) -> test_sample flags it", ("evidence",)),
           ("amend LR date after testing -> check_for_changes names the sample", ("evidence", "erp")),
           ("verify_integrity clean, then out-of-band edit detected", ("evidence", "chain")),
           ("findings + AJEs, workpaper xlsx, memo", ("findings", "workpaper", "memo")),
           ("risk graph: company band", ("risk_graph",)),
           ("partner confirm + sign-off; verify_trail OK", ("trail", "findings"))]
    for name, owners in e2e:
        stubs = [o for o in owners if is_stub(o)]

        @step(f"E2E: {name}")
        def _(stubs=stubs):
            return f"SKIP (stub: {', '.join(stubs)})" if stubs else "SKIP (SH-6 wires this step)"


def main():
    keep = "--keep" in sys.argv
    tmp = tempfile.mkdtemp(prefix="auditpilot-selftest-")
    config.set_data_dir(tmp)
    try:
        run()
    finally:
        config.set_clock(None)
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    width = max(len(n) for _, n, _ in RESULTS)
    for status, name, note in RESULTS:
        print(f"{status:<4}  {name:<{width}}  {note}")
    counts = {s: sum(1 for r in RESULTS if r[0] == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"\nselftest: {counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped"
          f"{f'  (data kept in {tmp})' if keep else ''}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
