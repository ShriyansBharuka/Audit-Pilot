"""MT-3 (vault/13): the money trail keeps recorded, bank-verified, received and affected apart, labels every edge's
provenance, and never attributes a transfer beyond the traced documents."""
import pytest
from starlette.testclient import TestClient

from app import analytics, config, erp, money_trail, plants, seed
from app.api_server import app

ACC, ADM = ("acc.neha", "accounts"), ("adm.kiran", "client_admin")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("trail"))
    plan = seed.build_plan(120, 7)
    plants.add_plants(plan, 7)
    ids = seed.load(plan, reset=True)
    # a chain: the company pays vendor B Rs 10 L; C (same PAN as B, a group entity) pays the company Rs 8 L
    config.set_clock("2026-03-10T11:00:00+05:30")
    b = erp.create_party(*ADM, tags="VENDOR", name="Chain Vendor B", pan="AAACB4321K", bank_account="111122223333",
                         ifsc="HDFC0000111")["result"]["id"]
    c = erp.create_party(*ADM, tags="CUSTOMER", name="Chain Customer C", pan="AAACB4321K", bank_account="444455556666",
                         ifsc="HDFC0000444")["result"]["id"]
    pay = erp.record_payment(*ACC, vendor_id=b, amount_paise=10_00_000_00, settled_on="2026-03-10")["result"]
    config.set_clock("2026-03-12T11:00:00+05:30")
    erp.record_receipt(*ACC, party_id=c, amount_paise=8_00_000_00, settled_on="2026-03-12")
    config.set_clock("2026-10-05T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)
    yield ids, {"B": b, "C": c, "pay": pay}
    config.set_clock(None)
    config.set_data_dir(default)


def test_abc_case_keeps_the_three_numbers_apart(world):
    ids, _ = world
    r = money_trail.trace(ids["PP1/po"])
    n = r["numbers"]
    assert n["verified_paise"] == 5_00_000_00                      # the advance, on the bank line, to ABC's account
    assert n["received_paise"] == 3_00_000_00                      # 60 of 100 at the PO rate
    assert n["affected_paise"] == 2_00_000_00                      # SHORT_RECEIPT, not a loss
    assert n["recorded_paise"] == 5_00_000_00 and n["attribution"] == "NOT_ESTABLISHED"
    kinds = {(e["kind"], e["source"], e["status"]) for e in r["edges"]}
    assert {("PAYMENT_OUT", "BANK", "VERIFIED"), ("GOODS_RECEIPT", "BOOKS", "CLAIMED"), ("ORDER", "BOOKS", "CLAIMED"),
            ("BILL", "BOOKS", "CLAIMED")} <= kinds
    # the same chain from the GRN, the bill or the advance payment
    assert money_trail.trace(ids["PP1/grn"])["numbers"]["affected_paise"] == 2_00_000_00
    assert money_trail.trace(ids["PP1/adv"])["root"]["documents"]["purchase_order"] == [ids["PP1/po"]]


def test_wrong_beneficiary_is_not_verified(world):
    ids, _ = world
    r = money_trail.trace(ids["PP4/pay"])
    assert r["numbers"]["verified_paise"] == 0                     # the bank paid someone other than the vendor
    out = [e for e in r["edges"] if e["kind"] == "PAYMENT_OUT"]
    assert {(e["source"], e["status"]) for e in out} == {("BANK", "VERIFIED"), ("BOOKS", "CLAIMED")}
    assert any(e["to"].startswith("ACCT:") for e in out if e["source"] == "BANK")


def test_chain_shows_both_transfers_without_attribution(world):
    _, w = world
    r = money_trail.trace(w["pay"]["settlement_id"], hops=2)
    e = {(x["from"], x["to"], x["kind"]): x for x in r["edges"]}
    assert e[("SELF", w["B"], "PAYMENT_OUT")]["status"] == "VERIFIED" and e[("SELF", w["B"], "PAYMENT_OUT")]["hop"] == 1
    assert e[(w["B"], w["C"], "IDENTITY")]["status"] == "INFERRED"
    assert e[(w["C"], "SELF", "PAYMENT_IN")]["amount_paise"] == 8_00_000_00 and e[(w["C"], "SELF", "PAYMENT_IN")]["hop"] == 2
    assert r["numbers"]["verified_paise"] == 10_00_000_00         # the C transfer is context, never added
    assert not any(x["kind"] != "IDENTITY" and {x["from"], x["to"]} == {w["B"], w["C"]} for x in r["edges"])
    assert money_trail.trace(w["pay"]["settlement_id"], hops=1)["numbers"] == r["numbers"]


def test_unknown_object_and_rest_guards(world):
    ids, _ = world
    with pytest.raises(LookupError, match="NOT_FOUND"):
        money_trail.trace("NOPE-1")
    api = TestClient(app)
    ok = api.get(f"/api/money-trail/{ids['PP1/po']}", headers={"Authorization": "Bearer aud_test"})
    assert ok.status_code == 200 and ok.json()["numbers"]["affected_paise"] == 2_00_000_00
    assert api.get(f"/api/money-trail/{ids['PP1/po']}", headers={"Authorization": "Bearer adm_test"}).status_code == 403
    assert api.get("/api/money-trail/NOPE-1", headers={"Authorization": "Bearer aud_test"}).status_code == 404
