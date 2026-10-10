"""REST API for the Next.js app (app/api_server.py): token-bound roles, real data, exact SHAP."""
import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app import config, db, demo_audit, explain, plants, seed
from app.api_server import app

AUD = {"Authorization": "Bearer aud_test"}
PTN = {"Authorization": "Bearer ptn_test"}
ADM = {"Authorization": "Bearer adm_test"}
SAL = {"Authorization": "Bearer sal_test"}


@pytest.fixture(scope="module")
def client():
    """A small audited company (planted year, doctored register, analytics, AuditGraph) in a temp data dir."""
    default = config.DATA_DIR
    config.set_data_dir(Path(tempfile.mkdtemp(prefix="auditpilot-api-")))
    db.init_all(reset=True)
    plan = seed.build_plan(200, 7)
    stubs = plants.add_plants(plan, 7)
    ids = seed.load(plan, True)
    plants.write_answer_key(config.DATA_DIR / "answer_key.json",
                            plants.resolve(stubs, ids) + plants.network_and_list_plants(ids))
    (config.DATA_DIR / "rp_list_demo.csv").write_text(plants.demo_rp_csv(plan), encoding="utf-8")
    demo_audit.run()
    yield TestClient(app)
    config.set_clock(None)
    config.set_data_dir(default)


def test_health_is_public(client):
    assert client.get("/api/health").json()["status"] == "healthy"


def test_identities_never_hand_out_tokens(client, monkeypatch):
    ids = client.get("/api/identities").json()
    assert ids and all(i["token"] is None for i in ids)
    monkeypatch.setenv("DEMO_ROLE_SWITCHER", "1")
    ids = client.get("/api/identities").json()
    assert all(i["token"] is None for i in ids if i["role"] == "engagement_partner")
    assert any(i["token"] for i in ids if i["role"] == "audit_staff")


def test_audit_endpoints_need_an_audit_token(client):
    for path in ("/api/audit/overview", "/api/audit/transactions", "/api/audit/findings", "/api/audit/trail",
                 "/api/audit/risk-graph", "/api/integrations/powerbi", "/api/audit/shap-summary"):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers=SAL).status_code == 403, path          # the client never sees audit data
        assert client.get(path, headers=AUD).status_code == 200, path


def test_overview_and_transactions(client):
    o = client.get("/api/audit/overview", headers=AUD).json()
    assert o["has_engagement"] and o["invoices_count"] > 0 and o["company_risk"]["band"] in ("HIGH", "MODERATE", "LOW")
    t = client.get("/api/audit/transactions?limit=10", headers=AUD).json()
    assert t["total"] > 0 and len(t["items"]) == 10
    d = client.get(f"/api/audit/transactions/{t['items'][0]['invoice_no']}", headers=AUD).json()
    assert d["invoice"]["invoice_no"] == t["items"][0]["invoice_no"] and d["lines"]


def test_shap_is_exact_on_every_flagged_invoice(client):
    s = client.get("/api/audit/shap-summary", headers=AUD).json()
    assert s["invoices"] > 0 and s["features"]
    with db.borrow("audit", "system") as a:
        flagged = [r[0] for r in a.execute("SELECT DISTINCT object_id FROM risk_snapshots WHERE object_type = 'INVOICE'"
                                           " AND R >= 30000")]
    for iid in flagged:
        x = client.get(f"/api/audit/shap/{iid}", headers=AUD).json()
        assert x["check"]["exact"], iid
        assert abs(sum(x["shap_values"].values()) - x["risk_score"]) < 0.05, iid
        assert abs(x["risk_score"] - x["stored_risk_score"]) <= 1, iid           # same formula as AuditGraph
    assert client.get("/api/audit/shap/NOPE", headers=AUD).status_code == 404


def test_evidence_upload_is_client_only(client):
    reqs = client.get("/api/audit/evidence/requests", headers=ADM).json()
    files = {"file": ("lr.txt", b"LR No: LR-1\n", "text/plain")}
    assert client.post("/api/audit/evidence/submit", data={"request_id": "x"}, files=files).status_code == 401
    assert client.post("/api/audit/evidence/submit", data={"request_id": "x"}, files=files, headers=AUD).status_code == 403
    if reqs:
        r = client.post("/api/audit/evidence/submit", data={"request_id": reqs[0]["id"]}, files=files, headers=ADM)
        assert r.status_code == 200 and r.json()["kind"] == "EVIDENCE"


def test_partner_actions_need_the_partner(client):
    body = {"decision": "CONFIRM", "note": "ok"}
    assert client.post("/api/audit/findings/F-001/decide", json=body).status_code == 401
    assert client.post("/api/audit/findings/F-001/decide", json=body, headers=AUD).status_code == 403


def test_n8n_events_feed_is_real(client):
    r = client.get("/api/integrations/n8n/events", headers=AUD).json()
    assert {"REGISTER_UPLOADED"} <= {e["kind"] for e in r["events"]}
    assert r["webhook_configured"] is False


def test_shapley_on_known_games():
    # additive game: each player gets its own weight; symmetric max game: equal split; efficiency always holds
    w = [3.0, 5.0, 7.0]
    assert [round(x, 9) for x in explain.shapley(3, lambda s: sum(w[i] for i in s))] == w
    phi = explain.shapley(2, lambda s: 10.0 if s else 0.0)
    assert phi == [5.0, 5.0]
    floor = explain.shapley(3, lambda s: max(sum(w[i] for i in s), 12.0 if 0 in s else 0.0))
    assert abs(sum(floor) - 15.0) < 1e-9


def test_deliverables_download(client):
    r = client.get("/api/audit/deliverables/workpaper", headers=AUD)
    assert r.status_code == 200 and r.content[:2] == b"PK" and r.headers["X-Content-SHA256"]
    m = client.get("/api/audit/deliverables/memo", headers=AUD).json()
    assert "DRAFT" in m["memo"] and m["sha256"]
