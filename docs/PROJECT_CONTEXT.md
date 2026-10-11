# AuditPilot AI: full project context (paste this into another assistant)

You are being given the context of a hackathon project so you can help with a related task. Treat this as background;
the task itself will follow separately. Everything below describes the project as it is on 11 Oct 2026.

## 1. What it is

**AuditPilot AI** is our entry for **ELEVATE 1.0 (DJSCE, Mumbai), Problem Statement 04: "AI-Run Statutory Revenue Audit"**.

**The problem:** in a statutory audit of revenue (India), the auditor gets an Excel sales register from the client
(6,000–8,000 sales a year), vouches only 25–35 invoices by hand, and never sees the company's real systems. So fake
sales, revenue booked in the wrong year, undisclosed related-party sales and circular trading hide behind
complete-looking paperwork. By chance alone, 30 random picks out of 7,000 catch even one of 10 planted frauds only
**4.2%** of the time.

**Our answer:** we build a mini version of the company's business system and audit **100%** of it:
- **The business:** enquiry → order → dispatch → invoice → payment, plus purchases (PO → goods receipt → bill →
  payment).
- **The records it writes to:** a tamper-evident double-entry ledger, and mock government and bank records (e-invoice
  IRN, e-way bill, GSTR-1/3B, bank statement).
- **The audit:** the client's uploaded register is compared with that system row by row. Every difference is a finding,
  never a cleaning step.
- **Agents:** everything is exposed over an **MCP server** with token-bound permissions, so AI agents (including the
  judges' own) can run the business as a client or audit it as the auditor, with exactly their token's permissions.
- **Sign-off:** a **human engagement partner** confirms every finding and signs off; the AI only proposes.

**The demo company** is synthetic and fictional: **Konkan Marine Controls Ltd**, FY 2025-26 (1 Apr 2025 – 31 Mar 2026):
- 7,587 issued invoices: 7,027 dated inside the FY, and 560 post-period invoices for cut-off testing
- 2 factories (units G2 Ratnagiri, G11 Verna/Goa)
- ~150 customers, vendors, directors and relatives
- planted irregularities, with a held-out answer key

A second demo organisation, **Sahyadri Shipyards Enterprises**, has 327 invoices.

**The team:** 4 people (Shriyans, Ibrahim, Darshan, Aarav). Note that the judging rules forbid participant names in the
slides.

## 2. The PS requirements and how each is met

| Requirement | Implementation |
|---|---|
| Client uploads the sales register + related-party list | Web client portal + MCP tools `upload_sales_register`, `upload_related_parties`; stored byte-for-byte with a server-computed SHA-256 |
| Workpaper with the client's data exactly as given + a Related / Non-related column | 4-sheet Excel (openpyxl): Sales Register (verbatim, cell for cell), Sales TOD, Sales Cut-off TOD, Credit Note TOD |
| Sales TOD of 25–35, risk-based, reproducible, with reasons | `sampling.py`: strata KEY (detector hits), HIGH_VALUE, RP, REPRESENTATIVE (systematic PPS); random seed recorded with a population snapshot; `reproduce_selection` replays it exactly |
| Cut-off TOD (last ~10 before / first 10–15 after the period end) | Compares invoice date with dispatch, LR, POD and e-way bill dates **and delivery terms** (transfer of control, Ind AS 115), plus the entry timestamp |
| Credit-note TOD | Post-period credit notes against pre-period sales (SA 560) |
| Evidence requested automatically, then tested | Requests created on selection (the client sees what is asked, never why); uploads checked against the books and the portals (same EWB? vehicle? another invoice's document? reused file?) |
| Detect changes after testing began | `check_for_changes`: the field, old/new value, user, and which samples are now stale |
| Ledger that can't be silently altered | Append-only tables, reversals instead of edits, SHA-256 hash chains, auditor-held anchors, offline verifier |
| MCP server with identity-based permissions | 53 tools, 6 roles; token = identity; auditor tokens can never write business data; partner token refused over MCP |
| Findings with ₹ impact and adjusting entries, human sign-off | Findings memo + statutory memo; AJE lines Dr = Cr; status PROPOSED until the partner confirms / rejects with a mandatory comment, then signs (web UI only) |

## 3. Architecture

- **Data:** four SQLite files (per organisation), with independence enforced by SQLite itself:
  - `erp.db`: the company's system of record (masters, orders, movements, invoices, credit notes, settlements, purchase
    orders, goods receipts, purchase bills, journals, `erp_log`). Client roles are read-write. **Audit roles get a
    read-only handle (`mode=ro` + `query_only`)**, so auditor code physically cannot write business data.
  - `ext.db`: the mock IRP (e-invoice), e-way bill portal, GSTR-1/3B filings, bank statement and MCA registry. Only the
    portal module writes it.
  - `pbc.db`: the "prepared by client" channel: evidence requests, client submissions, register exports.
  - `audit.db`: the auditor's file (engagement, frozen register, samples, risk hits, findings/AJEs, cases, risk
    snapshots, anchors, events, audit_trail). **Client roles get no handle at all.**
- **MCP server** (`python -m app.mcp_server`, port 8000, official `mcp` SDK 2.3, `MCPServer`, streamable HTTP or stdio):
  one Gateway class filters `list_tools` by role and checks every `call_tool`. Every call, including denied ones, is
  appended to the hash-chained `audit_trail`.
- **REST API** for the web app (`uvicorn app.api_server:app --port 8001`, FastAPI): Bearer-token auth with the same
  identities, role guards, and `X-Tenant` for the organisation.
- **Web app:**
  - **Next.js** (`web_v2/`, mirrored identically into `web/`): dark Supabase-like theme, grouped sidebar, landing page,
    Supabase e-mail sign-in.
  - **Streamlit** (`ui/app.py`): the older UI, still runs.
- **Automation:** n8n receives HMAC-signed webhooks (uploads, evidence received, stale samples, integrity alerts, risk
  escalations).

### Roles (token decides role; never a role parameter)

| Role | Who | Can |
|---|---|---|
| `sales`, `warehouse`, `accounts`, `client_admin` | Company staff (or a judge playing the company) | Run the business, upload register and RP list, answer evidence requests |
| `audit_staff` | The auditor AI / staff | Read everything, run tests, select samples, propose findings; never write business data |
| `orchestrator` | n8n | Status, scheduled checks, events |
| `engagement_partner` | A human CA | Confirm / reject findings and sign off, **web UI only** (the token is refused over MCP) |

**Identities:** agent/judge tokens live in `identities.json` (never committed). Web users sign in with Supabase; their
role comes **only** from their organisation's `tenant.json` roles map.

## 4. The audit engine

**Detectors D0–D15.** Each hit has a code, a severity (1–5), a ₹ impact, a plain-language reason (record ids only,
never client text) and the standard it rests on:

| | Detector | What it catches |
|---|---|---|
| D0 | Register vs system of record | Not in the books, missing from the register, amount / date / customer / GSTIN differences, duplicates, tie-out residue |
| D1 | Related parties via shared identifiers | PAN, PAN inside a GSTIN, bank, phone, e-mail, address |
| D2 | RP relationship dates | The relationship starts mid-period, or is declared with the wrong dates |
| D3 | Cut-off by transfer of control | Delivery terms; FOR-destination POD after year end |
| D4 | No physical movement | No dispatch / LR / POD, quantity shortfall, third-party payer, payer is a related party |
| D5 | Period-end concentration | Sales and discounts spikes, schemes at year end, Benford (information only) |
| D6 | Statutory documents and returns | Invoice vs IRN vs e-way bill vs GSTR-1/3B |
| D7 | Revenue journals with no sale | Unusual contra, post-closing entries, round amounts |
| D8 | Forged / reused evidence | Checked inside sample testing |
| D9 | Credit notes after the period end | Returns without inward movement, late cancellations |
| D10 | Circular trading / round trips | AuditGraph cycles |
| D11 | Changes after testing began | Stale samples |
| D12 | Integrity | Broken hash chain, anchor mismatch, out-of-band database edit, unbalanced journal |
| D13 | Backdating and sequence breaks | Late IRN, late POD entry |
| D14 | Instruction text in client data | Prompt injection, e.g. a customer named "IGNORE PREVIOUS INSTRUCTIONS…" |
| D15 | Purchase to pay | Short receipt, price variance, payment without receipt, duplicate payment, beneficiary mismatch, unrecorded liability, unsettled advance |

D15 "explains first": it checks later receipts, returns, recent advances and accruals before flagging.

**AuditGraph (`risk_graph.py`):**
- A temporal graph of the company, parties and money.
- **Engine A** is a noisy-OR over an invoice's hits. **Entity risk** is E = 0.35·C + 0.25·F + 0.15·T + 0.15·H + 0.10·N,
  where N reads the previous round, so scores can't feed back on themselves.
- **Final score** R = max(0.7·A + 0.3·E, 60 if there is hard evidence). Bands: LOW < 30 ≤ REVIEW < 60 ≤ HIGH.
- **Circular trading** uses minimum-span cycle decomposition, so each rupee in a cycle is counted once.
- **Company flag (SA 315):** LOW / MODERATE / HIGH from exposure vs performance materiality and the number of families
  hit.
- **Updates:** continuous per business event (1–3 s), plus a full rebuild per analytics run.
- **Explanations:** exact Shapley values (`explain.py`) attribute each score.

**Cases (`cases.py`):**
- Every severity ≥ 4 hit is grouped by its root object (invoice, PO chain, payment, journal, or a party for a cycle) into
  a case `AUD-0001…`.
- Each case carries **three separate numbers**: recorded (books), verified (bank lines naming the recorded
  counterparty), and potentially affected (to investigate, not a loss).
- It also has a risk score, a confidence, a status (OPEN / EXPLAINED / EVIDENCE_REQUESTED / ESCALATED /
  ADJUSTMENT_PROPOSED) and an append-only history.

**Money trail (`money_trail.py`):**
- Every edge is labelled VERIFIED (bank / portal), CLAIMED (books) or INFERRED (identity link).
- There is no downstream attribution: if A pays B and B pays C, it never claims A's money reached C.
- **Demo case AUD-0014:** ₹5,00,000 advance to ABC Industrial Supplies, 60 of 100 units received → verified ₹5 L,
  received ₹3 L, potentially affected ₹2 L.

**Year-end (`yearend.py`):** a monthly timeline; March documents with an April credit note, cancellation, late dispatch,
delivery or late keying; and a year-end freeze (analytics + snapshot + anchor).

**Deliverables:**
- `workpaper.py`: the 4-sheet Excel.
- `memo.py`: the findings memo.
- `statutory.py`: the statutory revenue audit memorandum (Markdown + PDF), grouped by SA 240 / SA 550 / Ind AS 115 /
  CGST Rule 138, with an AJE summary; PROPOSED / DRAFT.
- `reports.py`: Report A (continuous) and Report B (year-end).
- `powerbi.py`: a CSV + DAX package.
- `charts.py`: daily volume z-scores, Benford χ², risk histogram and scatter.

None of them issues an audit opinion (SA 700).

## 5. AI components (all optional; off cleanly without an API key)

- **Rule:** deterministic detectors decide findings. LLMs only investigate, extract and explain; their output is always
  PROPOSED. Amounts are copied from the system, never computed by a model.
- **Multi-agent case investigation** (`investigator.py`, OpenAI Agents SDK): risk, evidence and money-flow specialists
  run in parallel over MCP with an auditor token, then a reporting agent writes the result. Cited ids that no tool
  returned are flagged. **Live run on AUD-0014: $0.0917, 41 s, 11 tool calls.**
- **In-app assistant "Ask AuditPilot"** (`assistant.py`):
  - An Agents SDK agent connected to our MCP server with **the caller's own token**, so it sees only that role's tools,
    and every call is trailed.
  - Read-only tools run freely. Write tools are only **proposed** (tool, args, why); the user presses **Run** and that
    single call executes with their token.
  - For the partner it is read-only over page data.
  - It works for Supabase accounts in their own organisation.
  - Cost ≈ $0.01–0.03 per turn.
- **CSV check agent** (`csv_agent.py`, LangGraph): profile → verify → summarise. It says whether an uploaded CSV has any
  data, and matches rows to invoices / credit notes / bills, comparing amounts and dates.
- **Guards:**
  - a CostMeter with per-run and per-day caps, and every LLM call logged
  - client text is treated as data, never as instructions
  - the partner sign-off is human-only

## 6. Multi-organisation (tenants)

- Each organisation is its own data directory: `data/` for the default, `data/tenants/<slug>/` with a `tenant.json` for
  the others. There are no org_id columns.
- The organisation is chosen per request (`X-Tenant` header) through a ContextVar, so concurrent requests stay isolated.
  This is tested with mixed concurrent requests.
- A token sees only the organisations it belongs to; choosing one never grants a role.
- The MCP gateway accepts Supabase sessions + `X-Tenant`. The role comes from that organisation's `tenant.json`;
  outsiders and the partner are refused.

## 7. Results and performance (synthetic data; a regression test, not real-world accuracy)

- **Detection:** 36 planted irregularities across 11 families (A–K + P) → **100% caught**, **0 serious (severity ≥ 4)
  false positives** on the clean year.
- **Prioritisation:** 13 invoices with R ≥ 60 out of 7,027. Company band HIGH: exposure ₹72.2 L vs performance
  materiality ₹68.4 L, circular value ₹56.4 L.
- **Cases:** 31 on the demo company.
- **Sampling:** Sales TOD 30 = 12 KEY + 5 HIGH_VALUE + 3 RP + 10 REPRESENTATIVE → 115 evidence requests.
- **Speed:**
  - upload → risk map: under 1 minute
  - analytics over 100%: 7–11 s
  - graph build: 1.3 s
  - a live edit → risk: 1–3 s
  - a money trace: 0.05–0.2 s
  - reports / memo: 0.1–0.3 s
  - peak memory: ~360 MB
- **Quality:** 168 automated tests passing, a 23-step end-to-end self-test, and an 11-check MCP smoke test
  (`scripts/mcp_check.py`).

## 8. Tech stack

- **Backend:** Python 3.11+, SQLite (WAL), `mcp>=2.3,<3` (`from mcp.server import MCPServer`; never
  `mcp.server.fastmcp`), FastAPI / uvicorn.
- **Libraries:** openpyxl, PyMuPDF, networkx, Streamlit, `openai-agents`, `langgraph`, Supabase (auth).
- **Frontend:** Next.js 16 + React 19 + Tailwind 4 + lucide-react. There is no chart library: charts are inline SVG.
- **Models:** OpenAI GPT models via `OPENAI_MODEL_DEV` / `OPENAI_MODEL_DEMO` (dev: `gpt-6.1-sol`).
- **Sponsors / integrations:**
  - OpenAI: the agents
  - n8n: webhooks
  - Voroa: hosting target **[deployment not confirmed]**
  - ShipReady / Shopify: connector idea **[not confirmed built]**

## 9. Non-negotiable engineering rules (keep these if you write code or docs)

- Identity comes only from the token; never add a role or identity parameter to a tool or endpoint.
- Auditor code never writes business data. Adjusting entries are proposals in audit.db only.
- Never clean or overwrite client data; store submissions byte-for-byte with a server-computed SHA-256.
- Money is **integer paise** (no floats, no pandas on client data); dates are ISO `YYYY-MM-DD`; the time zone is
  Asia/Kolkata.
- `journals`, `journal_lines`, `erp_log`, `audit_trail`, `submissions`, `case_events` and `risk_snapshots` are
  append-only. Every ERP write goes through `erp.write_doc`.
- Samples use a random **recorded** seed + a population snapshot.
- Client text is untrusted: server prose cites ids only, and client text goes under `client_data`. Excel string cells
  are guarded against formula injection.
- Detectors decide; LLM output is PROPOSED; confirmation and sign-off are human-only, in the web UI.
- Never commit `.env`, `identities.json`, `data/` or `*.db`.

## 10. Repository map (github.com/ELEVATE-1-0/ELEV01, branch `main`)

```
app/            Python backend: config, db, chain, money, ledger, erp, portal, intake, register, related_parties,
                analytics (D3-D15), sampling, evidence (D8, D11, D12), findings, memo, workpaper, risk_graph, explain,
                cases, money_trail, yearend, reports, statutory, powerbi, charts, csv_agent, investigator, assistant,
                tenants, accounts (Supabase), gateway + tools_client + tools_audit + mcp_server (MCP), api_server (REST),
                seed + plants (demo data), selftest, demo_audit, evaluate
schema/         erp.sql ext.sql pbc.sql audit.sql
web_v2/, web/   Next.js app (identical src)
ui/app.py       Streamlit UI (older)
tests/          pytest suite (168 tests)
scripts/        mcp_check.py, verify_trail.py (offline trail check), tamper_demo.py
vault/          specs: 01 problem statement, 02 architecture, 03 schema, 04 MCP tools, 05 detectors, 06 deliverables,
                07 stack/contracts, 09 task board, 10 integrations, 13 money trail, PROGRESS.md (log)
docs/           HOW_IT_WORKS (root), FEASIBILITY.md, MCP_GUIDE.md, WEB_APPLICATION.md, pitch/ (slides content, demo script, metrics)
```

## 11. How to run

```bash
pip install -r requirements.txt
python -m app.seed --reset              # demo company (7k invoices) + plants + identities.json
python -m app.demo_audit                # one-command audit: register upload, analytics, graph, cases, evaluation
python -m app.tenants --seed-demo       # second organisation (Sahyadri Shipyards Enterprises)
python -m app.mcp_server                # MCP on :8000
uvicorn app.api_server:app --port 8001  # REST for the web app
cd web_v2 && npx next dev -p 3300       # web app (NEXT_PUBLIC_API_URL=http://localhost:8001)
python -m pytest -q; python -m app.selftest; python scripts/mcp_check.py
```

**Connect an agent:**
`claude mcp add --transport http auditpilot http://localhost:8000/mcp --header "Authorization: Bearer <token>"`

## 12. Status and known limits

- **Status:** all core PS requirements are built and passing; the brownie points are done:
  - continuous auditing
  - a counterparty graph with cycles
  - purchases (P2P)
  - multi-entity
  - plain-language justification
  - Power BI
  - the assistant
- **Limits (stated openly):**
  - the government and bank records are simulated
  - results are on synthetic data
  - risk scores are rankings, not fraud probabilities
  - the graph sees only entities the company transacts with
  - assistant chat history is per browser session only
  - a real Supabase sign-in → assistant flow has been covered by tests with Supabase faked, not clicked through end to end
- **Judging criteria (from the ELEVATE template):**
  - problem understanding and solution clarity
  - technical depth and scaling
  - originality and differentiation
  - quality of research, prototype and presentation
- **Deck format:** at most 8 slides, no participant names, file name `<PSID>_<TEAMNAME>`.
