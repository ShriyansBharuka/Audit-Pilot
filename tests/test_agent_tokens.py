"""Agent tokens: a web account connects an AI agent over MCP to its own organisation. The token is shown once and
stored hashed; a partner's agent is audit_staff (sign-off stays human); a revoked token or a removed member stops
working; and the MCP server, given the token, runs against that organisation's books (not the demo company)."""
import asyncio
import json
import os
import sys

import pytest
from starlette.testclient import TestClient

from app import accounts, agent_tokens, config, gateway, seed, tenants
from app.api_server import app

USERS = {"eyP.partner.sig": {"id": "u-partner", "email": "partner@firm.in"},
         "eyC.client.sig": {"id": "u-client", "email": "cfo@client.in"}}
H = lambda tok, slug=None: {"Authorization": f"Bearer {tok}", **({"X-Tenant": slug} if slug else {})}  # noqa: E731


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    d = tmp_path_factory.mktemp("agents")
    config.set_data_dir(d)
    seed.load(seed.build_plan(60, 7), reset=True)
    mp = pytest.MonkeyPatch()
    mp.setattr(accounts, "verify", lambda token: USERS[token])
    api = TestClient(app)
    org = api.post("/api/onboarding/organization", headers=H("eyP.partner.sig"),
                   json={"name": "Velas Marine Pvt Ltd", "pan": "AAFCV4821K", "gstin": "27AAFCV4821K1Z2", "fy": "2025-26"}).json()
    api.post(f"/api/tenants/{org['slug']}/invites", headers=H("eyP.partner.sig"), json={"email": "cfo@client.in", "role": "client_admin"})
    api.get("/api/auth/memberships", headers=H("eyC.client.sig"))          # accept the invite
    api.post("/api/client/records/party", headers=H("eyC.client.sig", org["slug"]),
             json={"name": "Coastal Dredgers Pvt Ltd", "tags": "CUSTOMER", "gstin": "27AAACC5123D1Z8"})
    yield api, org["slug"], d
    mp.undo()
    config.set_data_dir(default)


def test_create_list_and_roles(world):
    api, slug, _ = world
    r = api.post("/api/agent-tokens", headers=H("eyP.partner.sig", slug), json={"label": "Claude Code"})
    assert r.status_code == 200, r.text
    tok = r.json()
    assert tok["token"].startswith("agt_") and tok["role"] == "audit_staff"      # a partner's agent is audit staff
    listed = api.get("/api/agent-tokens", headers=H("eyP.partner.sig", slug)).json()["items"]
    assert [i["id"] for i in listed] == [tok["id"]] and "token" not in listed[0] and listed[0]["hint"] == tok["token"][-4:]
    stored = json.dumps(tenants.get(slug))
    assert tok["token"] not in stored                                            # only the hash is kept
    client = api.post("/api/agent-tokens", headers=H("eyC.client.sig", slug), json={}).json()
    assert client["role"] == "client_admin"
    # the gateway resolves it to the organisation
    at = asyncio.run(gateway.Tokens().verify_token(tok["token"]))
    assert at.client_id == "sb:u-partner" and at.scopes == ["audit_staff", f"tenant:{slug}"]
    # no agent tokens on the demo company
    assert api.post("/api/agent-tokens", headers=H("eyP.partner.sig"), json={}).status_code == 403


def test_revoke_and_removed_member(world):
    api, slug, _ = world
    tok = api.post("/api/agent-tokens", headers=H("eyC.client.sig", slug), json={"label": "temp"}).json()
    assert agent_tokens.lookup(tok["token"])
    assert api.delete(f"/api/agent-tokens/{tok['id']}", headers=H("eyC.client.sig", slug)).status_code == 200
    assert agent_tokens.lookup(tok["token"]) is None
    assert asyncio.run(gateway.Tokens().verify_token(tok["token"])) is None
    # a token dies with its owner's membership
    tok2 = api.post("/api/agent-tokens", headers=H("eyC.client.sig", slug), json={}).json()
    t = tenants.get(slug)
    role = t["roles"].pop("sb:u-client")
    accounts._save(t)
    assert agent_tokens.lookup(tok2["token"]) is None
    t["roles"]["sb:u-client"] = role
    accounts._save(t)


def test_mcp_runs_against_the_organisation(world):
    """A real MCP session (stdio, as Claude Desktop runs it) with an agent token sees the organisation's books."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    api, slug, data_dir = world
    tok = api.post("/api/agent-tokens", headers=H("eyC.client.sig", slug), json={"label": "stdio"}).json()["token"]

    async def go():
        env = {**os.environ, "MCP_TRANSPORT": "stdio", "MCP_TOKEN": tok, "DATA_DIR": str(data_dir)}
        params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"], env=env, cwd=os.getcwd())
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                who = await s.call_tool("whoami", {})
                parties = await s.call_tool("query_records", {"entity": "parties"})
                denied = await s.call_tool("list_cases", {})
                return [" ".join(c.text for c in x.content) for x in (who, parties)], denied

    (who, parties), denied = asyncio.run(go())
    assert "Velas Marine Pvt Ltd" in who and "client_admin" in who
    assert "Coastal Dredgers Pvt Ltd" in parties                                  # the organisation's own party
    assert denied.is_error and "PERMISSION_DENIED" in " ".join(c.text for c in denied.content)
