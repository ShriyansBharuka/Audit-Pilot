# Connect an AI agent to AuditPilot (MCP)

AuditPilot runs an MCP server, so any MCP-capable assistant (Claude, Cursor, VS Code Copilot, Gemini CLI, n8n, your
own agent) can work in the audit with **exactly the permissions of the token you give it**. Every call, including
refused ones, is written to the hash-chained audit trail.

## What it allows

53 tools in total. The token decides the role, and an agent only ever sees its own role's tools.

| Role (token prefix) | Tools | What the agent can do |
|---|---|---|
| `audit_staff` (`aud_`) | 26 | Engagement status, risk graph, cases and money trail (`trace_money`, `trace_sale`), run analytics, select and test samples, reproduce a selection, reconcile the register, propose findings, notes, workpaper sheets, deliverables and the statutory memo, `verify_integrity`, read-only SQL |
| `client_admin` (`adm_`) | 31 | Run the company's books: parties, items, sales orders, invoices, e-way bills, dispatch and delivery, credit notes, receipts and payments, purchases, journals, GSTR-1/3B, amendments and cancellations, bulk import; upload the sales register, related-party list and evidence |
| `accounts` (`acc_`) | 19 | Invoices, credit notes, receipts, payments, purchases, journals, GST filings, register export/upload, evidence |
| `sales` (`sal_`) | 9 | Parties, leads, schemes, sales orders, amendments |
| `warehouse` (`whs_`) | 11 | E-way bills, dispatch, delivery, goods receipts, documents, evidence |
| `orchestrator` (`orc_`) | 8 | Automation (n8n): status, change checks, analytics, sample tests, integrity checks |

Rules the server enforces, whatever the agent asks:

- **Auditor independence (SA 200):** audit tokens cannot create or change business records (`create_party` from an
  auditor is refused with `PERMISSION_DENIED`).
- **Clients never see the audit's reasoning:** a client token cannot list cases, findings or risk scores.
- **No AI sign-off:** the engagement partner's token is refused over MCP. Confirming findings and signing off happen
  only in the web app, by a person.
- **Agent output is a proposal:** findings an agent proposes stay *PROPOSED* until the partner decides.
- Without `X-Tenant`, MCP serves the demo company (Konkan Marine Controls Ltd). A web (e-mail) account works with its own
  organisation: send its Supabase session as the Bearer token plus `X-Tenant: <slug>`; the role comes from that
  organisation, and the partner role is still refused.
- Tokens from `identities.json` work on the demo company (Konkan Marine Controls Ltd); `agt_…` tokens created in the
  app work on the organisation they were created for.

## Easiest: the in-app page

In the web app click **Connect an agent** (top right). It walks you through it with your token already filled in:

1. **Get your token.** Signed in with an access token: it is shown there (Show / Copy). Signed in with e-mail: click
   **Create token** for your organisation (shown once; revoke any time). A partner's agent works as audit staff.
2. **Pick your assistant** (Claude Code, Claude Desktop, Claude.ai, ChatGPT, Cursor, VS Code, Gemini CLI, n8n, Python)
   and follow the numbered steps; every command and config has a Copy button.
3. **Public address** for the cloud assistants (Claude.ai, ChatGPT).
4. **Prompts to try.**

E-mail accounts' agent tokens (`agt_…`) work on *their own* organisation; the demo company uses the tokens below.

## Before you start

1. Start the server: `python -m app.mcp_server` (port 8000). Check it: `python scripts/mcp_check.py` should end with
   `11/11 checks passed`.
2. Get a token from `identities.json` (or the judge card printed at seed time). Use `aud_…` for an auditor agent,
   `adm_…` for a client agent. Treat tokens like passwords.

The server URL is `http://localhost:8000/mcp` on this machine, or `https://<your-host>/mcp` once hosted.

## Claude Code (one command)

```bash
claude mcp add --transport http auditpilot http://localhost:8000/mcp --header "Authorization: Bearer aud_..."
```

Then in Claude Code type `/mcp` to see it connected, and ask in plain English (prompts below).

## Claude Desktop (local, stdio)

Add to `claude_desktop_config.json` (Settings → Developer → Edit config), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "auditpilot": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "E:\\Projects\\Auditing Tool",
      "env": { "MCP_TRANSPORT": "stdio", "MCP_TOKEN": "aud_..." }
    }
  }
}
```

## Cursor

`~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project):

```json
{ "mcpServers": { "auditpilot": { "url": "http://localhost:8000/mcp", "headers": { "Authorization": "Bearer aud_..." } } } }
```

## VS Code (Copilot agent mode)

`.vscode/mcp.json`:

```json
{ "servers": { "auditpilot": { "type": "http", "url": "http://localhost:8000/mcp", "headers": { "Authorization": "Bearer aud_..." } } } }
```

## Gemini CLI

`~/.gemini/settings.json`:

```json
{ "mcpServers": { "auditpilot": { "httpUrl": "http://localhost:8000/mcp", "headers": { "Authorization": "Bearer aud_..." } } } }
```

## Apps that cannot send headers (Claude.ai and ChatGPT connectors)

Web apps run in the cloud, so they need a **public HTTPS** address, not `localhost`. Put the token in the path instead
of a header:

```text
https://<your-host>/c/aud_.../mcp
```

- **Claude.ai:** Settings → Connectors → Add custom connector → paste that URL.
- **ChatGPT:** Settings → Connectors (developer mode) → create a connector with that URL.

To get a public address before hosting, run a tunnel and tell the server its hostname (otherwise it answers 421):

```bash
cloudflared tunnel --url http://localhost:8000          # prints https://<random>.trycloudflare.com
PUBLIC_HOST=<random>.trycloudflare.com python -m app.mcp_server
```

## n8n and your own code

- **n8n:** the MCP Client Tool node, Streamable HTTP, URL `…/mcp`, header `Authorization: Bearer orc_...`.
- **Python:** the official `mcp` client, as in `scripts/mcp_check.py` or `ui/mcp_client.py`.

## Prompts to try

As an auditor (`aud_…`):

- "Who am I and what can I do here?" (calls `whoami`)
- "What's the engagement status and the company risk band?"
- "List the open audit cases, biggest first, and trace the money for the top one."
- "Select a sales sample and tell me why each item was picked."
- "Verify the integrity of the books and the audit trail."
- "Draft the statutory audit memo." (the memo is a draft; the partner decides)

As the client (`adm_…`):

- "Show me my last 5 invoices."
- "Which evidence requests are still open?"
- "Create a customer Coastal Dredgers Pvt Ltd, GSTIN 27AAACC5123D1Z8."

Try the walls too: ask the client agent for the audit cases, or the auditor agent to create a customer. Both are
refused, and the refusal appears in the web app's **Audit trail**.

## Troubleshooting

| Symptom | Cause |
|---|---|
| 401 Unauthorized | Missing or wrong token (or the partner token, which is web-only) |
| 421 Invalid Host header | Set `PUBLIC_HOST` to the public hostname the agent uses |
| A tool is missing | That role does not have it: check the table above |
| `PERMISSION_DENIED: …` | The role rule did its job; the message says which role may |
