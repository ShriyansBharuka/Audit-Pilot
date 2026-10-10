# How AuditPilot AI works

> A plain-language overview for the whole team. The exact specs live in `vault/`; this file explains the big picture so anyone can follow the code, the demo and the PPT. Who does what: [`WHO_DOES_WHAT.md`](WHO_DOES_WHAT.md).

## 1. The problem in one paragraph

A statutory auditor gets an Excel **sales register** from a company (6,000–8,000 sales a year) and can only check a few dozen sales by hand. The auditor never sees the company's real systems, so fake invoices, sales booked in the wrong year, hidden related-party sales and circular trading slip through behind paperwork that looks complete. The problem statement asks for a system that audits **the business itself, not just the spreadsheet**. It must be run end to end by an AI agent that can't change the business's data, and it must produce the workpaper a CA would sign.

## 2. Our answer in one paragraph

We build a **mini version of the company's business system** (orders → dispatch → invoice → payment), which posts to a **tamper-evident ledger** and to **mock government portals** (e-invoice, e-way bill, GST returns, bank). When the company uploads its sales register, we **compare 100% of it** against that system, run 15 detectors (D0–D14) plus our **AuditGraph** risk engine, and pick risk-based samples. We then request evidence from the company automatically, test it, and produce the **4-sheet workpaper, findings memo and audit trail**. Everything is exposed through an **MCP server**, so any AI agent (including the judges') can run the business as a company employee or audit it as the auditor, with exactly its token's permissions. **A human partner signs off every conclusion.**

## 3. The pieces

```
        Judges' AI agent / our GPT investigator / n8n / ShipReady app
                              │  (each holds a token = an identity)
                              ▼
   ┌──────────────── MCP server (python -m app.mcp_server) ────────────────┐
   │ Gateway: token → role → only that role's tools are visible/callable   │
   │ every call (allowed or denied) is written to the hash-chained trail   │
   ├──────────────────────────────┬────────────────────────────────────────┤
   │ Client tools (run business)  │ Audit tools (audit the business)       │
   └──────────────┬───────────────┴───────────────┬────────────────────────┘
                  │ read-write                    │ READ-ONLY (enforced by SQLite)
                  ▼                               ▼
   erp.db  the company's system of record ─── ext.db  "government" + bank records
   (orders, dispatches, invoices, credit notes,   (IRN, e-way bills, GSTR-1/3B,
    receipts, ledger, erp_log edit history)        bank statement)
                  │                               │
   pbc.db  evidence requests ⇄ client uploads     audit.db  the auditor's file
                                                  (workpaper, samples, findings,
                                                   risk scores, anchors, audit trail)
                              ▲
        Streamlit web app (client portal · auditor workspace · partner sign-off)
```

| Piece | What it does | Built with |
|---|---|---|
| **Mini ERP** (`erp.py`) | The company's real records: enquiry, sales order, dispatch/LR/POD, invoice, credit note, receipt | Python + SQLite |
| **Ledger** (`ledger.py`, `chain.py`) | Every invoice/CN/receipt posts balanced debits and credits. Nothing is ever edited, only reversed. Every write is hash-chained | Python `hashlib` (ported from Ibrahim's ReliefNet ledger) |
| **Mock government portals** (`portal.py`) | Generate IRN and e-way bill numbers and store GST filings and bank entries independently, so the company can't quietly change them | SQLite `ext.db` |
| **Audit engine** (`register.py`, `related_parties.py`, `analytics.py`, `evidence.py`) | Compares the register with the system, runs detectors D0–D14, tests evidence, detects changes after testing began | Python stdlib |
| **AuditGraph** (`risk_graph.py`) | Risk engine: a graph of the company, customers, vendors, directors and money flows; risk scores per invoice and per company; circular-trading value; risk history over time | networkx |
| **Sampling** (`sampling.py`) | Picks 25–35 Sales TOD samples, the cut-off samples and the credit-note samples, with a recorded random seed and a reason for every pick | Python `random` (reproducible) |
| **Deliverables** (`workpaper.py`, `memo.py`) | The 4-sheet Excel workpaper in the same layout as the PS figures, the findings memo with adjustments, the trail export | openpyxl |
| **MCP server** (`gateway.py`, `mcp_server.py`) | The front door for every agent: 46 tools, token-based roles, paginated results, clear errors | official `mcp` SDK 2.3 |
| **Web app** (`ui/app.py`) | Client portal (uploads, evidence), auditor workspace (overview, transactions, investigation, risk graph, workpaper), partner review + sign-off | Streamlit |

## 4. Who can do what (identities)

Every agent or person holds a **token**. The token decides the role, and the server enforces it. Nobody can just *claim* to be the auditor.

| Role | Who | Can |
|---|---|---|
| `sales`, `warehouse`, `accounts`, `client_admin` | company employees (or a judge playing the company) | run the business, upload the register and RP list, answer evidence requests |
| `audit_staff` | the auditor AI (the judges' agent or our GPT investigator) | read everything, run tests, pick samples, **propose** findings; **can never change business data** |
| `orchestrator` | n8n | check status, run scheduled tests, read events |
| `engagement_partner` | a **human** CA | confirm/reject findings and sign off, **only in the web app, never via MCP** |

## 5. The workflow, step by step

**A. The company runs its business (all year).** Through client tools: `create_lead` → `create_sales_order` → `issue_invoice` (an IRN is generated on the mock portal) → `generate_eway_bill` → `record_dispatch` → `record_delivery` → `record_receipt`. Every step writes to `erp.db`, posts to the ledger and appends to the hash-chained edit log.

**B. The company uploads its register.** `upload_sales_register` + `upload_related_parties` (MCP) or the client portal page. The file is stored **exactly as given**, with a SHA-256 fingerprint.

**C. "The system is notified."** The upload triggers the audit pipeline automatically, and n8n sends the auditor a message.

**D. Sheet 1: the Sales Register.** It's pasted exactly as provided, plus auditor columns: does each row match the system, and is the customer a related party (traced through shared PAN / GSTIN / bank / phone / directors, with dates)?

**E. Test 100% of the population.**
- **D0** compares the register with the system: every difference is a finding.
- **D1–D14** cover the other PS families:
  - related parties: D1 identifiers, D2 relationship dates;
  - wrong year by delivery terms: D3 cut-off;
  - turnover with no physical movement: D4;
  - year-end spikes in sales and discounts: D5;
  - invoice vs e-way bill vs IRN vs GSTR-1 mismatches: D6;
  - revenue journal entries with no sale behind them: D7;
  - credit notes after year end: D9;
  - circular trading: D10;
  - backdating: D13;
  - plus evidence (D8), changes after testing (D11), integrity (D12) and instruction text hidden in documents (D14).

**F. AuditGraph scores the risk** (full spec: `vault/05 §19`).
- **Continuous, not just at upload.** Every business event (invoice, dispatch, payment, credit note, edit) updates the graph and the affected risk scores the moment it happens. The register upload triggers the bigger annual-audit run (reconciliation, every detector, a full graph rebuild, sampling).
- **Transaction score:** `A` = the invoice's own anomaly score from its detector hits.
- **Entity score:** `E = 0.35·C + 0.25·F + 0.15·T + 0.15·H + 0.10·N`:
  - circular-trading exposure (C);
  - significance of suspicious flows (F);
  - temporal anomalies (T);
  - unresolved exceptions (H);
  - counterparty/network risk (N), read from the *previous* round so scores can't feed back into themselves and escalate.
- **Combined:** `R = 0.7·A + 0.3·E`, and hard evidence (a fake e-way bill, no dispatch) never drops below High.
- **Circular trading** uses the minimum-span cycle decomposition from the 2017 paper. It finds time-ordered directed cycles and measures how much ₹ is genuinely circular, with the original history kept alongside the residual flows. It does not flag every cycle it finds.
- Each score carries a **confidence**, the whole company gets a **LOW / MODERATE / HIGH** flag, and every score is kept over time (history is never overwritten).

**G. Pick samples.**
- Sales TOD of 25–35 items: the riskiest first, then high-value, related parties, then risk-weighted random picks across customers.
- Cut-off TOD: the last 10 invoices before 31 March + the first 15 after.
- Credit Note TOD.

The seed is recorded, so anyone can re-run the selection and get the identical picks.

**H. Evidence requested automatically.** The client sees what's requested (never *why*), n8n emails them with reminders, and they upload the invoice, e-way bill, LR and POD.

**I. Test the evidence.** The server hashes and reads each document and checks it against the system and the government portal: same e-way bill? same vehicle? does it belong to another invoice? was it reused?

**J. Watch for tampering.**
- If the company changes anything after testing started (e.g. edits a lorry-receipt date), `check_for_changes` names the field, the old and new values, who did it and which samples are affected.
- If someone edits the database file directly, `verify_integrity` catches it through the hash chains and the auditor-held anchors.

**K. Findings and adjustments.** Each finding gets plain-language reasons, the standard (SA / Ind AS / GST), the ₹ impact and a proposed adjusting entry, with status **PROPOSED**.

**L. Human sign-off.** The partner reviews in the web app and confirms or rejects each finding, then signs off. The workpaper, memo and trail are regenerated as FINAL, and anyone can verify the trail offline with `scripts/verify_trail.py`.

## 5b. The web app and the Audit Investigation Explorer

The Streamlit app (`ui/app.py`) is **just another MCP client**: every client and auditor click calls the same MCP tools with the logged-in user's token. It gets exactly that identity's permissions, and every click lands in the audit trail. Only the partner's decisions bypass MCP (`app/partner.py`), on purpose, because the partner token is refused by the MCP server.

| Role | Pages |
|---|---|
| Client roles | **Client portal**: upload the register / RP list; see evidence requests; upload a file or attach the system's official copy |
| `audit_staff` | **Overview** (company risk band, counts, one-click audit steps) · **Investigation Explorer** · **Workpaper** (the 4 sheets, deliverables, submit for review) |
| `engagement_partner` | **Partner review**: confirm / reject / modify each finding (a comment is mandatory), then sign off. Blocked while anything is PROPOSED, stale or failing integrity |

**Audit Investigation Explorer** (Aarav's design). Start from a suspicious company, follow its connections, open a transaction, see its documents and exactly why it's risky, and trace every change, all in one place:
1. **🕸 Network View.** The AuditGraph neighbourhood as a graph: colour = risk band, solid edges = transactions, dashed = identity links (shared PAN/bank/phone/director). It shows circular flows with their ₹ circular value. Select an entity to focus on it, or a transaction to open it.
2. **🧾 Transaction Timeline.** The full paper trail of one sale in date order: enquiry → order → invoice → IRN → e-way bill → dispatch/LR → POD → GSTR-1 → payment → credit notes → ledger postings, with missing links shown as gaps. AuditGraph's risk history is overlaid (R, A, E over time, with the trigger and reasons for each change).
3. **📎 Evidence & Change History.** Why it's risky (every detector hit with code, severity, ₹ impact and a plain-language reason); the supporting documents the client uploaded (with SHA-256, who and when); the system's official copies; the hash-chained edit log for the invoice, its dispatches and its order, with field-level before → after; and any changes after testing began, with the stale samples.

## 6. Tech we use, and why

| Need | Choice | Why |
|---|---|---|
| Language | Python 3.11 | the whole team knows it |
| Database | SQLite (4 files) | zero install; read-only connections physically block the auditor from writing |
| AI agent access | official `mcp` SDK 2.3 | the PS requires an MCP server; judges plug in their own agent |
| Web app | Streamlit | fast to build, Python only; no separate website |
| Graph | networkx | cycles and paths for AuditGraph |
| Excel | openpyxl | the 4-sheet workpaper in the PS figure layout |
| PDFs | PyMuPDF | render and read evidence documents |
| LLM (optional) | OpenAI GPT-6 (Luna for extraction, Sol for dev, Astra for the final demo) | investigator agent + reading scanned documents; capped at <$100 of our $700 |
| Not used | pandas, FastAPI, PostgreSQL, React | they break "pasted exactly as provided", add services Voroa can't spare, or cost build time |

## 7. Sponsors: where each one shows up

| Sponsor | Role in our product |
|---|---|
| **Voroa** | Hosting: both services (the MCP server + the web app) run there on 2 vCPU / 4 GB, CPU only. Judges connect to the Voroa URL |
| **n8n** | Automation: upload notifications, evidence-request emails + reminders, scheduled monitoring (continuous auditing). It calls our MCP server with its own limited token |
| **ShipReady** | A Shopify app (built on the ShipReady boilerplate) that feeds online orders, discount codes and refunds into the system of record, like a real sales channel |
| **OpenAI** | Our AuditPilot investigator agent (just another MCP client with an auditor token) + document reading |

## 8. Our data

We generate a **synthetic but realistic company** (*Konkan Marine Controls Ltd*, fictional): FY 2025-26, ~7,000 invoices, 2 factories, ~150 customers, directors and relatives. We plant irregularities in it (at least 2 per family, some easy and some sneaky) and keep the list in `data/answer_key.json`, which the engine **never reads**. We use that key only to measure precision and recall for the PPT. Judges can also plant their own irregularities live through the client tools.

## 8b. Honest limitations (also a PPT slide)
- **The "government" and bank records are simulated by us.** A separate read-only database shows *how* the system would check against real portals and bank feeds; it doesn't make our demo records independently trustworthy.
- **The graph only sees entities we have transactions for.** It can't trace money through trading partners' other books, so cycles are shown through the company itself, shared identifiers, or the small synthetic group network we include for the demo.
- **The weights are provisional.** Scores rank risk; they are not fraud probabilities. Results are prototype performance on our synthetic data.

## 9. The demo (~7 minutes)

1. Show the judge card: the auditor token can't even *see* the client tools.
2. **Replay the year** in fast-forward and watch AuditGraph's risk scores move. An invoice turns High when a post-year-end credit note lands.
3. As the **client**: plant three things live (a 31-Mar invoice shipped 2-Apr, a customer sharing a director's bank account, a manual journal crediting sales) and upload a doctored register.
4. As the **auditor**: reconcile → analytics → samples (show the seed and reasons) → the client uploads evidence (one forged) → it's caught.
5. The client edits a lorry-receipt date: the stale sample is named. Edit the database file directly: the integrity check catches it.
6. n8n notifications along the way. The partner signs in the web app. Open the Excel workpaper + memo, then verify the trail offline.

## 10. How to run it (once built)

```bash
pip install -r requirements.txt
python -m app.seed --reset        # builds the company, the plants and the tokens (prints the judge card)
python -m app.mcp_server          # MCP server on :8000 (MCP_TRANSPORT=stdio for local agents)
streamlit run ui/app.py           # web app on :8501
python -m app.selftest            # end-to-end check
python -m app.evaluate            # precision / recall / ablation for the PPT
```
Connecting an agent (e.g. Claude Code): `claude mcp add --transport http auditpilot-auditor https://<voroa-host>/mcp --header "Authorization: Bearer aud_…"`. More in `vault/04 §7`.
