@AGENTS.md

## Claude Code specifics
- **Library docs:** use context7 (`mcp__context7__resolve-library-id` → `query-docs`) for `mcp` (python-sdk v2), `openai-agents`, `openpyxl`, `streamlit`, `pymupdf` and n8n. Don't trust memory for the MCP SDK: v2 renamed FastMCP to MCPServer.
- **Quota (Claude Pro):** keep one session per task ID from `vault/09_TASK_BOARD.md`. Don't spawn subagents or workflows unless the human asks. If the Opus quota runs low, continue routine edits on Sonnet.
- Before saying a task is done, run its tests and `python -m app.selftest` when the platform exists, and paste the result in your reply.
- Before editing, re-read the vault section you're implementing. The vault (`vault/03`, `vault/04`, `vault/07 §4`) wins over your assumptions.
- Don't push unless the human says so; `git pull --rebase` before any push.
