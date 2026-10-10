"""07 Â§8.2: every (tool, role) pair outside TOOL_ROLES is PERMISSION_DENIED + a DENIED trail row, and erp.db stays
byte-identical; audit tokens don't even see client tools; the partner token is rejected on MCP; real calls work."""
import asyncio
import hashlib
import json
import os
import subprocess
import sys

import pytest

from app import config, db, seed
from conftest import TOKENS

MCP_ROLES = ("sales", "warehouse", "accounts", "client_admin", "audit_staff", "orchestrator")


@pytest.fixture()
def server(world):
    from app import gateway, mcp_server  # noqa: F401  (registers the tools)
    seed.load(seed.build_plan(30, 7), reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    yield gateway
    gateway.STDIO_ID = None


def as_role(gw, role):
    gw.STDIO_ID = next((p, r) for p, r in TOKENS.values() if r == role)


def call(gw, name, args=None):
    out = asyncio.run(gw.mcp.call_tool(name, args or {}))          # mcp 2.x: CallToolResult; errors raise ToolError
    if isinstance(out.structured_content, dict):
        return out.structured_content.get("result", out.structured_content)
    return json.loads(out.content[0].text)


def erp_bytes():
    h = hashlib.sha256()
    for suffix in ("", "-wal"):
        p = config.DB_PATHS["erp"].with_name("erp.db" + suffix)
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def last_trail():
    with db.borrow("audit", "audit_staff") as a:
        return dict(a.execute("SELECT * FROM audit_trail ORDER BY seq DESC LIMIT 1").fetchone())


def test_full_permission_matrix(server):
    gw = server
    from mcp.server.mcpserver.exceptions import ToolError
    denied = 0
    for name, roles in sorted(gw.TOOL_ROLES.items()):
        for role in MCP_ROLES:
            if role in roles:
                continue
            as_role(gw, role)
            before = erp_bytes()
            with pytest.raises(ToolError, match="PERMISSION_DENIED"):
                call(gw, name, {})
            assert erp_bytes() == before, (name, role)
            t = last_trail()
            assert (t["tool"], t["role"], t["outcome"]) == (name, role, "DENIED")
            denied += 1
    assert denied > 100


def test_audit_identities_dont_see_client_tools(server):
    gw = server
    for role in MCP_ROLES:
        as_role(gw, role)
        seen = {t.name for t in asyncio.run(gw.mcp.list_tools())}
        assert seen == {t for t, r in gw.TOOL_ROLES.items() if role in r}
    as_role(gw, "audit_staff")
    seen = {t.name for t in asyncio.run(gw.mcp.list_tools())}
    assert "create_sales_order" not in seen and "get_engagement_status" in seen
    assert len(gw.TOOL_ROLES) == 46


def test_partner_token_is_rejected_on_mcp(server):
    gw = server
    assert asyncio.run(gw.Tokens().verify_token("ptn_test")) is None
    assert asyncio.run(gw.Tokens().verify_token("aud_test")).scopes == ["audit_staff"]
    env = {**os.environ, "MCP_TRANSPORT": "stdio", "MCP_TOKEN": "ptn_test"}
    r = subprocess.run([sys.executable, "-m", "app.mcp_server"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "not an MCP identity" in r.stderr


def test_client_runs_the_business_and_the_auditor_audits_it(server):
    gw = server
    as_role(gw, "client_admin")
    me = call(gw, "whoami")
    assert me["summary"]["role"] == "client_admin" and "issue_invoice" in me["summary"]["tools"]
    so = call(gw, "create_sales_order", {"party_id": "P-0001", "confirmed_on": "2026-03-20",
                                         "lines": [{"item_id": "IT-001", "qty": 2, "rate": "6800.00"}]})
    inv = call(gw, "issue_invoice", {"so_id": so["summary"]["id"], "invoice_date": "2026-03-30"})
    assert inv["summary"]["invoice_no"].startswith("G2/") and inv["summary"]["taxable_paise"] == 1360000
    with pytest.raises(Exception, match="valid string|rupees as a string"):     # floats never reach the books
        call(gw, "record_receipt", {"amount": 1.5, "invoice_nos": [inv["summary"]["id"]]})
    exp = call(gw, "export_sales_register")
    up = call(gw, "upload_sales_register", {"base_export_id": exp["summary"]["export_id"],
                                            "edits": [{"row_no": 1, "column": "Total Cost", "value": 1}]})
    assert "d0_hits" not in json.dumps(up)                       # the client never sees the auditor's results
    as_role(gw, "audit_staff")
    st = call(gw, "get_engagement_status")
    assert st["summary"]["register_rows"] > 0 and "D0" in st["summary"]["risk_hits_by_detector"]
    rec = call(gw, "reconcile_register_to_system", {"limit": 5})
    assert rec["summary"]["by_code"].get("TAXABLE_DIFF") and len(rec["items"]) <= 5
    q = call(gw, "query_records", {"entity": "parties", "filters": {"id": "P-0001"}})
    assert "name" not in q["items"][0] and q["items"][0]["client_data"]["name"]          # client text quarantined
    tr = call(gw, "trace_sale", {"invoice": inv["summary"]["invoice_no"]})
    assert "NO_MOVEMENT" in tr["summary"]["gaps"]
    sheet = call(gw, "get_workpaper_sheet", {"sheet": "sales_register", "limit": 3})
    assert sheet["items"][0]["auditor"]["[Auditor] SoR_Match"] and sheet["next_cursor"] == "3"
    sql = call(gw, "run_readonly_sql", {"sql": "SELECT count(*) AS n FROM invoices"})
    assert sql["items"][0]["n"] > 0
    from mcp.server.mcpserver.exceptions import ToolError
    with pytest.raises(ToolError, match="only a single SELECT"):
        call(gw, "run_readonly_sql", {"sql": "DELETE FROM invoices"})
    f = call(gw, "propose_finding", {"category": "Cut-off", "title": "t", "explanation": "e", "taxable_impact": "100.00",
                                     "aje_lines": [{"account_code": "SALES", "debit": "100.00"},
                                                   {"account_code": "CONTRACT_LIABILITY", "credit": "100.00"}]})
    assert f["summary"]["finding_id"] == "F-001" and f["summary"]["status"] == "PROPOSED"
    with pytest.raises(ToolError, match="does not balance"):
        call(gw, "propose_finding", {"category": "x", "title": "t", "explanation": "e",
                                     "aje_lines": [{"account_code": "SALES", "debit": "1.00"}]})
    with db.borrow("audit", "audit_staff") as a:
        outcomes = Counter_of(a)
    assert outcomes["OK"] >= 10 and outcomes["ERROR"] >= 2
    assert "_test" not in json.dumps(list_trail())                                 # tokens never logged


def Counter_of(a):
    from collections import Counter
    return Counter(r[0] for r in a.execute("SELECT outcome FROM audit_trail"))


def list_trail():
    with db.borrow("audit", "audit_staff") as a:
        return [dict(r) for r in a.execute("SELECT * FROM audit_trail")]


def test_http_bearer_401_and_token_in_path(server):
    gw = server
    from starlette.testclient import TestClient
    app = gw.mcp.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0",
                                     transport_security=gw.TransportSecuritySettings(allowed_hosts=["localhost:*"]))
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    listing = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(gw.TokenInPath(app), base_url="http://localhost:8000") as c:
        assert c.post("/mcp", json=init, headers=h).status_code == 401
        assert c.post("/mcp", json=init, headers={**h, "Authorization": "Bearer ptn_test"}).status_code == 401
        ok = c.post("/mcp", json=init, headers={**h, "Authorization": "Bearer aud_test"})
        assert ok.status_code == 200
        tools = c.post("/mcp", json=listing, headers={**h, "Authorization": "Bearer aud_test"}).json()["result"]["tools"]
        assert "get_engagement_status" in {t["name"] for t in tools} and "issue_invoice" not in {t["name"] for t in tools}
        via_path = c.post("/c/adm_test/mcp", json=listing, headers=h).json()["result"]["tools"]
        assert "issue_invoice" in {t["name"] for t in via_path}
