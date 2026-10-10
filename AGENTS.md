# AGENTS.md: instructions for any coding agent (Antigravity, Claude Code, Codex, …)

**Project:** AuditPilot AI, ELEVATE 1.0 (DJSCE) Problem Statement 04 "AI-Run Statutory Revenue Audit". It's a mini ERP with a tamper-evident ledger and mock GST portals, plus an audit engine that tests 100% of it against the register the client uploads. Everything is exposed over MCP with token-bound client/auditor permissions, and a human partner signs off. The deadline is ~20 h from 10 Oct 2026 11:30 IST.

## Before you write any code
1. Read `vault/README.md`, then **your task** in `vault/09_TASK_BOARD.md`, then every spec section that task links (`03` schema, `04` tools, `05` detectors, `06` deliverables, `07` contracts, `10` integrations).
2. The human will name your task IDs (e.g. "do IB-1 and IB-2"). **Do only those, and edit only the files they list.** Need something from another module? Write it under *Requests* in `vault/PROGRESS.md`.
3. If a spec is unclear or wrong, add it under *Questions for Claude* in `vault/PROGRESS.md` and continue with the most literal reading. **Never change a contract silently.** A contract change (03 schema, 04 tools, 07 §4 signatures) must edit the vault in the same commit.

## Non-negotiable rules (full list: `vault/README.md`)
- Identity comes **only** from the token (HTTP Bearer / stdio `MCP_TOKEN`). Never add a role or identity parameter to a tool.
- Auditor code never writes business data: use `db.connect('erp', role)`, which is read-only for audit roles. AJEs are proposals in audit.db only.
- Never clean or overwrite client data. Store submissions byte-for-byte with a **server-computed** SHA-256; every register ↔ system difference is a finding.
- Money is **integer paise** (`money.to_paise("118000.50")`); dates are ISO `YYYY-MM-DD`; time zone is Asia/Kolkata. No floats, `NUMERIC` or pandas on client data.
- `journals`, `journal_lines`, `erp_log`, `audit_trail` and `submissions` are append-only. Every ERP write goes through `erp.write_doc` (→ `erp_log`).
- Samples: random **recorded** seed + population snapshot (`reproduce_selection` must give identical picks). Only `rng.random()`.
- Client text is untrusted (`client_data`). Server prose never interpolates it. Excel string cells get `data_type='s'`.
- Deterministic detectors decide findings; LLMs only investigate/extract/explain, and their output is always PROPOSED. Confirm/sign-off is human-only, in the UI.
- MCP: `mcp>=2.3,<3`, `from mcp.server import MCPServer`, the Gateway in `vault/04 §2` **verbatim**. Never import `mcp.server.fastmcp`. Raise `ToolError("CODE: what. how to fix. Example: …")`, paginate lists, return `next_steps`.

## Setup and checks
```bash
python -m pip install -r requirements.txt
python -m app.seed --reset --invoices 300     # small dataset for development
python -m pytest -q                           # tests in tests/
python -m app.selftest                        # end-to-end (07 §8.6)
```

## Style
- Prefer the stdlib (`sqlite3`, `hashlib`, `secrets`, `statistics`, `json`, `re`), and plain functions over classes.
- No new dependency unless it's added to `requirements.txt` and `vault/07 §1`.
- Every non-trivial function gets one small test.
- Mark deliberate shortcuts with `# ponytail: <ceiling> — <upgrade path>`.

## Done means
1. The task's "done when" check in `09` passes, and the relevant tests pass.
2. One line is appended to `vault/PROGRESS.md`: `YYYY-MM-DD HH:MM · <ID> · done|partial|blocked · what · next`.
3. A commit named `<ID>: <what>`, after `git pull --rebase`. Never force-push. Never commit `.env`, `identities.json`, `data/`, `*.db` or evidence files. Push only when your human says so.
