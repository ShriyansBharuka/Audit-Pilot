"""EX-4: organisations as separate data directories. A token sees only its tenants, switching changes the overview,
tenant 2 data never shows under tenant 1, the tenant never grants a role, and the switch is per request (ContextVar)."""
import threading

import pytest
from starlette.testclient import TestClient

from app import analytics, config, db, erp, seed, tenants
from app.api_server import app

AUD = {"Authorization": "Bearer aud_test"}            # aud.judge: member of tenant 2
PTN = {"Authorization": "Bearer ptn_test"}            # ptn.mehta: not a member
ADM = {"Authorization": "Bearer adm_test"}            # Konkan's client admin


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("tenants"))
    seed.load(seed.build_plan(120, 7), reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)
    t2 = tenants.seed_demo(principals=["aud.judge"], invoices=40)
    with tenants.scope(t2["slug"]):
        config.set_clock("2026-10-05T10:00:00+05:30")
        erp.create_party("adm.kiran", "client_admin", name="Tenant Two Only Traders", gstin="27AAPFU0939F1ZV")
    yield t2
    config.set_clock(None)
    config.set_data_dir(default)


def test_token_sees_only_its_tenants(world):
    api = TestClient(app)
    slugs = lambda h: [t["slug"] for t in api.get("/api/tenants", headers=h).json()["items"]]
    assert slugs(AUD) == ["konkan", world["slug"]]
    assert slugs(PTN) == ["konkan"] and slugs(ADM) == ["konkan"]
    assert api.get("/api/audit/overview", headers={**PTN, "X-Tenant": world["slug"]}).status_code == 403
    assert api.get("/api/audit/overview", headers={**AUD, "X-Tenant": "no-such-org"}).status_code == 403
    # a tenant never grants a role: the client token stays a client everywhere
    assert api.get("/api/audit/overview", headers={**ADM, "X-Tenant": "konkan"}).status_code == 403


def test_switching_changes_overview_and_isolates_data(world):
    api = TestClient(app)
    one = api.get("/api/audit/overview", headers=AUD).json()
    two = api.get("/api/audit/overview", headers={**AUD, "X-Tenant": world["slug"]}).json()
    assert one["entity_name"] == "Konkan Marine Controls Ltd" and two["entity_name"] == "Sahyadri Shipyards Enterprises"
    assert one["invoices_count"] != two["invoices_count"] and two["engagement_id"] == world["engagement_id"]
    # (the Konkan seed also has a customer called Sahyadri Shipyards Enterprises, so compare the SELF party)
    with db.borrow("erp", "audit_staff") as e:                         # the default tenant's books
        names = {r[0] for r in e.execute("SELECT name FROM parties")}
        self1 = e.execute("SELECT name FROM parties WHERE id = 'SELF'").fetchone()[0]
    assert "Tenant Two Only Traders" not in names and self1 == "Konkan Marine Controls Ltd"
    with tenants.scope(world["slug"]), db.borrow("erp", "audit_staff") as e:
        names2 = {r[0] for r in e.execute("SELECT name FROM parties")}
        self2 = e.execute("SELECT name FROM parties WHERE id = 'SELF'").fetchone()[0]
    assert "Tenant Two Only Traders" in names2 and self2 == "Sahyadri Shipyards Enterprises"
    assert "Konkan Marine Controls Ltd" not in names2
    assert config.ENGAGEMENT_ID == "ENG-2025-26"                      # nothing leaked out of the request


def test_scope_is_per_thread(world):
    seen = {}

    def worker(slug, key):
        with tenants.scope(slug):
            for _ in range(200):
                seen.setdefault(key, set()).add(str(config.DB_PATHS["erp"]))

    ts = [threading.Thread(target=worker, args=(s, s)) for s in ("konkan", world["slug"])]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(seen["konkan"]) == 1 and len(seen[world["slug"]]) == 1 and seen["konkan"] != seen[world["slug"]]


def test_new_organisation_validation(world):
    api = TestClient(app)
    good = {"name": "Deccan Valves Pvt Ltd", "pan": "AAECD1234F", "gstin": seed.make_gstin("27", "AAECD1234F"),
            "fy": "2026-27"}
    assert api.post("/api/tenants", json={**good, "pan": "BAD"}, headers=AUD).status_code == 400
    assert api.post("/api/tenants", json={**good, "gstin": "27AAECD1234F1Z0"}, headers=AUD).status_code == 400
    assert api.post("/api/tenants", json={**good, "fy": "2026-28"}, headers=AUD).status_code == 400
    assert api.post("/api/tenants", json=good, headers=ADM).status_code == 403
    r = api.post("/api/tenants", json=good, headers=PTN)
    assert r.status_code == 200 and r.json()["invoices_count"] == 0 and r.json()["period_start"] == "2026-04-01"
    slug = r.json()["slug"]
    assert slug in [t["slug"] for t in api.get("/api/tenants", headers=PTN).json()["items"]]
    assert slug not in [t["slug"] for t in api.get("/api/tenants", headers=AUD).json()["items"]]
    ov = api.get("/api/audit/overview", headers={**PTN, "X-Tenant": slug}).json()
    assert ov["entity_name"] == "Deccan Valves Pvt Ltd" and ov["invoices_count"] == 0
