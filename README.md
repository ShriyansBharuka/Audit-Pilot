# ELEV01 · AuditPilot AI: AI-run statutory revenue audit (ELEVATE 1.0 · PS-04)

Audit the business, not the spreadsheet. This repo holds a mini ERP with a tamper-evident double-entry ledger and mock GST portals, plus an audit engine that tests 100% of it against the register the client uploads. Both are exposed as an MCP server where any agent holding a token can run the business or audit it, with exactly that token's permissions. A human partner signs off.

- **Start here:** [`vault/README.md`](vault/README.md) (specs) → [`vault/09_TASK_BOARD.md`](vault/09_TASK_BOARD.md) (tasks)
- **How it works:** [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) · **Who does what:** [`WHO_DOES_WHAT.md`](WHO_DOES_WHAT.md)
- **Coding agents:** [`AGENTS.md`](AGENTS.md) · Claude Code: [`CLAUDE.md`](CLAUDE.md)
- **Run (once built):** `pip install -r requirements.txt` → `python -m app.seed --reset` → `python -m app.mcp_server` → `streamlit run ui/app.py`. Judge connection commands are in [`vault/04 §7`](vault/04_MCP_TOOLS_SPEC.md).

Team: Shriyans Bharuka (lead), Ibrahim, Darshan, Aarav.
