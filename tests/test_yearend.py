"""MT-6 (vault/13): the year-end view links every planted March document to what happened to it in April, the
timeline covers the period plus the subsequent-events window, and the freeze anchors both chains."""
import pytest
from starlette.testclient import TestClient

from app import analytics, config, db, plants, seed, yearend
from app.api_server import app

AUD = {"Authorization": "Bearer aud_test"}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("yearend"))
    plan = seed.build_plan(120, 7)
    plants.add_plants(plan, 7)
    ids = seed.load(plan, reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)
    yield ids
    config.set_clock(None)
    config.set_data_dir(default)


def test_planted_march_april_cases_all_appear(world):
    ids = world
    items = {i["march_doc"]["doc_id"]: i for i in yearend.march_april_links()["items"]}
    kinds = {k: {e["kind"] for e in items[ids[f"{k}/inv"]]["april_events"]} for k in ("PC1", "PC2", "PC3", "PI1", "PI2")}
    assert "LATE_DISPATCH" in kinds["PC1"]                      # invoiced 30 Mar, goods left 3 Apr
    assert "DELIVERED_AFTER_PERIOD" in kinds["PC2"]             # FOR destination, POD in April
    assert "ENTERED_AFTER_PERIOD" in kinds["PC3"]               # dated 25 Mar, keyed in 25 Apr
    assert kinds["PI1"] == {"CREDIT_NOTE"} and kinds["PI2"] == {"CREDIT_NOTE"}
    pi1 = items[ids["PI1/inv"]]
    assert pi1["april_events"][0]["id"] == ids["PI1/cn"]
    assert "POST_PERIOD_REVERSAL" in {h["code"] for h in pi1["hits"]} and pi1["affected_paise"] > 0
    assert ids["PP5/grn"] in items and items[ids["PP5/grn"]]["april_events"][0]["kind"] == "BILL_AFTER_PERIOD"


def test_timeline_months_and_party_filter(world):
    t = yearend.timeline()
    yms = [m["ym"] for m in t["months"]]
    assert yms[0] == "2025-04" and "2026-03" in yms and yms[-1] == "2026-05"
    march = next(m for m in t["months"] if m["ym"] == "2026-03")
    assert march["sales_paise"] > 0 and march["open_exceptions"] > 0 and not march["post_period"]
    april = next(m for m in t["months"] if m["ym"] == "2026-04")
    assert april["post_period"] and april["cn_paise"] > 0
    assert all(m["band"] in ("LOW", "MODERATE", "HIGH") for m in t["months"])
    one = yearend.timeline(party_id="P-0001")
    assert sum(m["sales_paise"] for m in one["months"]) < sum(m["sales_paise"] for m in t["months"])


def test_rest_and_freeze(world):
    api = TestClient(app)
    assert api.get("/api/yearend/timeline", headers=AUD).json()["months"]
    assert api.get("/api/yearend/march-april", headers=AUD).json()["items"]
    for tok in ("adm_test", "sal_test"):
        assert api.get("/api/yearend/timeline", headers={"Authorization": f"Bearer {tok}"}).status_code == 403
    assert api.post("/api/yearend/freeze", headers={"Authorization": "Bearer ptn_test"}).status_code == 403
    r = api.post("/api/yearend/freeze", headers=AUD).json()
    assert r["anchor"]["label"] == "PERIODIC" and r["snapshot_run"].startswith("RG-") and r["analytics_run"]
    with db.borrow("audit", "system") as a:
        assert a.execute("SELECT count(*) FROM anchors WHERE id = ?", (r["anchor"]["id"],)).fetchone()[0] == 1
