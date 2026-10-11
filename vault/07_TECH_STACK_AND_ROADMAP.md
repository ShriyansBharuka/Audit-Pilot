# 07 · Stack, layout, owners, contracts, 20-hour schedule

> Revised by Claude, 2026-10-10. Replaces the first draft. Team: **Shriyans** (lead), **Ibrahim**, **Darshan**, **Aarav**. AI workers: **Antigravity** (Shriyans's PC), **Claude Code #2** (teammate's Claude Pro, second PC), **Claude** (reviewer/spec owner), and **GPT credits** in-product only (`10`).

## 1. Stack (versions checked on PyPI 2026-10-10)

| Need | Choice | Why / note |
|---|---|---|
| Language | Python 3.11 | already installed on the team PCs |
| MCP server | **`mcp>=2.3,<3`** (official SDK; `from mcp.server import MCPServer`) | `pip install mcp` gives 2.3.0. `FastMCP` was renamed `MCPServer`, and `mcp.server.fastmcp` raises ModuleNotFoundError. It brings starlette + uvicorn, so **no FastAPI** is needed |
| Storage | stdlib `sqlite3`, 4 files (`03`) | zero install; `mode=ro` enforces independence |
| Excel | `openpyxl>=3.1.5` | verbatim copy + formatted sheets |
| UI | `streamlit>=1.40` (1.65 current) | Python-only, fast for a mixed-experience team; UI only, every action calls the same role-checked services |
| PDFs | `pymupdf>=1.24` | render mock evidence + extract text (already installed) |
| Stats | stdlib `statistics` (median/MAD), `secrets`, `random` | **no numpy, scipy or pandas**. Pandas coerces dates, numbers and leading zeros, which breaks "pasted exactly as provided" |
| Graph (D10) | `networkx` (optional; installed) or a 15-line DFS | brownie only |
| Investigator | `openai-agents` (0.23.x) + GPT credits | optional P1, see `10` |
| CSV verification agent | `langgraph` (1.2.x): StateGraph profile → verify → summarize, deterministic nodes; optional LLM wording via the OpenAI Responses API under the same CostMeter | optional, `app/csv_agent.py`, REST `POST /api/agents/csv-verify` |
| Web app API (added 2026-10-10 by Ibrahim's PH-6, recorded by Claude) | `fastapi>=0.143` (REST bridge `app/api_server.py` for the Next.js app in `web/`, port **8001**; needs Starlette 1.x like `mcp`, so not 0.115) | the MCP server stays the agent entry point; the REST API enforces the same token roles |
| Tunnel | `cloudflared tunnel --url http://localhost:8000` | judges' hosted agents and n8n cloud need a public URL |

`requirements.txt`:
```
mcp>=2.3,<3
openpyxl>=3.1.5
streamlit>=1.40
pymupdf>=1.24
pytest>=8
# optional
networkx>=3.3
openai-agents>=0.23
fastapi>=0.143        # web app REST API (app/api_server.py)
```

## 2. Processes and ports

| Process | Command | Port |
|---|---|---|
| Seed / reset (CLI only, never an MCP tool) | `python -m app.seed --reset [--invoices 7000] [--seed 7]` | builds the 4 DBs, `identities.json`, demo evidence, `data/answer_key.json`, and prints the judge card |
| MCP over HTTP (judges, n8n) | `python -m app.mcp_server` (env `PUBLIC_HOST`, `PUBLIC_URL`) | 8000 (`/mcp`, `/c/<token>/mcp`, `/files/<key>`, `/api/evidence/<req>`, `/connectors/shopify`) |
| MCP over stdio (local) | `MCP_TRANSPORT=stdio MCP_TOKEN=aud_… python -m app.mcp_server` | none |
| UI | `streamlit run ui/app.py` | 8501 |
| Web app API (added 2026-10-10 by Ibrahim's PH-6, recorded by Claude) | `fastapi>=0.143` (REST bridge `app/api_server.py` for the Next.js app in `web/`, port **8001**; needs Starlette 1.x like `mcp`, so not 0.115) | the MCP server stays the agent entry point; the REST API enforces the same token roles |
| Tunnel | `cloudflared tunnel --url http://localhost:8000` | none |
| Self-test | `python -m app.selftest` | none |

## 3. Folder layout

```
AGENTS.md  CLAUDE.md  README.md  requirements.txt  .env.example  .gitignore
vault/                 specs: the source of truth (read README first)
schema/                erp.sql  ext.sql  pbc.sql  audit.sql        (DDL from 03; applied by db.init_all)
app/
  config.py            paths, env, TZ='Asia/Kolkata', engagement defaults
  db.py                connect(db, role), init_all(), tx()                         [Shriyans]
  chain.py  money.py   hash chain, to_paise/fmt_inr/tax_split                       [Ibrahim]
  ledger.py            COA, post_journal, reverse_journal, trial_balance           [Ibrahim]
  erp.py               write_doc + every business service                           [Shriyans]
  portal.py            ext.db: IRN, EWB, GSTR-1/3B, bank, signatures                 [Ibrahim]
  trail.py  notify.py  audit_trail + anchors; events → n8n webhook (HMAC)           [Ibrahim]
  tenants.py           organisations as data directories, scope(), create(), seed_demo() (EX-4)
  intake.py            submit(), on_client_upload()                                 [Darshan]
  register.py          parse_verbatim, map_columns, D0 reconcile                    [Darshan]
  related_parties.py   D1 identifier graph, D2 RP timing                            [Darshan]
  analytics.py         D3–D7, D9, D10, D13, D14 → risk_hits                         [Aarav]
  sampling.py          strata, PPS, cut-off/CN selection, reproduce                 [Aarav]
  evidence.py          extract, test_sample (D8), bundle, check_for_changes (D11), verify_integrity (D12)  [Ibrahim]
  findings.py  memo.py hits → findings, AJEs, materiality, SA 450; memo md/html     [Aarav]
  workpaper.py         4-sheet xlsx                                                 [Darshan]
  playbook.py  tools_client.py  tools_audit.py  mcp_server.py   MCP layer          [Shriyans]
  investigator.py      GPT agent over MCP stdio + CostMeter (10)                    [Aarav]
  seed.py              demo company + plants + answer key                           [Darshan]
  selftest.py          end-to-end check                                             [Shriyans]
ui/app.py              Streamlit: login by token; Overview, Transactions, Investigation, Workpaper; client portal; partner review   [Antigravity → Shriyans]
adapters/voroa.py      sponsor slot (10)
connectors/shopify/    ShipReady app (10)                                           [Darshan + Claude #2]
n8n/                   exported workflow JSONs (10)                                 [Ibrahim]
scripts/               verify_trail.py  tamper_demo.py  replay_shopify.py  judge_card.py
tests/                 test_tamper.py  test_rbac.py  test_sampling.py  test_detectors.py  test_verbatim.py
data/                  gitignored: *.db  evidence/  audit_files/  answer_key.json
```

### 3a. Tenant-aware settings (EX-4)

`config.DATA_DIR`, `EVIDENCE_DIR`, `AUDIT_FILES_DIR`, `EXPORTS_DIR`, `DB_PATHS[db]`, `ENGAGEMENT_ID`, `ENTITY_NAME`,
`PERIOD_START`, `PERIOD_END` and `FY_LABEL` follow the active tenant (a ContextVar; module `__getattr__`). Read them as
`config.X` at call time, never `from app.config import X` and never as a default argument, or a request for tenant 2
would silently use tenant 1. `config.set_data_dir(path)` moves the default tenant (tests, selftest).

```python
tenants.scope(slug) -> contextmanager[tenant]        # run a block against one organisation (default when falsy)
tenants.registry() -> [tenant]; tenants.visible(principal) -> [tenant]; tenants.allowed(principal, slug) -> bool
tenants.create(name, pan, gstin, fy, principals, created_by) -> tenant   # ValueError('INVALID_ARGUMENT: …')
tenants.seed_demo(principals=None, invoices=300) -> tenant               # Sahyadri Shipyards Enterprises
config.use_tenant(settings | None) -> token; config.reset_tenant(token); config.active_tenant() -> dict | None
```

REST: `GET /api/tenants` (any signed-in identity: the tenants it may see), `POST /api/tenants` (audit roles), and every
endpoint honours `X-Tenant` (403 when the token's principal may not see that tenant; ignored without a Bearer token).

### 3b. Web sign-in with Supabase (added 2026-10-11)

The web app signs people in with Supabase Auth (e-mail + password). The Bearer token is then the Supabase session
token; agent/judge tokens from `identities.json` keep working everywhere. Since ASSIST-2 the MCP gateway also accepts a
Supabase session for an organisation (`X-Tenant`), role from that organisation's `tenant.json` only (vault/04 §2).

- `partner.identity(token)`: `identities.json` first; otherwise a JWT goes to `accounts.identity`, which asks Supabase
  (`GET /auth/v1/user`, anon key) whether the session is valid and caches the answer until the token expires. The
  project signs sessions with ES256, so the legacy HS256 JWT secret is **not** used or stored.
- Principal `sb:<user id>`; role per tenant from `tenant.json.roles` only (03 §0a). No role -> 403 `NO_ROLE`.
- Settings: `SUPABASE_URL`, `SUPABASE_ANON_KEY` in `.env` (the anon key is public). Never the service-role key.

```text
GET  /api/assistant/status                 ASSIST: {enabled, supported, mode tools|page_data, reason}
POST /api/assistant/chat                   ASSIST: SSE; Agents SDK agent over MCP with the caller's own token (+ X-Tenant)
POST /api/assistant/execute                ASSIST: the user pressed Run on ONE proposed tool call -> MCP, caller's token
GET  /api/auth/memberships                    signed-in web account -> [{slug, name, role}] (accepts pending invites)
POST /api/onboarding/organization             {name, pan, gstin, fy, membership_no?} -> new tenant; creator = engagement_partner
GET  /api/tenants/{slug}/members              that tenant's engagement partner -> members + pending invites
POST /api/tenants/{slug}/invites              that tenant's engagement partner -> {email, role} (client or audit roles)
POST /api/client/sales-register               accounts, client_admin: multipart file -> intake.submit SALES_REGISTER
POST /api/client/related-parties              client_admin: multipart file -> intake.submit RP_LIST
POST /api/client/records/{kind}               party | invoice | credit-note | journal -> erp.* (same roles and
                                              parameters as the client MCP tools; money as rupee strings)
GET  /api/client/lookups                      client roles: parties, items, recent invoices, chart of accounts
```

## 4. Module contracts (code against these; stubs first)

All money is paise; all dates are ISO strings; every function opens connections via `db.connect(db, role)`; every client write goes through `erp.write_doc`.

```python
# db.py
def connect(db: str, role: str) -> sqlite3.Connection            # 03 §6
def init_all(reset: bool = False) -> None                         # apply schema/*.sql, triggers, COA seed, PRAGMAs
@contextmanager
def tx(conn): ...                                                 # BEGIN IMMEDIATE / COMMIT / ROLLBACK

# chain.py · money.py                                             # 03 §6 (copy)
def append(conn, table: str, row: dict) -> tuple[int, str]
def verify(conn, table: str, anchors=()) -> dict
def to_paise(s: str) -> int;  def fmt_inr(paise: int) -> str;  def tax_split(taxable_paise: int, rate_bp: int, inter_state: bool) -> dict

# ledger.py
def post_journal(conn, voucher_date, voucher_type, lines: list[dict], narration, actor, role, tool,
                 source_type=None, source_id=None, reverses_no=None, aje_ref=None) -> int   # raises ValueError unless Dr == Cr > 0
def reverse_journal(conn, journal_no: int, date: str, actor, role, tool, reason) -> int
def trial_balance(conn, upto: str) -> dict[str, int]             # account_code -> net paise (Dr positive)
def seed_coa(conn) -> int                                         # called by db.init_all: 03 §2 COA via erp.write_doc (erp_log rows)

# erp.py: each service is (actor, role, **args) -> dict(result, next_steps); opens erp rw, calls portal.* when needed
def write_doc(conn, actor, role, tool, action, doc_type, doc_id, reason=None) -> int        # appends erp_log; returns seq
create_party · link_parties · create_item · create_lead · create_scheme · create_sales_order · issue_invoice ·
generate_eway_bill · record_dispatch · record_delivery · issue_credit_note · record_receipt · record_payment ·
record_purchase · post_journal_entry · file_gstr1 · file_gstr3b · amend_record · cancel_document · import_records ·
export_sales_register · render_document

# portal.py (role 'portal'; ext.db; server clock for ack_at / generated_at)
def register_irn(supplier_gstin, fy, doc_type, doc_no, doc_date, buyer_gstin, taxable_paise, tax_paise) -> dict
def cancel_irn(irn: str) -> dict                                  # refuses after 24 h
def generate_eway_bill(**f) -> dict;  def cancel_eway_bill(ewb_no) -> dict
def file_gstr1(gstin, period, omit=(), changes=()) -> dict;  def file_gstr3b(gstin, period, figures=None) -> dict
def bank_txn(account_no, value_date, amount_paise, cp_name, cp_account, cp_ifsc, utr, narration) -> str
def verify_signature(einvoice_row: dict) -> bool

# trail.py · notify.py
def trail(principal, role, tool, args, outcome, result=None, transport='HTTP') -> None   # audit_trail row with erp anchor
def anchor(engagement_id: str, label: str) -> dict
def emit(kind: str, payload: dict, engagement_id=None) -> None    # events row + optional POST to N8N_WEBHOOK_URL (X-AuditPilot-Signature: HMAC)

# intake.py · register.py · related_parties.py
def submit(kind, content: bytes, filename, submitted_by, request_id=None, declared=None) -> str   # pbc.submissions id
def on_client_upload(submission_id: str) -> dict                  # system principal: freeze rows, engagement, D0 + RP tags, event
def parse_verbatim(content: bytes, filename: str) -> tuple[list[str], list[dict]]
def map_columns(headers: list[str]) -> dict[str, str]             # knows Fig. 1 headers: 'Bill no.', 'GST No.', 'Total Cost', 'Gross Amt.' …
def reconcile(engagement_id: str) -> list[dict]                   # D0 hits
def run_d1_d2(engagement_id: str) -> list[dict];  def rp_status(party_id: str, on_date: str) -> tuple[str, str]

# analytics.py · sampling.py · findings.py · memo.py
def run_all(engagement_id, detectors=None, incremental=False) -> dict    # writes risk_hits; returns counts by detector/code + top 20
def select(engagement_id, kind, size=30, seed=None, actor='') -> dict     # first call = testing start (anchor + snapshots + requests)
def reproduce(run_id: str) -> dict;  def pps(items, k, rng) -> list
# risk_graph.py (05 §19)
def build(engagement_id) -> dict                                  # {nodes, edges, cycles, company:{band, exposure_paise, families, circular_paise}}
def on_event(doc_type: str, doc_id: str, erp_seq: int) -> list[dict]  # called by erp.write_doc after commit (best-effort); returns changed snapshots (05 §19.6)
def from_hits(engagement_id) -> list[str];  def aje(finding: dict) -> list[dict] | None;  def sa450_summary(engagement_id) -> dict

# evidence.py
def extract(submission_id) -> dict;  def test_sample(run_id, sample_no, actor, note=None) -> dict
def bundle(invoice_id) -> list[tuple[str, str]];  def check_for_changes(engagement_id) -> dict;  def verify_integrity(engagement_id) -> dict

# workpaper.py · memo.py
def build(engagement_id) -> dict                                  # {path, sha256, download_key}
```
Shared shapes (plain dicts; no class hierarchy):
- **risk_hit:** `{detector, code, object_type, object_id, severity, impact_paise, reason, evidence}`
- **finding:** as in `03 #34`
- **tool result:** `{summary, items?, next_cursor?, next_steps, client_data?}`

## 5. Ownership and AI workers

| Owner | Modules | Suggested AI worker |
|---|---|---|
| **Shriyans** | db, erp, mcp_server + tools + playbook, selftest, integration, demo | Antigravity (scaffold, wrappers, UI) + Claude reviews |
| **Ibrahim** | chain, money, ledger, portal, trail, notify, evidence, n8n workflows | Claude Code #2 or Antigravity; Claude reviews chain/anchors |
| **Darshan** | seed + answer key, intake, register, related_parties, workpaper, ShipReady connector | Antigravity (seed bulk, xlsx) + Claude Code #2 (RP graph, ShipReady) |
| **Aarav** | analytics, sampling, findings, memo, investigator | Claude Code #2 (audit brain) |

Rule: you edit only your modules; for anything else, ask the owner or write it in `PROGRESS.md`. Changing a contract (03/04/07 §4) means editing the vault in the same commit.

## 6. Schedule: **submission 08:00 IST, 11 Oct 2026** (format: PPT + working prototype)

**What we ship (decided 14:30):**
1. **One web application**, not a marketing website. It's the Streamlit app (client portal, auditor workspace with Overview / Transactions / Investigation / Risk graph / Workpaper, partner review) plus the MCP endpoint that judges' agents use. Its home page doubles as a 1-screen landing ("what it is, how to connect, judge card"), which covers anything a website would.
2. Deployed on **Voroa** (`10 §3`).
3. The **PPT** (~10 slides: problem → system of record → independence/MCP → 100% detection + risk graph → live demo flow → deliverables → sponsors → architecture → team).

Revised end-game (T0 = 12:30). The hours below stay valid up to T15; the rows after it replace the old T15–T20 rows:
- **T15–T17 (03:30–05:30):** deploy on Voroa and re-run the judge simulation against the Voroa URL; finish the PPT and the demo video backup (screen recording, in case the live demo fails).
- **T17 (05:30): feature freeze.**
- **T17–T19 (05:30–07:30):** final clean seed on Voroa, full selftest, rehearsal, push.
- **Submit by 07:30** (30 min buffer).

| When | What | Exit check |
|---|---|---|
| **Now** (before T0) | Shriyans: repo skeleton + `pip install -r requirements.txt` + Gateway hello (`whoami` over stdio and HTTP). Ibrahim: `chain.py`, `money.py` + test_tamper. Darshan: seed skeleton (company, 2 units, ~150 customers, ~40 items, Fig. 1 export). Aarav: `pps`, strata, control-date function + unit tests | each runs locally |
| **T0–T1** | Contract freeze: `schema/*.sql` from 03, every module stubbed with valid return shapes, `python -m app.selftest` green on stubs | selftest passes |
| **T1–T6** | **P0 build** in parallel (§7) | each module's done-when in `09` |
| **T6** (~18:30) | **Integration #1** on a 300-invoice seed: seed → export → doctored upload → Sheet 1 → analytics → samples → evidence → test → findings → xlsx/memo. Claude reviews the code | E2E runs |
| **T6–T11** | Finish P0; P0.5 (n8n); P1 (investigator, PDF extraction, UI pages, D10) | — |
| **T11** (~23:30) | **Judge simulation:** a fresh Claude Code session with only the URL + client token ("run the business for a day; plant 3 irregularities"), then only the auditor token ("audit FY 2025-26 revenue"). Log every stall → fix descriptions/errors. Recall run vs `answer_key.json` | 100% recall; no stalls |
| **T11–T15** | Fix misses and false positives; ShipReady (3 h time box); Voroa once its docs arrive; deliverable polish. Sleep in two 3-hour shifts | — |
| **T15–T17** | README + judge card + connection commands, demo script, slides, rehearsal | rehearsal under 7 min |
| **T17** | **Feature freeze.** Only bug fixes after this point | — |
| **T17–T20** | Final clean seed, full selftest, push, buffer | tagged commit pushed |

## 7. Cut lines

- **P0 (must):**
  - 4 DBs + chain + ledger + erp_log + trail + anchors.
  - Identity/roles/Gateway (stdio + HTTP).
  - Client tools: lifecycle + upload_sales_register (edits) + upload_related_parties + amend/cancel + post_journal_entry + file_gstr1 + generate_eway_bill + import_records + render_document/upload_evidence.
  - Detectors D0, D1 (GSTIN + STRONG/MEDIUM edges), D2 (dates), D3, D4, D5 (sales + discounts), D6 (IRN/EWB/GSTR-1/tax type), D7, D8 (hash/number reuse + structured field match), D9, D11, D12, D13.
  - Sampling: 3 kinds + reproduce.
  - Findings + AJEs, the 4-sheet xlsx, memo, trail export + verify script, partner confirm/sign-off (UI).
  - Seed with plants + answer key; selftest.
- **P0.5:** n8n (upload notify, evidence emails + reminders, scheduled monitoring); a minimal Streamlit (login, client portal, partner review).
- **P1:** investigator (GPT); PDF text extraction + D14; full UI views; D10 cycles; MCA mock; GSTR-3B; RP price test; ShipReady connector; Voroa slot.
- **P2:** LLM vision for scanned or Hindi/Marathi documents; multi-entity; on-prem local model; purchases/inventory extension; React UI; docx memo.

## 8. Acceptance tests (the whole team's definition of done)

1. `test_tamper.py`: the four cases in 03 §6 (edit without rehash, rehash, rewritten tail vs anchor, direct UPDATE with triggers dropped).
2. `test_rbac.py`: every (tool, role) pair not in `TOOL_ROLES` gives PERMISSION_DENIED + a DENIED trail row, and **erp.db stays byte-identical**. An audit-role `connect('erp', …)` INSERT raises `attempt to write a readonly database`. A client-role `connect('audit', …)` raises PERMISSION_DENIED. The partner token is rejected on MCP.
3. `test_sampling.py`: the same seed + population gives identical picks; size 25–35; ≥3 RP; ≤3 per customer; every pick has a reason; `reproduce_selection.identical == True`.
4. `test_verbatim.py`: Sheet 1 equals the uploaded file cell for cell (values + number formats) plus the auditor columns; `=HYPERLINK(…)` text stays a string; CSV leading zeros survive.
5. `test_detectors.py`: on the seed, every `answer_key.json` plant has a matching `risk_hits` code, and the false-positive count is printed.
6. `python -m app.selftest`, end to end: seed → export → doctored upload → analytics → samples → render/upload evidence (one forged) → test_sample → amend an LR date after testing → `check_for_changes` names the sample → deliverables → partner confirm → sign-off → `scripts/verify_trail.py` OK.
7. Judge simulation (§6 T11) completes without human hints.

## 9. Judge runbook

```bash
pip install -r requirements.txt
python -m app.seed --reset                       # prints the judge card (tokens per role)
# Production: deploy both services on Voroa (10 §3) and use its https host below.
cloudflared tunnel --url http://localhost:8000   # fallback only (laptop): copy the https host
set PUBLIC_HOST=<host> & set PUBLIC_URL=https://<host>/mcp     (PowerShell: $env:PUBLIC_HOST="<host>")
python -m app.mcp_server                         # HTTP MCP on :8000
streamlit run ui/app.py                          # partner + client portal on :8501
```
Connection commands for Claude Code, Claude Desktop, Cursor and header-less hosts are in `04 §7`. Never expose the partner token to an agent.
