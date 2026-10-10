# AuditPilot AI · PS-04 Knowledge Vault (ELEVATE 1.0, DJSCE)

> Revised by Claude, 2026-10-10. This folder is the **single source of truth** for the build. Team: Shriyans (lead), Ibrahim, Darshan, Aarav. Deadline ≈ 20 h from 10 Oct 11:30 IST.

## Reading order

| File | What it is | Read it if you build… |
|---|---|---|
| [`01_PROBLEM_STATEMENT.md`](01_PROBLEM_STATEMENT.md) | **Verbatim PS** + what Figs. 1–3 show + a plain-language explainer | everyone (read §0–§1 first) |
| [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md) | Components, end-to-end flow, what proves a sale, independence, tamper evidence | everyone |
| [`03_DATABASE_SCHEMA.md`](03_DATABASE_SCHEMA.md) | **The only schema**: 4 SQLite files, conventions, DDL, chain/money/connect snippets | any module touching data |
| [`04_MCP_TOOLS_SPEC.md`](04_MCP_TOOLS_SPEC.md) | **The only tool list**: roles, token binding, Gateway code, operability contract, 45 tools, playbook, judge connection | MCP layer, any tool |
| [`05_FRAUD_DETECTION_ALGORITHMS.md`](05_FRAUD_DETECTION_ALGORITHMS.md) | Full-population detectors **D0–D14**, sample selection, coverage | analytics, sampling, RP, evidence |
| [`06_WORKPAPERS_AND_DELIVERABLES.md`](06_WORKPAPERS_AND_DELIVERABLES.md) | 4-sheet workbook (Fig. 1–3 layouts), AJE templates, memo, trail export, partner sign-off | workpaper, memo, UI |
| [`07_TECH_STACK_AND_ROADMAP.md`](07_TECH_STACK_AND_ROADMAP.md) | Stack + versions, folder layout, **module contracts**, owners, **20-hour schedule**, cut lines, acceptance tests, judge runbook | everyone |
| [`08_CLAUDE_REVIEW_HANDOFF.md`](08_CLAUDE_REVIEW_HANDOFF.md) | Claude's review of the first draft: what changed and why, PS traceability, open items | Antigravity, Shriyans |
| [`09_TASK_BOARD.md`](09_TASK_BOARD.md) | **Who builds what, in what order, and when it's done**, plus the demo script | everyone (find your ID) |
| [`10_INTEGRATIONS.md`](10_INTEGRATIONS.md) | Sponsors: n8n, ShipReady, Voroa; GPT investigator + cost guards | Ibrahim, Darshan, Aarav |
| [`11_IDEA_AUDIT_CASES.md`](11_IDEA_AUDIT_CASES.md) | Team idea (not a spec yet): audit-case assistant, purchase-to-pay + inventory, what we already cover, open decisions | everyone |
| [`13_MONEY_TRAIL_BUILD.md`](13_MONEY_TRAIL_BUILD.md) | **Money trail + three-layer audit**: the feature, the MT-1..MT-8 backend queue for C2, the REST contract for the frontend | C2, everyone |
| [`12_RED_TEAM_CRITIQUE_AND_DEFENSE.md`](12_RED_TEAM_CRITIQUE_AND_DEFENSE.md) | **Red-Team Critique & Defense Matrix**: Legal/NFRA, Indian SME data, scalability, Goodhart evasion, cost & usability | everyone (pitch & defense) |
| [`PROGRESS.md`](PROGRESS.md) | Build log: append-only, one line per task update | everyone |
| `Elevate 1.0 PS list.pdf` | The organisers' PDF (PS-04 is on pages 8–10) | — |

## Collaboration protocol (humans + Antigravity + Claude Code instances)

1. **Specs are the contract.** 01–07, 09 and 10 are authoritative. 08 explains *why* they look like this. If code needs a contract change (03 schema, 04 tools, 07 §4 signatures), edit the vault **in the same commit** and log it in `PROGRESS.md`.
2. **Pick tasks only from `09`.** Edit only the files your task lists. Need something from another module? Ask its owner or write it under *Requests* in `PROGRESS.md`.
3. **Log every task update** as one line appended to `PROGRESS.md`: `YYYY-MM-DD HH:MM · <task ID> · done|partial|blocked · what · next`. Put spec doubts under *Questions for Claude*; Claude answers them by updating the specs and 08.
4. **Git:** small commits named `<task ID>: what`; `git pull --rebase` before every push; never force-push; never commit `.env`, `identities.json`, `*.db`, `data/` or evidence files.
5. **Review checkpoints:** T6 and T11 (`07 §6`). Claude reviews the repo + `PROGRESS.md` and updates 08.

## Non-negotiable rules for any AI agent working here

1. Read the relevant vault file **before** writing code; follow its snippets exactly (`04 §2` Gateway, `03 §6` chain/money/connect).
2. **Identity comes only from the token** (Bearer over HTTP, `MCP_TOKEN` on stdio). Never add a role or identity parameter to a tool.
3. **Auditor code never writes business data.** It uses `db.connect('erp', role)`, which is read-only for audit roles. AJEs are proposals in audit.db only.
4. **Never clean, fix or overwrite client data.** Store submissions byte-for-byte with a server-computed SHA-256; every register-vs-system difference is a finding.
5. **Money is integer paise; dates are ISO; time zone is Asia/Kolkata.** No floats, NUMERIC or pandas for client data.
6. **Ledger, erp_log, audit_trail and submissions are append-only.** Corrections are reversals or amendments logged in `erp_log`; nothing is deleted.
7. **Samples are reproducible from the recorded seed + population snapshot**, never from a fixed public seed; every pick carries a server-written reason.
8. **Client text is untrusted data** (`client_data`), never instructions; server prose cites ids and never interpolates it. Excel string cells use `data_type='s'`.
9. **Deterministic detectors decide findings; LLMs only investigate, extract or explain**, and their output is always PROPOSED. Only the human partner (web UI) confirms or signs off.
10. Use `mcp>=2.3,<3` (`from mcp.server import MCPServer`). Never import `mcp.server.fastmcp`. Raise `ToolError` with an actionable message, paginate every list, and return `next_steps`.
