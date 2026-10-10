"""MT-4 (vault/13): one case per root cause, the three numbers kept apart, actions append to an append-only history,
and the client can never see a case."""
import sqlite3

import pytest
from starlette.testclient import TestClient

from app import analytics, cases, config, db, plants, seed
from app.api_server import app

AUD = {"Authorization": "Bearer aud_test"}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("cases"))
    plan = seed.build_plan(120, 7)
    plants.add_plants(plan, 7)
    ids = seed.load(plan, reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    run = analytics.run_all(config.ENGAGEMENT_ID)
    yield ids, run
    config.set_clock(None)
    config.set_data_dir(default)


def by_root(root_type, root_id):
    return next(c for c in cases.list_cases(limit=100)["items"] if (c["root_type"], c["root_id"]) == (root_type, root_id))


def test_one_case_per_root_cause(world):
    ids, run = world
    assert run["cases"]["active"] and run["cases"]["new"]
    items = cases.list_cases(limit=100)["items"]
    roots = [(c["root_type"], c["root_id"]) for c in items]
    assert len(roots) == len(set(roots))
    # several codes on one invoice are one case
    assert any({"NO_MOVEMENT", "EWB_REQUIRED_MISSING"} <= set(c["codes"]) for c in items)
    # the ABC purchase chain (PO, GRN, bill) is one case with the money-trail numbers
    abc = by_root("purchase_order", ids["PP1/po"])
    assert "SHORT_RECEIPT" in abc["codes"] and abc["verified_paise"] == 5_00_000_00 and abc["affected_paise"] == 2_00_000_00
    # a D10 cycle folds into a party case, never one case per cycle invoice
    cyc = [c for c in items if c["root_type"] == "invoice" and set(c["codes"]) <= {"ROUND_TRIP_GOODS", "ROUND_TRIP_CASH",
                                                                                   "MONEY_PATH", "CIRCULAR_FLOW"}]
    assert not cyc
    assert all("ABC" not in c["title"] for c in items)                # titles cite codes and ids only


def test_rebuild_is_idempotent(world):
    before = {c["case_id"]: (c["root_type"], c["root_id"]) for c in cases.list_cases(limit=100)["items"]}
    assert cases.rebuild()["new"] == []
    after = {c["case_id"]: (c["root_type"], c["root_id"]) for c in cases.list_cases(limit=100)["items"]}
    assert before == after


def test_actions_append_history(world):
    ids, _ = world
    abc = by_root("purchase_order", ids["PP1/po"])["case_id"]
    with pytest.raises(ValueError, match="needs a note"):
        cases.act(abc, "EXPLAINED", "", "aud.meera", "audit_staff")
    with pytest.raises(PermissionError):
        cases.act(abc, "ESCALATE", "x", "ptn.rao", "engagement_partner")
    r = cases.act(abc, "REQUEST_EVIDENCE", None, "aud.meera", "audit_staff", doc_kind="LR")
    assert r["case"]["status"] == "EVIDENCE_REQUESTED"
    with db.borrow("pbc", "system") as pb:
        req = pb.execute("SELECT * FROM evidence_requests WHERE id = ?", (r["event"]["payload"]["request_id"],)).fetchone()
    assert req["sample_ref"] == abc and req["doc_kind"] == "LR"
    ul = by_root("purchase_order", ids["PP5/po"])["case_id"]
    r = cases.act(ul, "PROPOSE_ADJUSTMENT", "accrue at year end", "aud.meera", "audit_staff",
                  aje_lines=[{"account_code": "PURCHASES", "dr_paise": 90_000_00},
                             {"account_code": "CREDITORS", "party_id": "P-VEN5", "cr_paise": 90_000_00}])
    fid = r["event"]["payload"]["finding_id"]
    with db.borrow("audit", "system") as a:
        f = a.execute("SELECT * FROM findings WHERE id = ?", (fid,)).fetchone()
    assert f["status"] == "PROPOSED" and f["gross_impact_paise"] == 90_000_00
    with pytest.raises(ValueError, match="balanced|INVALID"):
        cases.act(ul, "PROPOSE_ADJUSTMENT", None, "aud.meera", "audit_staff",
                  aje_lines=[{"account_code": "PURCHASES", "dr_paise": 1}])
    hist = cases.get_case(abc)["history"]
    assert [h["action"] for h in hist] == ["OPENED", "REQUEST_EVIDENCE"]
    with db.borrow("audit", "system") as a, pytest.raises(sqlite3.DatabaseError, match="append-only"):
        a.execute("UPDATE case_events SET note = 'x'")
    assert cases.rebuild()["new"] == [] and by_root("purchase_order", ids["PP1/po"])["status"] == "EVIDENCE_REQUESTED"


def test_get_case_and_rest_guards(world):
    ids, _ = world
    api = TestClient(app)
    lst = api.get("/api/cases?limit=5", headers=AUD).json()
    assert lst["total"] >= 5 and len(lst["items"]) == 5
    cid = by_root("purchase_order", ids["PP1/po"])["case_id"]
    d = api.get(f"/api/cases/{cid}", headers=AUD).json()
    assert d["numbers"]["verified_paise"] == 5_00_000_00 and d["numbers"]["attribution"] == "NOT_ESTABLISHED"
    assert {x["status"] for x in d["money_trail"]["edges"]} >= {"VERIFIED", "CLAIMED"} and d["documents"]
    assert "not a loss" in d["explanation"] and d["suggested_action"]
    for tok in ("adm_test", "sal_test"):
        h = {"Authorization": f"Bearer {tok}"}
        assert api.get("/api/cases", headers=h).status_code == 403
        assert api.get(f"/api/cases/{cid}", headers=h).status_code == 403
    assert api.post(f"/api/cases/{cid}/action", json={"action": "ESCALATE", "note": "x"},
                    headers={"Authorization": "Bearer ptn_test"}).status_code == 403
    ok = api.post(f"/api/cases/{cid}/action", json={"action": "ESCALATE", "note": "vendor unreachable"}, headers=AUD)
    assert ok.status_code == 200 and ok.json()["case"]["status"] == "ESCALATED"
    assert api.post(f"/api/cases/{cid}/action", json={"action": "DELETE"}, headers=AUD).status_code == 400
    assert api.get("/api/cases/AUD-9999", headers=AUD).status_code == 404
