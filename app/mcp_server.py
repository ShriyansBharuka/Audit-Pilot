# app/mcp_server.py   run: python -m app.mcp_server   (set MCP_TRANSPORT=stdio + MCP_TOKEN for stdio)
import os
from app import gateway
import app.tools_client, app.tools_audit           # noqa: F401  (register tools on gateway.mcp via @tool)

def main():
    if os.environ.get("MCP_TRANSPORT") == "stdio":
        i = gateway.IDS.get(os.environ.get("MCP_TOKEN", ""))
        if not i or i["role"] == "engagement_partner":
            raise SystemExit("MCP_TOKEN missing or not an MCP identity")
        gateway.STDIO_ID = (i["principal"], i["role"])  # set on the module that caller() reads
        gateway.mcp.run()
    else:
        import uvicorn
        host = os.environ.get("PUBLIC_HOST", "localhost")   # e.g. abc.trycloudflare.com
        app = gateway.mcp.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0",
                  transport_security=gateway.TransportSecuritySettings(allowed_hosts=["localhost:*", "127.0.0.1:*", host, host + ":*"]))
        uvicorn.run(gateway.TokenInPath(app), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

if __name__ == "__main__":
    main()
