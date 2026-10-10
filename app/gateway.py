"""MCP Gateway: token -> role, role-filtered tools, a trail row per call. STUB until SH-3, which replaces this file
with the 04 §2 code verbatim (MCPServer from mcp.server; never mcp.server.fastmcp). The stub records roles only,
so tools_*.py can already be written against `tool(...)`."""
STUB = True

TOOL_ROLES: dict[str, set[str]] = {}
STDIO_ID = None


class ToolError(Exception):
    """Stand-in for mcp.server.mcpserver.exceptions.ToolError until SH-3."""


def tool(*roles, read_only=False, destructive=False):   # usage: @tool("accounts", "client_admin")
    def deco(fn):
        TOOL_ROLES[fn.__name__] = set(roles)
        return fn
    return deco
