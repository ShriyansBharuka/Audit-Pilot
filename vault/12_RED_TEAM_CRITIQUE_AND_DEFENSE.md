# 12 · Red team: the objections judges will raise, and our honest answers

> **Purpose:** the defence playbook for AuditPilot AI. Every realistic objection from judges, sceptical Chartered
> Accountants, IT security reviewers and regulators (ICAI / NFRA), with the answer **as the code stands**.
> Anything we haven't built is marked **(roadmap)**: never claim it as done on stage.
> Fact-checked by Claude against the repo on 2026-10-10 21:30 (commit 12214c1); legal points checked against public
> sources (links at the end).

---

## Summary matrix: the six fronts

| Front | The objection | Our answer |
| :--- | :--- | :--- |
| **1. Legal & regulatory** | *"NFRA says technology can't exercise scepticism for you; sending client books to a US LLM breaches confidentiality / DPDP."* | **Human decides, always:** every finding and AJE is `PROPOSED`; only the partner confirms, in the UI. **Deterministic core:** all 15 detectors (D0–D14), sampling, AuditGraph and the workpaper run locally with **no LLM**. The LLM investigator is **off by default**; when switched on, tool outputs (including party names and amounts) go to OpenAI, so it's an engagement-level opt-in. |
| **2. Messy Indian data** | *"Tally books are dirty; LRs are handwritten; Bill-To / Ship-To breaks matching."* | **Portal records anchor everything:** e-way bill, IRN and GSTR-1 come from the (mock) government portals, not the client. **GSTIN check digit** validated (the official mod-36 algorithm); PAN-in-GSTIN cross-check. Unreadable evidence → `NEEDS_MANUAL_REVIEW`, never a guess. Ship-To matching is **(roadmap)**: a known false-positive source today. |
| **3. Scale** | *"Cycle detection explodes; SQLite locks; continuous scoring lags."* | **Bounded cycle search:** ≤ 5 transaction edges, ≤ 3 identity hops, 90-day time-ordered window, minimum-span decomposition. **WAL SQLite**, read-only audit connections. Measured at 7,003 invoices: full analytics 11 s, graph 1.3 s, a live edit re-scored in ~1–3 s. |
| **4. Evasion & explainability** | *"Fraudsters split invoices below ₹50k; SHAP is expensive; false positives exhaust staff."* | **Split detector** (≥ 3 same-day invoices to one customer adding up above the e-way threshold). **Benford** (Nigrini MAD) as an indicator. **Exact SHAP** of the real score in milliseconds. **Zero severity ≥ 4 false positives** on the clean 7k year and the planted set. |
| **5. Cost & deployment** | *"LLM tokens eat the audit fee; listed clients ban public clouds."* | **₹0 core:** no LLM needed for the audit. Measured LLM cost when used: **$0.024 per investigation** (Sol), ~$0.12 on Astra, hard caps $3 / run and $40 / day. **One Docker container**, 2 vCPU / 4 GB, runs on-premise; with the LLM, n8n and the Supabase pages off it makes no outbound calls. |
| **6. CA culture** | *"Partners want Excel; ICAI won't accept an autonomous AI auditor."* | **Excel deliverable:** the 4-sheet `.xlsx` in the PS's figure layouts (Sheet 1 = the client's file cell for cell), tick marks ✓ ✗ NP NA ST, DRAFT until signed. **Positioned as a co-pilot**, never an auditor. |

---

# 1. Regulatory, legal and compliance

### 1.1 NFRA on technology and automation bias; auditor liability
- **The objection:** NFRA's first Staff Series paper on technology in audit (*General Principles for Technology
  Adoption in Audit*, July 2026) warns about **automation bias** and says technology **cannot be expected to exercise
  professional scepticism on behalf of the auditor**; tool output counts as audit evidence only after the auditor
  evaluates its relevance and reliability. The signing CA remains liable (Companies Act 2013 ss. 132, 147). If the AI
  proposes a wrong AJE and the CA accepts it, who is responsible?
- **Risk for us:** anything sold as an "autonomous AI auditor" is a non-starter.
- **Our answer (built):**
  1. **`PROPOSED` by construction:** detectors and the investigator can only create PROPOSED findings. Confirm /
     reject / modify and sign-off exist only for the `engagement_partner` role, only in the web UI; the partner token
     is refused on MCP, and `/api/identities` never hands it out.
  2. **Mandatory comment, then sign-off:** sign-off is refused while any finding is PROPOSED, any sample is STALE, or
     integrity checks fail. Every decision needs a comment.
  3. **Verifiable trail:** decisions and sign-off are hash-chained in `audit_trail`; the sign-off records the
     partner's name and ICAI membership number; `scripts/verify_trail.py` re-checks the chain offline.
  4. **Explainability:** every score decomposes exactly (SHAP, `app/explain.py`), and every finding cites record ids
     and standards, which is what "evaluate relevance and reliability" needs.
- **Soundbite:** *"AuditPilot doesn't replace the CA's judgement; it removes the 40 hours of spreadsheet hunting so the
  CA has time to exercise it."*

### 1.2 Client confidentiality and the DPDP Act 2023
- **The objection:** a CA must keep client information confidential (CA Act 1949, First Schedule Part I, and the ICAI
  Code of Ethics); sending registers with customer names, bank accounts and PANs to a foreign LLM API looks like a
  breach, and the DPDP Act adds personal-data duties.
- **Facts:** DPDP s.16 uses a **negative list**: cross-border transfer is allowed unless the government restricts a
  country by notification (none notified as of mid-2026; sectoral rules still apply). So DPDP isn't a blanket ban,
  but consent / purpose limits and the client's own contract terms still bind.
- **Our answer:**
  1. **The audit runs fully locally (built):** D0–D14, the ledger and hash chain, sampling, AuditGraph and the
     workpaper need no internet and no LLM.
  2. **The LLM is an explicit opt-in (built):** `LLM_ENABLED=0` by default; when on, the investigator reads data
     through the same MCP tools as any auditor, so **tool outputs, including party names and amounts, are sent to
     OpenAI**. Turn it on only where the engagement letter allows it.
  3. **PII masking before the LLM (roadmap):** replace PANs, bank accounts and names with tokens
     (`[PAN_01]`, `[BANK_01]`) in tool outputs sent to the model, and map them back in the answer.
  4. **Local model (roadmap):** the investigator uses the OpenAI Agents SDK; an on-premise model behind an
     OpenAI-compatible endpoint is a configuration change, not yet tested.

### 1.3 Bill-To / Ship-To supplies
- **The objection:** many supplies are "bill to A, ship to B" (IGST Act s.10(1)(b)): the invoice party differs from the
  consignee on the e-way bill / LR. A naive matcher flags every one.
- **Honest status:** today D4 compares the dispatch party with the invoice party and raises
  `DISPATCH_PARTY_MISMATCH` at **severity 4**, so a genuine bill-to / ship-to supply **would be flagged** (our demo
  data has none). **(roadmap, worth doing before a real pilot)** read the ship-to GSTIN from the e-way bill and accept a
  movement that reconciles to either the buyer or the ship-to party. On stage: acknowledge it as a known limit.

---

# 2. Real-world data quality

### 2.1 "Garbage in, garbage out" Tally books
- **The objection:** informal ledger names, duplicate parties ("ABC Corp" / "ABC Corp Ltd"), missing phones and PANs.
  Fuzzy matching on that produces false related-party rings.
- **Our answer (built):**
  1. **GSTIN check digit:** every GSTIN is validated with the official mod-36 check-digit algorithm, and the PAN
     inside it is cross-checked against the party's PAN (`INVALID_GSTIN`, `PAN_GSTIN_MISMATCH`). PAN itself has only
     a format, no public check digit.
  2. **No fuzzy name matching at all:** D1 links parties only through **exact identifiers** (PAN incl. PAN-in-GSTIN,
     bank account, phone last 10 digits, email, normalised address key) and declared links (DIR-12 / MBP-1 style).
  3. **Fan-out guard:** an identifier shared by many unrelated parties (e.g. the CA's phone on six customers) is a
     `SERVICE_PROVIDER_IDENTIFIER`, not a related-party ring.
- **(roadmap)** a duplicate-party report for near-identical names, as a data-quality note, never a finding.

### 2.2 Handwritten LRs (bilty)
- **The objection:** most LRs are handwritten carbon copies photographed on a phone; OCR fails.
- **Our answer:**
  1. **The e-way bill is the anchor (built):** above ₹50,000 a movement needs an e-way bill, which is digital and
     carries vehicle, date and transporter; D4/D6 check it against the (mock) portal in `ext.db`, not the client's
     copy.
  2. **No guessing (built):** evidence extraction reads text or PDF text; if it can't extract the fields, the document
     is marked `NEEDS_MANUAL_REVIEW` for a human. It never invents a date or amount.
  3. **(roadmap)** OCR / vision extraction with a confidence score that routes low-confidence scans to a human.

### 2.3 Rounding differences
- **The objection:** multi-rate invoices differ by a few rupees between Tally, the ERP and the portals; strict equality
  floods the auditor.
- **Our answer:** money is **integer paise** everywhere, so our own sums never drift. Register ↔ books differences
  are reported exactly (the PS asks that every difference be a finding) with their ₹ impact, and the round-off column
  is mapped separately. The misstatement summary compares totals with materiality (SA 450); cycles below the clearly
  trivial threshold (5% of OM) aren't flagged. **(roadmap)** a configurable "trivial difference" band for D0 so ₹1
  rounding rows group into one note.

---

# 3. Technical scalability

### 3.1 Cycle explosion
- **The objection:** enumerating all cycles is exponential in dense networks; the demo could run out of memory.
- **Our answer (built):**
  1. **Time-ordered, windowed search:** a cycle must run forward in time within **90 days**.
  2. **Bounded length:** at most **5 transaction edges** and **3 identity hops in a row**, starting and ending at the
     audited company (we only see our own books, so we don't pretend to see third parties' cycles).
  3. **Minimum-span decomposition** (2017 circular-trading paper, `vault/05 §19.4`): the circular value is the minimum
     residual on the cycle, subtracted and repeated, so turnover isn't double counted.
  4. Flag only cycles above the clearly trivial threshold and not explained by matching goods (e.g. job work).

### 3.2 SQLite locks
- **Our answer (built):** WAL mode with `synchronous=NORMAL` and a 10-second busy timeout; audit roles connect
  read-only (`mode=ro` + `PRAGMA query_only`), so auditors can't block or alter ERP writes. Fine for a single firm's
  engagement; **(roadmap)** Postgres for multi-tenant SaaS.

### 3.3 Continuous re-scoring
- **Our answer (built):** two speeds. **Per event:** after each ERP commit, `risk_graph.on_event` reloads only the
  touched customer's documents, re-runs the per-document detectors and updates its scores: measured **0.4 s for a
  27-invoice customer, 1.5 s for 255, ~1–2 s for the largest (818)**. **Full run:** the whole graph, cycles and
  company band on upload or schedule: **1.3 s** at 7k invoices.

---

# 4. Evasion, explainability, false positives

### 4.1 Fraudsters adapt (Goodhart)
- **The objection:** they'll book on 15 March, split invoices to ₹48,000, add random paise.
- **Our answer:**
  1. **Split invoices (built):** `SPLIT_BELOW_THRESHOLD`: ≥ 3 invoices to the same customer on the same day, together
     above the e-way threshold.
  2. **Movement-based, not date-based (built):** D3/D4 test whether goods actually moved (LR, e-way bill, POD) and when
     control passed under the delivery terms, wherever in the year the invoice falls; booking on 15 March doesn't
     help a sale that never shipped.
  3. **Benford (built):** first-digit MAD > 0.015 (Nigrini's nonconformity level) on ≥ 1,000 values: an indicator for
     analytical review, never a finding by itself.
  4. **Concentration vs run-rate (built):** D5 compares the period-end window with the customer's own median month
     (median + MAD), not a fixed calendar rule.

### 4.2 SHAP cost and correlated features
- **The objection:** exact Shapley values cost 2^M evaluations; correlated raw features (base, tax, total) split
  credit arbitrarily.
- **Our answer (built, `app/explain.py`):**
  1. **Players are risk hits, not raw columns:** each detector hit on the invoice plus the customer's entity risk E.
     A typical invoice has 2–7 players, so all 2^n coalitions are enumerated **exactly** in milliseconds; the summary
     over every invoice scored ≥ 30 takes ~0.2 s.
  2. **It explains the real model:** the value function is the actual AuditGraph formula
     R = max(0.7·A + 0.3·E, 60 floor for hard evidence), so the attributions **sum to the score exactly** (shown as a
     check in the UI); E's share is split over its five weighted terms.
  3. **Correlation is handled by the axioms:** two hits on the same root cause share credit symmetrically (Shapley's
     symmetry property) instead of one stealing it.

### 4.3 False-positive fatigue
- **The objection:** 600 alerts on 7,000 invoices and the junior turns the tool off.
- **Our answer (measured):** zero severity ≥ 4 hits on the clean 7,003-invoice year for D0/D3/D4/D6/D7/D9/D13, and
  100% precision on the planted set (31/31 caught). How we keep it quiet: severity levels (indicators like D5 and
  Benford are severity 2 and never findings alone); confidence C separate from risk R; grace periods before
  "missing movement" in continuous mode; the fan-out guard on shared identifiers. Note: a **single** hard-evidence
  hit (e.g. no movement at all, or the register disagreeing with the books) is enough to rank an invoice HIGH; we
  don't require two families, because one portal contradiction is already strong evidence.

---

# 5. Economics, deployment, security

### 5.1 Token cost vs audit fees
- **The objection:** mid-market audit fees are ₹1.5–5 L; $300–500 of LLM tokens per audit kills the margin.
- **Our answer (measured):** the audit itself costs **₹0** in API fees: upload to risk map in **under a minute** of CPU
  at 7k invoices (upload + D0 ~8.5 s, analytics 11 s, graph 1.3 s). The optional investigator measured **$0.024 per
  case on Sol** (31 s, 3 tool calls); ~13 flagged cases on Astra ≈ $1.60. Caps: $3 per run, $40 per day
  (`LLM_RUN_CAP_USD`, `LLM_DAY_CAP_USD`). Details: `docs/FEASIBILITY.md`.

### 5.2 Public cloud vs on-premise
- **Our answer (built):** one Docker image (`Dockerfile`, `scripts/start.sh`): the MCP server (`mcp` SDK
  `MCPServer`), the SQLite files, the REST API and the Streamlit UI on 2 vCPU / 4 GB; the Next.js app builds
  separately. It runs on a laptop or a server inside the firm. Outbound calls happen only if you turn them on: the
  OpenAI investigator, the n8n webhook, and the Supabase-backed pages (orgs, RBAC, sharing, fraud hub) in the Next.js
  app, which use Supabase cloud.

### 5.3 Security of the app itself
- **Our answer (built):** identity comes only from the token (Bearer or stdio `MCP_TOKEN`), never a tool parameter;
  tools are role-filtered at the MCP gateway and the REST API applies the same roles; every call is hash-chained in
  `audit_trail` (OK / DENIED / ERROR); client text is untrusted (returned under `client_data`, instruction-like text
  flagged by D14); Excel string cells are written as text, so no formula injection.

---

# 6. Human factors

### 6.1 Partners want Excel
- **Our answer (built):** the primary deliverable is the **4-sheet workpaper** (`openpyxl`): Sheet 1 is the client's
  register cell for cell plus auditor columns; the TOD sheets follow the PS's Figs. 2–3 header blocks with tick marks
  (✓ ✗ NP NA ST), a conclusion, prepared / reviewed, a DRAFT banner until sign-off and the chain heads in the footer.
  The web app is the investigation view, not a replacement. **(roadmap)** frozen header rows and live formulas
  (totals as `=SUM`) in the TOD sheets.

### 6.2 "Autonomous AI" vs decision support
- **Our answer:** AuditPilot is a **co-pilot**: it tests 100% of the population, ranks risk, selects samples, requests
  and tests evidence, and drafts findings; the CA reviews, decides and signs. That matches NFRA's framing that tools
  amplify, and never replace, the auditor's scepticism.

---

## Slide summary (for the deck)

```text
WHY AUDITPILOT AI WORKS IN THE REAL WORLD

1. REGULATORY
   - Human in the loop by construction: findings are PROPOSED; only the partner confirms and signs, in the UI.
   - The audit runs locally with no LLM; the LLM investigator is an explicit opt-in.

2. REAL DATA
   - Government portal records (e-way bill, IRN, GSTR-1) anchor the tests, not the client's copies.
   - Exact identifiers + GSTIN check digit, no fuzzy name matching; unreadable evidence goes to a human.

3. SCALE
   - Time-ordered, bounded cycle search with minimum-span decomposition.
   - 7,003 invoices: analytics 11 s, graph 1.3 s, a live edit re-scored in ~1-3 s.

4. COST
   - Rs 0 core audit; optional investigator measured at $0.024 per case, hard-capped.
   - Excel-first: the 4-sheet workpaper CAs already use.
```

## Sources
- NFRA Staff Series, *General Principles for Technology Adoption in Audit* (July 2026): coverage at
  [CAalley](https://caalley.com/news-updates/indian-news/ai-cannot-replace-auditor-judgement-flags-automation-bias-in-audits-nfra)
  and a [PDF copy](https://www.caalley.com/ca/nfra/nfra_202607231927160337.pdf). Check the official NFRA text before
  quoting it exactly.
- DPDP Act 2023 s.16 (negative list): [DSCI FAQ](https://www.dsci.in/files/content/documents/2025/cross-border-flow-of-data.pdf),
  [Bar & Bench](https://www.barandbench.com/amp/story/columns/the-dpdp-cross-border-transfer-rules-arent-live-yet-so-why-are-contracts-being-redrafted-as-if-they-are).
- Measured numbers: `docs/FEASIBILITY.md`, `docs/pitch/metrics.json`.
