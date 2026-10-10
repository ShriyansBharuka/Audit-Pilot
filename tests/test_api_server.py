"""Tests for the AuditPilot AI REST API server."""
import json
import pytest
from starlette.testclient import TestClient

from app.api_server import app
from app import config


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["entity"] == "Konkan Marine Controls Ltd"


def test_api_identities(client):
    res = client.get("/api/identities")
    assert res.status_code == 200
    ids = res.json()
    assert len(ids) > 0
    roles = {i["role"] for i in ids}
    assert "engagement_partner" in roles
    assert "audit_staff" in roles


def test_api_overview(client):
    res = client.get("/api/audit/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["has_engagement"] is True
    assert data["invoices_count"] > 0
    assert data["revenue_paise"] > 0
    assert "₹" in data["revenue_formatted"]
    assert "D0" in data["detector_counts"]
    assert data["company_risk"]["band"] in ("HIGH", "REVIEW", "LOW")


def test_api_transactions(client):
    res = client.get("/api/audit/transactions?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    assert len(data["items"]) == 10
    item = data["items"][0]
    assert "invoice_no" in item
    assert "risk_score" in item
    assert "risk_band" in item


def test_api_transaction_detail(client):
    t_res = client.get("/api/audit/transactions?limit=1")
    inv_no = t_res.json()["items"][0]["invoice_no"]
    res = client.get(f"/api/audit/transactions/{inv_no}")
    assert res.status_code == 200
    data = res.json()
    assert data["invoice"]["invoice_no"] == inv_no
    assert len(data["lines"]) > 0


def test_api_risk_graph(client):
    res = client.get("/api/audit/risk-graph")
    assert res.status_code == 200
    data = res.json()
    assert len(data["cycles"]) > 0
    cycle = data["cycles"][0]
    assert len(cycle["nodes"]) >= 2
    assert cycle["amount_paise"] > 0


def test_api_shap_explanation(client):
    t_res = client.get("/api/audit/transactions?limit=1")
    inv_no = t_res.json()["items"][0]["invoice_no"]
    res = client.get(f"/api/audit/shap/{inv_no}")
    assert res.status_code == 200
    data = res.json()
    assert data["invoice_no"] == inv_no
    assert "shap_values" in data
    assert data["risk_score"] >= 0
    assert len(data["explanation_text"]) > 0


def test_api_findings_review_queue(client):
    res = client.get("/api/audit/findings")
    assert res.status_code == 200
    findings = res.json()
    assert len(findings) > 0
    f = findings[0]
    assert "detector" in f
    assert "gross_impact_paise" in f
    assert f["status"] in ("PROPOSED", "CONFIRMED", "REJECTED", "MODIFIED")


def test_api_partner_decision_unauthenticated(client):
    res = client.post(
        "/api/audit/findings/F-001/decide",
        json={"decision": "CONFIRM", "note": "Approved by auditor"},
    )
    assert res.status_code == 401


def test_api_powerbi_dataset(client):
    res = client.get("/api/integrations/powerbi")
    assert res.status_code == 200
    data = res.json()
    assert "invoices" in data
    assert "findings" in data
    assert len(data["invoices"]) > 0


def test_api_n8n_trigger(client):
    res = client.post(
        "/api/integrations/n8n/trigger",
        json={"workflow_name": "Test Workflow", "action": "test_action"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "RUNNING"
    assert "execution_id" in data
