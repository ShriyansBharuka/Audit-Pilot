# app/gateway.py  (imported by tools_client.py / tools_audit.py as: from app.gateway import tool, ToolError)
import json, os
from pathlib import Path
from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from app.trail import trail                      # appends audit.audit_trail (H/A), returns nothing
from app.playbook import PLAYBOOK, DENY_HINT

IDS = json.loads(Path(os.environ.get("IDENTITIES", "identities.json")).read_text())
TOOL_ROLES: dict[str, set[str]] = {}
STDIO_ID = None                                   # (principal, role) in stdio mode

class Tokens(TokenVerifier):
    async def verify_token(self, token):
        i = IDS.get(token)
        if i and i["role"] != "engagement_partner":   # partner: web UI only
            return AccessToken(token=token, client_id=i["principal"], scopes=[i["role"]])
        return None

def caller():
    t = get_access_token()
    if t: return t.client_id, t.scopes[0]
    if STDIO_ID: return STDIO_ID
    raise ToolError("UNAUTHENTICATED: send 'Authorization: Bearer <token>' (HTTP) or set MCP_TOKEN (stdio).")

class Gateway(MCPServer):                         # the single choke point: permission + trail
    async def list_tools(self):
        role = caller()[1]
        return [t for t in await super().list_tools() if role in TOOL_ROLES.get(t.name, ())]
    async def call_tool(self, name, arguments, context=None):
        who, role = caller()
        if role not in TOOL_ROLES.get(name, ()):
            trail(who, role, name, arguments, "DENIED")
            raise ToolError(f"PERMISSION_DENIED: {who} (role {role}) may not call {name}. {DENY_HINT.get(role, '')}")
        try:
            out = await super().call_tool(name, arguments, context)
        except Exception as e:
            trail(who, role, name, arguments, "ERROR", str(e)); raise
        trail(who, role, name, arguments, "OK", out)
        return out

PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000/mcp")
mcp = Gateway("auditpilot", instructions=PLAYBOOK, token_verifier=Tokens(),
              auth=AuthSettings(issuer_url="https://auth.example.com",   # placeholder: static tokens, no OAuth server
                                resource_server_url=PUBLIC_URL,
                                validate_token_resource=False))         # static tokens carry no audience; silences the 2.3 deprecation warning

def tool(*roles, read_only=False, destructive=False):   # usage: @tool("accounts", "client_admin")
    def deco(fn):
        TOOL_ROLES[fn.__name__] = set(roles)
        return mcp.tool(annotations=ToolAnnotations(read_only_hint=read_only, destructive_hint=destructive))(fn)
    return deco

class TokenInPath:  # /c/<token>/mcp -> Authorization header (header-less hosts)
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        parts = scope.get("path", "").split("/", 3)
        if scope["type"] == "http" and len(parts) == 4 and parts[1] == "c":
            hdrs = [h for h in scope["headers"] if h[0] != b"authorization"]
            scope = {**scope, "path": "/" + parts[3], "raw_path": ("/" + parts[3]).encode(),
                     "headers": hdrs + [(b"authorization", f"Bearer {parts[2]}".encode())]}
        await self.app(scope, receive, send)
