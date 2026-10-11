"""ASSIST-2: the MCP gateway accepts Supabase web accounts for their organisations (X-Tenant). The role comes from that
organisation's tenant.json only; outsiders, web accounts on the demo company and the partner are refused; every call
runs against (and is trailed in) that organisation's own databases. Supabase itself is faked (no network)."""
import asyncio
import json
import socket
import threading
import time

import pytest
import uvicorn
from starlette.testclient import TestClient

from app import accounts, assistant, config, db, gateway, investigator, seed, tenants
import app.mcp_server  # noqa: F401  (registers the tools)
from app.api_server import app

JWT = {u: f"eyJhbGciOiJFUzI1NiJ9.{u}.sig" for u in ("aud", "cli", "ptn", "out")}
USERS = {JWT[u]: {"id": f"u-{u}", "email": f"{u}@example.in"} for u in JWT}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="module")
def org(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("mcptenants"))
    seed.load(seed.build_plan(30, 7), reset=True)
    t = tenants.create("Deccan Valves Pvt Ltd", "AAECD1234F", seed.make_gstin("27", "AAECD1234F"), "2025-26",
                       ["aud.judge"], "test")
    t["roles"] = {"sb:u-aud": "audit_staff", "sb:u-cli": "client_admin", "sb:u-ptn": "engagement_partner"}
    t["principals"] = sorted({*t["principals"], *t["roles"]})
    accounts._save(t)
    real = accounts.verify
    accounts.verify = lambda token: dict(USERS[token]) if token in USERS else (_ for _ in ()).throw(LookupError("bad"))
    port = _free_port()
    asgi = gateway.mcp.streamable_http_app(stateless_http=True, json_response=True, host="127.0.0.1",
                                           transport_security=gateway.TransportSecuritySettings(
                                               allowed_hosts=["127.0.0.1:*", "localhost:*"]))
    server = uvicorn.Server(uvicorn.Config(gateway.TokenInPath(gateway.TenantHeader(asgi)), host="127.0.0.1", port=port,
                                           log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    old = assistant.MCP_URL
    assistant.MCP_URL = f"http://127.0.0.1:{port}/mcp"
    yield t["slug"]
    assistant.MCP_URL = old
    accounts.verify = real
    server.should_exit = True
    th.join(timeout=5)
    config.set_data_dir(default)


def tools(token, slug):
    return {t["name"] for t in asyncio.run(assistant.list_tools(token, slug))}


def refused(token, slug):
    try:
        asyncio.run(assistant.list_tools(token, slug))
    except BaseException:  # noqa: BLE001  401 from the gateway surfaces as an exception group
        return True
    return False


def test_role_comes_from_the_organisation(org):
    aud, cli = tools(JWT["aud"], org), tools(JWT["cli"], org)
    assert "list_cases" in aud and "create_party" not in aud
    assert "create_party" in cli and "list_cases" not in cli


def test_outsiders_demo_company_and_partner_refused(org):
    assert refused(JWT["out"], org)                    # no role in this organisation
    assert refused(JWT["ptn"], org)                    # partner: web UI only, also for web accounts
    assert refused(JWT["aud"], None)                   # web accounts have no role on the demo company
    assert refused(JWT["aud"], "no-such-org")
    assert refused("ptn_test", None)                   # the agent partner token, as before
    assert "list_cases" in tools("aud_test", org)      # an agent token that is a member of this organisation
    assert refused("adm_test", org)                    # an agent token that is not


def test_calls_run_in_that_organisation(org):
    who = json.loads(asyncio.run(assistant.execute(JWT["cli"], "whoami", {}, org))["text"])
    assert who["summary"]["entity"] == "Deccan Valves Pvt Ltd" and who["summary"]["principal"] == "sb:u-cli"
    r = asyncio.run(assistant.execute(JWT["cli"], "create_party", {"name": "Tenant Only Pumps", "gstin": "27AAACT2727Q1ZW"}, org))
    assert r["ok"], r["text"]
    with db.borrow("erp", "audit_staff") as e:                                     # not in the demo company
        assert not e.execute("SELECT 1 FROM parties WHERE name = 'Tenant Only Pumps'").fetchone()
    with tenants.scope(org):
        with db.borrow("erp", "audit_staff") as e:
            assert e.execute("SELECT 1 FROM parties WHERE name = 'Tenant Only Pumps'").fetchone()
        with db.borrow("audit", "system") as a:                                    # trailed in the org's own file
            row = a.execute("SELECT principal, role, outcome FROM audit_trail WHERE tool = 'create_party'").fetchone()
    assert tuple(row) == ("sb:u-cli", "client_admin", "OK")


def test_assistant_supports_web_accounts(org, monkeypatch):
    monkeypatch.setattr(investigator, "ready", lambda: (True, "ready"))
    api = TestClient(app)
    s = api.get("/api/assistant/status", headers={"Authorization": f"Bearer {JWT['aud']}", "X-Tenant": org}).json()
    assert s["supported"] and s["mode"] == "tools"
    p = api.get("/api/assistant/status", headers={"Authorization": f"Bearer {JWT['ptn']}", "X-Tenant": org}).json()
    assert p["mode"] == "page_data"
