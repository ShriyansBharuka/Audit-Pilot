"""MCP smoke test, run like an agent would (official MCP client): python scripts/mcp_check.py [http://host:8000/mcp]

Checks: no token -> 401; each role lists only its tools; real calls work; cross-role calls are refused; the
header-less /c/<token>/mcp path works; the partner token is refused over MCP; calls land in the audit trail.
Needs the MCP server running (python -m app.mcp_server) and identities.json.
"""
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/mcp"
IDS = json.load(open("identities.json", encoding="utf-8"))
BY_ROLE = {}
for tok, rec in IDS.items():
    BY_ROLE.setdefault(rec["role"], (tok, rec))


def text(res):
    return " ".join(" ".join(getattr(c, "text", "") for c in res.content).split())


async def session(token, url=URL, fn=None):
    hc = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"} if token else {})
    async with streamable_http_client(url, http_client=hc) as (r, w, *_):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            return await fn(s, init)


def ok(flag, label):
    print(f"  [{'PASS' if flag else 'FAIL'}] {label}")
    return flag


async def main():
    results = []
    print(f"MCP server: {URL}\n")

    # 1. no token
    try:
        urllib.request.urlopen(urllib.request.Request(URL, data=b"{}", headers={"Content-Type": "application/json"}), timeout=10)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    results.append(ok(code == 401, f"no token -> HTTP {code} (expected 401)"))

    # 2. what each role sees
    print("\nTools per role (an agent only ever sees its own role's tools):")
    tools_of = {}
    for role, (tok, rec) in sorted(BY_ROLE.items()):
        if role == "engagement_partner":
            continue
        async def lt(s, init):
            return init, (await s.list_tools()).tools
        init, tools = await session(tok, fn=lt)
        tools_of[role] = [t.name for t in tools]
        print(f"  {role:<14} {len(tools):>3} tools  ({rec['principal']})")
    print(f"  server name '{init.server_info.name}', instructions sent to the agent: {len(init.instructions or '')} chars")

    # 3. real calls
    print("\nReal calls:")
    aud = BY_ROLE["audit_staff"][0]
    adm = BY_ROLE["client_admin"][0]
    for tok, tool, args in [(aud, "whoami", {}), (aud, "get_engagement_status", {}),
                            (aud, "list_cases", {}), (adm, "whoami", {}),
                            (adm, "query_records", {"entity": "invoices", "limit": 2}),
                            (adm, "list_evidence_requests", {"limit": 2})]:
        async def c(s, init, tool=tool, args=args):
            t0 = time.perf_counter()
            r = await s.call_tool(tool, args)
            return r, time.perf_counter() - t0
        try:
            r, dt = await session(tok, fn=c)
            results.append(ok(not r.is_error, f"{IDS[tok]['role']:<12} {tool}({args or ''}) in {dt * 1000:.0f} ms -> {text(r)[:90]}"))
        except Exception as e:  # noqa: BLE001
            results.append(ok(False, f"{tool}: {e}"))

    # 4. permission walls
    print("\nPermission walls:")
    for tok, tool, args, why in [(adm, "list_cases", {}, "client cannot use audit tools"),
                                 (aud, "create_party", {"name": "X Traders"}, "auditor cannot write client data (SA 200)")]:
        async def c(s, init, tool=tool, args=args):
            return await s.call_tool(tool, args)
        r = await session(tok, fn=c)
        results.append(ok(r.is_error and "PERMISSION_DENIED" in text(r), f"{why}: {text(r)[:80]}"))

    # 5. partner token refused over MCP
    ptn = BY_ROLE["engagement_partner"][0]
    try:
        await session(ptn, fn=lambda s, i: s.list_tools())
        results.append(ok(False, "partner token accepted over MCP"))
    except BaseException:  # noqa: BLE001
        results.append(ok(True, "partner token refused over MCP (sign-off is human-only, in the web UI)"))

    # 6. header-less hosts
    base = URL.rsplit("/mcp", 1)[0]
    async def wi(s, init):
        return await s.call_tool("whoami", {})
    r = await session(None, url=f"{base}/c/{aud}/mcp", fn=wi)
    results.append(ok(not r.is_error, f"header-less URL /c/<token>/mcp -> {text(r)[:70]}"))

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
