"""One process, one port: the REST API for the web app and the MCP server for agents (hosts like Render expose a
single port per service, and both must share the same SQLite files).

    uvicorn app.serve:app --host 0.0.0.0 --port $PORT

/mcp and /c/<token>/mcp go to the MCP server (TokenInPath, TenantHeader, host checks, its lifespan); every other path
goes to the REST API (app/api_server.py). Locally the two still run separately (python -m app.mcp_server, uvicorn
app.api_server:app); this module is only the single-port deployment entry.
"""
import os

# the in-app assistant calls MCP over HTTP: in this process that is our own port
os.environ.setdefault("MCP_INTERNAL_URL", f"http://127.0.0.1:{os.environ.get('PORT', '8000')}/mcp")

from app import gateway                                  # noqa: E402
import app.tools_client, app.tools_audit                 # noqa: E402,F401  (register the tools on gateway.mcp)
from app.api_server import app as api                    # noqa: E402

_host = os.environ.get("PUBLIC_HOST") or os.environ.get("RENDER_EXTERNAL_HOSTNAME") or "localhost"
_mcp = gateway.mcp.streamable_http_app(
    stateless_http=True, json_response=True, host="0.0.0.0",
    transport_security=gateway.TransportSecuritySettings(
        allowed_hosts=["localhost:*", "127.0.0.1:*", _host, _host + ":*"]))
_mcp_entry = gateway.TokenInPath(gateway.TenantHeader(_mcp))


def _is_mcp(path):
    return path == "/mcp" or path.startswith("/mcp/") or path.startswith("/c/")


async def app(scope, receive, send):
    if scope["type"] == "lifespan":                      # the MCP session manager needs it; the REST API has none
        return await _mcp(scope, receive, send)
    if _is_mcp(scope.get("path", "")):
        return await _mcp_entry(scope, receive, send)
    return await api(scope, receive, send)
