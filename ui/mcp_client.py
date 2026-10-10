"""The web UI is just another MCP client: every business/audit action goes through the MCP server with the
logged-in user's token, so the UI gets exactly that identity's permissions and every click is in the audit trail.
"""
import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8000/mcp")


class ToolFailed(Exception):
    pass


def _payload(res):
    data = getattr(res, "structured_content", None) or getattr(res, "structuredContent", None)
    if isinstance(data, dict) and set(data) == {"result"} and isinstance(data["result"], dict):
        data = data["result"]
    if data is None:
        text = " ".join(getattr(c, "text", "") for c in res.content)
        try:
            data = json.loads(text)
        except ValueError:
            data = {"text": text}
    return data


def call(token, tool, args=None, url=None):
    """Synchronous call of one MCP tool -> its result dict; ToolFailed carries the server's CODE: message."""
    async def go():
        hc = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"})
        async with streamable_http_client(url or MCP_URL, http_client=hc) as streams:
            async with ClientSession(streams[0], streams[1]) as s:
                await s.initialize()
                return await s.call_tool(tool, args or {})
    try:
        res = asyncio.run(go())
    except BaseException as e:  # noqa: BLE001 - connection errors surface as one readable message
        raise ToolFailed(f"cannot reach the MCP server at {url or MCP_URL} ({type(e).__name__})") from e
    if getattr(res, "is_error", False):
        raise ToolFailed(" ".join(getattr(c, "text", "") for c in res.content).replace("Error executing tool ", ""))
    return _payload(res)
