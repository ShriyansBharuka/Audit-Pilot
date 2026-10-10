"""DA-6 AuditGraph (05 §19): minimum-span decomposition, cycle classification on the synthetic network, the company
flag (clean -> LOW; plants -> HIGH with >= 4 families, planted items on top) and per-event updates."""
import json

import pytest

from app import analytics, config, db, erp, intake, risk_graph, seed

ACC, WHS, SAL = ("acc.neha", "accounts"), ("whs.ganesh", "warehouse"), ("sales.priya", "sales")
L = 1_00_000_00                                   # Rs 1 lakh in paise


def e(i, a, b, amount, ts, kind="T"):
    return {"id": i, "a": a, "b": b, "amount": amount, "ts": ts, "kind": kind}


def test_minimum_span_decomposition_spec_example():
    # 05 §19.4: A->B Rs 10 L, B->C Rs 9 L, C->A Rs 8 L gives circular Rs 8 L; residuals 2 / 1 / 0
    edges = [e("ab", "A", "B", 10 * L, "2026-01-01"), e("bc", "B", "C", 9 * L, "2026-01-05"),
             e("ca", "C", "A", 8 * L, "2026-01-09")]
    cycles, residual = risk_graph.decompose(edges, {}, start="A")
    assert len(cycles) == 1 and cycles[0]["circular"] == 8 * L and cycles[0]["members"] == ["A", "B", "C"]
    assert residual == {"ab": 2 * L, "bc": 1 * L, "ca": 0}
    assert [x["amount"] for x in edges] == [10 * L, 9 * L, 8 * L]             # the original history is untouched


def test_repeated_decomposition_and_time_order():
    edges = [e("ab1", "A", "B", 5 * L, "2026-01-01"), e("ab2", "A", "B", 4 * L, "2026-01-02"),
             e("ba", "B", "A", 7 * L, "2026-01-10")]
    cycles, residual = risk_graph.decompose(edges, {}, start="A")
    assert [c["circular"] for c in cycles] == [5 * L, 2 * L] and residual["ba"] == 0 and residual["ab2"] == 2 * L
    late = [e("ab", "A", "B", 5 * L, "2026-03-01"), e("ba", "B", "A", 5 * L, "2026-01-01")]   # money came back first
    assert risk_graph.decompose(late, {}, start="A")[0] == []
    far = [e("ab", "A", "B", 5 * L, "2026-01-01"), e("ba", "B", "A", 5 * L, "2026-06-01")]    # outside 90 days
    assert risk_graph.decompose(far, {}, start="A")[0] == []
    via = [e("ab", "A", "B", 5 * L, "2026-01-01"), e("ca", "C", "A", 5 * L, "2026-01-03")]   # B ~ X ~ C identity
    cyc = risk_graph.decompose(via, {"B": {"X"}, "X": {"B", "C"}, "C": {"X"}}, start="A")[0]
    assert cyc[0]["id_hops"] == 2 and cyc[0]["members"] == ["A", "B", "X", "C"]


@pytest.fixture(scope="module")
def network_world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("network"))
    plan = seed.build_plan(120, 7)
    seed.load(plan, reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    intake.on_client_upload(intake.submit("RP_LIST", seed.declared_rp_csv(plan).encode(), "rp.csv", "adm.kiran"))
    run = analytics.run_all(config.ENGAGEMENT_ID)
    yield plan, run, risk_graph.build(config.ENGAGEMENT_ID)
    config.set_clock(None)
    config.set_data_dir(default)


def test_network_cycles_are_classified(network_world):
    plan, run, g = network_world
    by = {tuple(c["members"]): c for c in g["cycles"]}
    goods = by[("SELF", "P-NET1", "P-NETD1", "P-NET2")]
    cash = by[("SELF", "P-NET2", "P-NETD1", "P-NETD2", "P-NET3")]
    job = by[("SELF", "P-VEN2")]
    assert goods["flagged"] and goods["codes"] == ["ROUND_TRIP_GOODS"] and goods["span_days"] == 18
    assert goods["circular_paise"] == min(s["taxable_paise"] for s in plan["sales"] if s["key"] == "S-N0001") or \
        goods["circular_paise"] == 390 * 435000
    assert cash["flagged"] and cash["codes"][0] == "ROUND_TRIP_CASH" and "MONEY_PATH" in cash["codes"]
    assert not job["flagged"] and job["codes"] == ["RECIPROCAL_EXPLAINED"]          # the false-positive control
    assert {"CIRCULAR_FLOW", "ROUND_TRIP_GOODS", "ROUND_TRIP_CASH"} <= set(run["counts"]["D10"])
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["P-NET1"]["band"] == "HIGH" and nodes["P-NET1"]["E"] >= 60 and nodes["P-NET1"]["C"] >= 0.9
    assert "J" in g["company"]["families"]
    with db.borrow("audit", "audit_staff") as a:
        snaps = a.execute("SELECT count(*) FROM risk_snapshots WHERE run_id LIKE 'RG-%'").fetchone()[0]
        assert snaps > 0
        with pytest.raises(Exception, match="append-only"):
            a.execute("UPDATE risk_snapshots SET band = 'LOW'")


@pytest.fixture()
def clean_world(world):
    plan = seed.build_plan(150, 7, network=False)
    seed.load(plan, reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    intake.on_client_upload(intake.submit("RP_LIST", seed.declared_rp_csv(plan).encode(), "rp.csv", "adm.kiran"))
    return plan


def test_clean_company_is_low_and_plants_make_it_high(clean_world):
    c0 = analytics.run_all(config.ENGAGEMENT_ID)["company"]
    assert c0["band"] == "LOW" and c0["families"] == [], c0

    def sale(qty=10, inv_date="2026-03-30", **kw):
        config.set_clock(f"{inv_date}T10:00:00+05:30")
        so = erp.create_sales_order(*SAL, party_id="P-0003", confirmed_on="2026-03-01",
                                    lines=[{"item_id": "IT-001", "qty": qty}])["result"]["id"]
        return erp.issue_invoice(*ACC, so_id=so, invoice_date=inv_date, **kw)["result"]
    p1 = sale()                                                           # C: premature (moves in April)
    config.set_clock("2026-04-03T10:00:00+05:30")
    erp.record_dispatch(*WHS, invoice_nos=[p1["id"]], moved_on="2026-04-03", lr_no="LR-X1")
    p2 = sale(qty=200)                                                    # D: no movement at all
    p3 = sale(irn=p1["irn"])                                              # F: copied IRN
    config.set_clock("2026-04-05T10:00:00+05:30")
    j = erp.post_journal_entry(*ACC, voucher_date="2026-03-31", narration="year end adjustment entry",   # G
                               lines=[{"account_code": "SUSPENSE", "dr_paise": 30 * L},
                                      {"account_code": "SALES", "cr_paise": 30 * L}])["result"]
    config.set_clock("2026-04-12T10:00:00+05:30")
    erp.issue_credit_note(*ACC, cn_date="2026-04-12", reason="RATE_DIFF",                                 # I
                          lines=[{"invoice_no": p2["id"], "taxable_paise": 5 * L}])
    config.set_clock("2026-10-05T10:00:00+05:30")
    c1 = analytics.run_all(config.ENGAGEMENT_ID)["company"]
    assert c1["band"] == "HIGH" and len(c1["families"]) >= 4 and {"C", "D", "F", "G", "I"} <= set(c1["families"])
    g = risk_graph.build(config.ENGAGEMENT_ID)
    top = [n["id"] for n in sorted((n for n in g["nodes"] if n["type"] == "invoice"), key=lambda n: -n["R"])[:20]]
    assert {p1["id"], p2["id"], p3["id"]} <= set(top[:10])
    assert all(n["R"] >= 60 for n in g["nodes"] if n["id"] in (p1["id"], p2["id"], p3["id"]))
    assert str(j["journal_no"]) in {h for h in _hit_objects()}


def _hit_objects():
    with db.borrow("audit", "audit_staff") as a:
        return [r[0] for r in a.execute("SELECT object_id FROM risk_hits WHERE detector = 'D7'")]


def test_on_event_updates_risk_per_document(clean_world):
    # year-round mode on the next, still-open year: FY 2026-27, after every seeded document
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute("UPDATE engagements SET period_start = '2026-04-01', period_end = '2027-03-31'")
    config.set_clock("2026-08-10T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)                               # baseline
    so = erp.create_sales_order(*SAL, party_id="P-0004", confirmed_on="2026-08-01",
                                lines=[{"item_id": "IT-001", "qty": 5}])["result"]["id"]
    inv = erp.issue_invoice(*ACC, so_id=so, invoice_date="2026-08-10")["result"]
    with db.borrow("audit", "audit_staff") as a:                          # fresh: dispatch and GSTR-1 not due yet
        assert a.execute("SELECT count(*) FROM risk_hits WHERE object_id = ?", (inv["id"],)).fetchone()[0] == 0
    # weeks later the goods have still not moved: the next commit for this customer re-runs the per-document
    # detectors and the invoice escalates
    config.set_clock("2026-09-05T10:00:00+05:30")
    erp.amend_record(*SAL, entity="parties", id="P-0004", changes={"phone": "9000000001"}, reason="new number")
    with db.borrow("audit", "audit_staff") as a:
        codes = {r[0] for r in a.execute("SELECT code FROM risk_hits WHERE object_id = ?", (inv["id"],))}
        assert "NO_MOVEMENT" in codes
        hist = [tuple(r) for r in a.execute("SELECT run_id, band FROM risk_snapshots WHERE object_type = 'INVOICE' AND"
                                            " object_id = ? ORDER BY rowid", (inv["id"],))]
        assert hist and hist[-1][1] == "HIGH" and hist[-1][0].startswith("EV-")
        ev = [json.loads(r[0]) for r in a.execute("SELECT payload_json FROM events WHERE kind = 'RISK_ESCALATED'")]
        assert any(p["object_id"] == inv["id"] for p in ev)
