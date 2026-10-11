# AuditPilot AI: content for the ELEVATE 1.0 template (8 slides)

This follows `final elevate tempelate.pdf`: the title slide, the 6 fixed section slides, and the **one extra slide
allowed** (we use it for results + demo), 8 in total.

**Before you submit:**
- **Delete the template's "Instructions" page.**
- **No participant names anywhere** (that includes team photos, signatures, a GitHub username shown in a link preview).
- File name: **`<PSID>_<TEAMNAME>`**, for example `PS04_<teamname>.pdf` **[confirm the exact PS ID format and team name]**.
- Every link must open for a stranger: check the GitHub repo is public (or share a view-only link), and that the demo
  video is "anyone with the link".

**Layout tip for the light-blue template:**
- **Text:** navy on the sky background. Each section slide already has its 3 bullets as headings, so put our content
  under each heading as 2–4 short lines, or as a small table.
- **Images:** screenshots of our dark app read well as framed cards with a thin white border.
- **Numbers:** one bold number per block (the slides are judged as "evidence-led").

Every number below is measured on our synthetic demo company (`docs/FEASIBILITY.md`, `docs/pitch/metrics.json`,
`vault/PROGRESS.md`).

---

## Slide 1: Title (template page 1)

**Team Name:** `<team name>` **[confirm; no member names]**

**PS ID:** `PS-04` **[confirm the official ID format]**
**PS Name:** AI-Run Statutory Revenue Audit

**Abstract** (about 75 words; fits the box):
> Auditors vouch 30 of 7,000 invoices and never see the company's real systems. AuditPilot AI rebuilds the business:
> orders, dispatch, invoices, payments, purchases, on a tamper-evident ledger beside mock GST, e-way bill and bank
> records. It tests **100% of them** against the register the client uploads, ranks risk with a graph engine and follows
> the money. AI agents work over MCP with **identity-bound permissions**; they investigate and draft, and a **human partner
> signs**. Every action is hash-chained.

---

## Slide 2: Proposed Solution (template page 2)

### Proposed Solution and Core Concept
- **Audit the business, not the spreadsheet.** A mini ERP (enquiry → order → dispatch → invoice → payment, plus
  PO → goods receipt → bill → payment) posts to a double-entry ledger and to mock IRP / e-way bill / GSTR / bank records.
- The client's uploaded register is compared with that system **row by row**. *Every difference is a finding, never a
  cleaning step.*
- **The AI proposes; the human partner signs.**

### Key Functionalities and Detailed Approach
Draw this as a 6-step flow (arrows, left to right):
1. **Upload:** the register and related-party list, stored byte-for-byte with SHA-256.
2. **Test 100%:** 16 detectors (D0–D15) over every invoice, credit note, journal, payment and purchase.
3. **Rank:** the AuditGraph risk engine: transaction + counterparty risk, and circular trading.
4. **Sample + request evidence:** a risk-based Sales TOD (25–35 items), cut-off and credit-note TOD, with a recorded seed
   and a reason for every pick; requests go to the client automatically.
5. **Investigate:** cases, a money trail (books vs bank), and AI agents that cite record ids.
6. **Deliver:** the 4-sheet Excel workpaper, the statutory memo with adjusting entries, the hash-chained trail, and
   partner sign-off.

### Problem – Solution Alignment
Small 2-column table:

| The PS needs | AuditPilot |
|---|---|
| Register copied *exactly as given* | Sheet 1 = the client's file, cell for cell |
| Risk-based, reproducible samples | Recorded seed + population snapshot; `reproduce_selection` gives identical picks |
| Cut-off by transfer of control | Delivery terms + LR / POD / e-way bill dates, not the invoice date |
| Agents with identity-based permissions | MCP server: the token decides the role; an auditor can never write business data |
| Detect changes after testing began | "Sample 12 is stale: its LR date was changed by warehouse user X" |
| Human sign-off | Partner-only, in the web app; the partner token is refused over MCP |

**Visual:** the flow diagram + one screenshot of the Overview page.

---

## Slide 3: Technical Approach (template page 3)

### System Architecture and Overall Workflow
**Diagram** (the main visual on this slide):
- **Top:** AI agents (judges' agent, our agents, n8n) and the web app, all through **one MCP gateway**. Token → role → only
  that role's tools; every call, including refused ones, goes to the audit trail.
- **Bottom:** 4 SQLite files:
  - **erp.db:** the company's books. The auditor's handle is **read-only, enforced by SQLite itself**.
  - **ext.db:** mock government and bank records.
  - **pbc.db:** evidence requests ⇄ client uploads.
  - **audit.db:** the auditor's file; client roles get no handle at all.

### Technologies, Frameworks and Models
- **Backend:** Python, SQLite (WAL), official **MCP SDK 2.3** (53 tools, 6 roles), FastAPI.
- **Frontend:** Next.js + Tailwind; sign-in with Supabase.
- **AI:**
  - **OpenAI Agents SDK:** a 4-agent case investigation, and an in-app assistant over MCP.
  - **LangGraph:** a CSV verification agent.
  - **GPT models**, under a hard daily cost cap.
- **Analytics:**
  - graph cycle decomposition
  - **exact Shapley values** to explain each risk score
  - Benford and z-score analytics
- **Outputs:** openpyxl (Excel workpaper), PyMuPDF (PDF memo), a Power BI dataset (CSV + DAX), and n8n signed webhooks.

### Implementation and System Components
Icon grid with one line each:
- **Ledger + hash chain:** append-only tables, SHA-256 chained edit log, auditor-held anchors.
- **16 detectors:** the register, related parties, cut-off, movement, GST portals, journals, credit notes, cycles,
  backdating, prompt-injection, and purchase-to-pay.
- **AuditGraph:** risk score R = 0.7·transaction + 0.3·entity, with a hard-evidence floor and a company risk band.
- **Cases + money trail:** books (CLAIMED) vs bank (VERIFIED) vs identity links (INFERRED).
- **Deliverables:** the workpaper, statutory memo, reports A/B, and the offline trail verifier.
- **Multi-organisation:** each client organisation is its own set of books + engagement.

---

## Slide 4: Innovation and Uniqueness (template page 4)

### Innovative Approach and Core Differentiators
- **We audit a working system of record, not an exported spreadsheet**, cross-checked against independent government
  and bank records.
- **Auditor independence is enforced by the database**, not by code paths: SA 200 made physical.
- **Agents are first-class but cannot overstep:** any MCP agent (including the judges') gets exactly its token's
  permissions, and AI writes are only *proposed* until a human presses Run.

### Unique Features and Functionalities
- **Follow-the-money cases** with three numbers kept apart: *recorded*, *bank-verified*, *potentially affected*.
  Example: ₹5,00,000 paid, 60 of 100 units received → ₹2,00,000 to investigate, and "where the money went next: not
  established" (no over-claiming).
- **Circular trading measured, not just flagged:** minimum-span decomposition counts each rupee in a cycle once.
- **Tamper-evident everything:** a client edit after testing names the field, the old and new values, the user, and the
  stale sample; a direct database edit fails the integrity check.
- **Prompt-injection safe:** client text is data. A customer named "IGNORE PREVIOUS INSTRUCTIONS…" is flagged (D14) and
  is never obeyed (tested live).
- **Explainable scores:** exact Shapley attribution shows why each invoice scored what it did.

### Comparison with Existing Approaches
Table (keep it factual):

| | Manual sampling (Excel) | Typical audit analytics tools (data extracts) | **AuditPilot AI** |
|---|---|---|---|
| Coverage | 25–35 invoices | Full extract, analysed offline | **100%, continuously, as records change** |
| Source of truth | Register given by the client | Client's ledger extract | **System of record + GST / e-way bill / bank records** |
| Detects post-test edits | No | Rarely | **Yes: field, old/new value, user, stale sample** |
| Agent access | — | — | **MCP, identity-bound, every call trailed** |
| Who decides | Auditor | Auditor | **Detectors propose, AI explains, partner signs** |

---

## Slide 5: Feasibility and Viability (template page 5)

### Technical and Operational Feasibility
**It runs today**, end to end, on a 7,000-invoice company:

| | Measured |
|---|---|
| Full audit: upload → risk map | **under 1 minute** |
| Analytics over 100% of the books | 7–11 s |
| Live client edit → risk updated | 1–3 s |
| Money trace / case view | 0.05–0.2 s |
| Peak memory | ~360 MB |

- **Operational fit:** the same SA / Ind AS / CGST references auditors already use are cited on every hit, and the
  deliverables are in the PS's own workpaper layout.

### Scalability, Deployment and Resource Requirements
- **Deployment:** CPU-only; runs on 2 vCPU / 4 GB; no GPU, no model hosting.
- **Processes:** two services (the MCP server and the web/API), with the four SQLite files per organisation.
- **Scaling:** organisations are separate data folders, so they scale out per tenant. A 70,000-invoice year is about
  10× the timings (≈2.5 min batch); the per-event risk update stays flat.
- **LLM cost:**
  - the deterministic audit uses **no LLM**
  - one 4-agent investigation: **$0.09** (measured)
  - one assistant answer: **$0.01–0.03**
  - a hard daily budget cap, and every call metered

### Challenges, Risks and Sustainability
- **Simulated portals:** the e-invoice, e-way bill, GSTR and bank records are mocks. All portal access goes through one
  module, so real connectors replace one file.
- **Risk scores are rankings, not fraud probabilities:** findings are decided by deterministic detectors, never by the
  LLM.
- **LLM misuse or injection:** read-only tools only, writes proposed, client text treated as data, partner sign-off
  human-only.
- **Sustainability:** a spec "vault" + 168 automated tests + a 23-step self-test keep it maintainable. Every shortcut is
  marked with its upgrade path.

---

## Slide 6: Impact and Scaling (template page 6)

### Target Users and Areas of Application
- **Statutory auditors / CA firms:** revenue and purchase audits, especially mid-size firms without Big-4 tooling.
- **Companies' internal audit and finance teams:** continuous monitoring before the year-end audit.
- **Also:** GST and forensic reviews (fake turnover, circular trading, undisclosed related parties).

### Expected Impact and Key Benefits
- **Coverage:** from 30 invoices to **100%**. Odds of catching 1 of 10 hidden frauds by random sampling: **4.2%**.
- **Focus:** of 7,027 invoices, **13** are prioritised for a human to look at first.
- **Trust:** every conclusion traces to record ids, every action is hash-chained, and a human signs.
- **Speed:** a year-end cut-off review that took days of vouching becomes a ranked list of 6 March→April exceptions.

### "YC says yes tomorrow. Can it handle success next week?"
Put this as a confident checklist:

| Concern | Our answer |
|---|---|
| **Users** | Each organisation is isolated in its own data folder; per-request tenant selection; tested with concurrent mixed-tenant requests (20 at once, 0 leaks). |
| **Breaks** | **168 automated tests**, a **23-step end-to-end self-test**, an **11-check MCP smoke test**; all run before every commit. |
| **Crashes** | Stateless HTTP for the MCP server; SQLite WAL; deterministic re-runs (`run_analytics` is idempotent; cases rebuild idempotently). |
| **Robustness** | Append-only tables + hash chains, so nothing is silently lost or altered; the LLM is optional and switches off cleanly (503, panel hidden). |
| **Scaling path** | Move from SQLite to Postgres per tenant (same schema); queue long analytics runs; add read replicas for the API. |

---

## Slide 7: Research and References (template page 7)

### Research Background and Supporting Evidence
- **Why 100% testing:** a 30-item random sample from 7,000 catches ≥ 1 of 10 planted items with probability
  1 − C(6990,30)/C(7000,30) ≈ **4.2%**.
- **Our evaluation:** 36 planted irregularities across 11 families → **100% caught, 0 serious false positives**, with
  the answer key held out from the engine. (This is our synthetic data: a regression test, not a real-world accuracy
  claim.)
- Grounded in the auditing and tax rules the PS cites (below).

### Datasets, Papers, Sources and References
- **Dataset:** a synthetic company, Konkan Marine Controls Ltd (fictional): FY 2025-26, 7,587 invoices (7,027 in the
  FY), 2 factories, ~150 customers, directors and relatives, plus planted irregularities; seeded and reproducible.
- **Standards:**
  - ICAI SA 200, 230, 240, 315, 320, 330, 450, 500, 520, 530, 550, 560, 700
  - Ind AS 115, 24, 10
  - Companies Act 2013 s.143(12), s.144, s.188; CARO 2020
  - CGST Act s.34; Rules 46, 48, 138
- **Methods:**
  - Shapley-value explanations (Lundberg & Lee, 2017, "A Unified Approach to Interpreting Model Predictions")
  - Benford's law for audit analytics (Nigrini)
  - minimum-span cycle decomposition for circular trading (Kumar et al., 2017) **[confirm the exact citation]**
  - OWASP Top 10 for LLM Applications (LLM01 prompt injection)
  - Model Context Protocol specification (modelcontextprotocol.io)

### Demo, Competitor Analysis, GitHub or Supporting Links
- **GitHub:** `https://github.com/ELEVATE-1-0/ELEV01` **[confirm public / view access]**
- **Demo video (2.5 min):** `<link>` **[upload; "anyone with the link"]**
- **Live app / MCP endpoint:** `<hosted URL>` **[confirm hosted]**
- **Competitor analysis:** one line pointing back to the comparison table on slide 4.

**Visual:** a QR code for the repo and one for the video.

---

## Slide 8: Results and Live Demo (the one extra slide allowed)

**Title:** RESULTS AND LIVE DEMO (same header style as the others)

**Left half: evidence** (big numbers, one per line):
- **100%:** planted irregularities caught (36 / 36, 11 families)
- **0:** serious false positives on the clean year
- **16** detectors · **53** MCP tools · **6** roles
- **₹2,00,000:** the ABC case: paid ₹5 L, received 60 / 100 units, bank-verified
- **$0.09:** one live 4-agent AI investigation (41 s, 0 invented ids)

**Right half: the demo in 5 beats** (with small screenshots):
1. An auditor agent tries to create an invoice → **refused and logged**.
2. The client plants a 31-Mar invoice shipped 2-Apr and doctors the register → **both caught, with reasons and ₹ impact**.
3. "Trace this ₹5 lakh payment" → the money trail separates books from bank.
4. "Ask AuditPilot" → it answers with ids; a write appears as a **Run / Dismiss** card.
5. The client edits an LR after testing → the stale sample is named; the partner signs; the trail verifies offline.

**Footer line:** *"Connect your own agent and try to fool it"* + the MCP command or a QR code.

---

## If you must cut to 7 slides
Drop slide 8 and move its "big numbers" into Slide 5 (feasibility table) and Slide 7 (research evidence).
