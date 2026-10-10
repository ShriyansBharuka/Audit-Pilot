# 13 · Money trail + three-layer audit: build spec and queue for Darshan's Claude (C2)

> Written by Claude (Shriyans's PC), 2026-10-10 21:00. **C2 builds the backend in this file, item by item (MT-1 …
> MT-8).** Claude on Shriyans's PC builds the frontend screens against the REST contract in §6 as each item lands.
> Background and the team's reasoning: `11_IDEA_AUDIT_CASES.md` (case assistant) and this file §1 (the feature).
> Specs 01–10 still win; where this file adds a table, tool or detector, **edit 03 / 04 / 05 in the same commit**
> (AGENTS.md rule).

## 0. Rules for C2 (read first)

- **Your files:** everything under `app/`, `schema/`, `tests/`, `scripts/`, `vault/03-05`, plus the endpoints you add to
  `app/api_server.py`. **Don't edit** `web/` (frontend, Claude's), `app/explain.py` (exact SHAP, Claude's) or `ui/`.
- One item = one commit `MT-n: <what>`, after `git pull --rebase`. Log one line in `vault/PROGRESS.md`. Push when
  Shriyans says so (he has said "keep pushing": push after each item).
- Before "done": `python -m pytest -q` (all green; there are 114 tests now) and `python -m app.selftest`.
- The usual non-negotiables hold: integer paise; ISO dates; every ERP write through `erp.write_doc`; append-only
  tables; identity only from the token; the client never sees audit reasons, cases or scores; no LLM decides an
  amount, a match or a path (deterministic tools compute them, the LLM explains them).
- REST endpoints use the existing guards in `app/api_server.py`: `dependencies=[AUDIT]` for audit data,
  `Depends(require(*CLIENT_ROLES))` for client actions. Never return tokens.

## 1. The feature (what the team wants)

An **end-to-end audit intelligence system** with three connected layers:

1. **Continuous audit** (Apr–Feb, all year): monitor every transaction, compare expected vs actual, flag
   discrepancies as they happen. *We have this for sales:* `erp.write_doc` → `risk_graph.on_event`.
2. **Year-end assessment** (March / April onwards / the annual audit): freeze the year, cut-off testing, risk
   aggregation, compare how the books evolved with the final ledger; link March events to April reversals (a March
   sale returned in April → was revenue recognised correctly?). Keep the risk history so the auditor sees how a
   balance developed, not only where it ended. (SA 315 risk identification, SA 330 response.)
3. **Multi-agent investigation** of flagged cases: a risk agent (prioritise), an evidence agent (fetch invoices,
   ledger, bank, delivery, edit history), a money-flow / graph agent (trace transfers, verified amounts, unexplained
   flows) and a reporting agent (findings + draft workpaper). **One orchestrator with tools is fine.**

**Core principle:** distinguish **where money is recorded as going** (the company's books: a claim) from **where
independently verified evidence proves it went** (bank lines, portal records, third-party documents).

Every case surfaces **three separate numbers**, never one blended "loss":

| Number | Meaning |
|---|---|
| **Verified transaction value** | amount supported by independently verifiable records (bank / portal / third party) |
| **Potentially affected amount** | amount that needs investigation, not necessarily a loss |
| **Risk score** | priority (materiality, patterns, control failures, evidence quality), explainable by its factors (SHAP), and **separate from confidence** in the evidence |

Worked example (the demo case): we paid ABC Industrial Supplies **₹5,00,000** for 100 units; the warehouse received
**60** (₹3,00,000 at the PO price) → **₹2,00,000 potentially unsupported** (before tax, freight, valid adjustments).
The system checks later deliveries, returns, advances and credit notes first; if nothing explains it, it opens a
case: bank payment verified (bank line), recorded beneficiary = ABC, downstream transfers **not established** (we
don't have ABC's bank), suggested action = request proof of the remaining delivery.

Money-trail rules (the graph must not over-claim):
- A pays B ₹10 L and B pays C ₹8 L: show both transfers if both bank lines exist, but **never conclude** that ₹8 L
  of A's money reached C. That needs tracing evidence and an attribution rule.
- Never sum every edge of a circular network as "the loss": the same money is counted repeatedly. Use the
  minimum-span circular value we already compute (`risk_graph.decompose`).
- Every edge carries its **provenance**: `VERIFIED` (bank / portal / third-party record), `CLAIMED` (the company's
  own books or documents), `INFERRED` (identity link or graph inference). Company records and our hash chain prove
  *what the company recorded and that it wasn't altered*, not that the transaction happened.

Two reports, not one:
- **Report A, continuous audit intelligence** (operational): unreconciled transactions, missing evidence, control
  failures, risk trend, open alerts.
- **Report B, year-end investigation report** (for the auditor): transaction risk register, counterparty exposure,
  funds-flow summaries, investigated cases, proposed AJEs, unresolved questions. An AI-drafted executive summary is
  allowed (marked DRAFT); **it never issues an audit opinion** (SA 700: the partner forms it).

Pitch line: *an agentic audit platform that continuously monitors the books, reconciles the year, investigates
discrepancies and reconstructs explainable money trails: which transactions are risky, how much money is involved,
where payments went, and what evidence supports each conclusion.*

## 2. Scope for the hackathon (keep it this narrow)

- **Keep the revenue audit as the core** (it's what PS-04 scores). Add a **minimal purchase-to-pay slice** so the
  money trail has both directions: PO → goods receipt → bill → bank payment.
- Year-end demo moments: March–April reversals (have), a **missing goods receipt**, a **duplicate payment**, an
  **unrecorded liability** (goods received 28 Mar, bill dated 3 Apr), unusual revenue recognition (have).
- Build the **evidence + money-flow agents first** (real agentic behaviour), the reporting agent last.
- One strong **case investigation screen** (frontend, Claude): "Trace this ₹5 lakh payment".
- Not in scope: inventory roll-forward (needs opening stock + production), downstream tracing beyond our own bank.

## 3. What already exists (reuse, don't rebuild)

| Need | Already in the repo |
|---|---|
| Vendor bills | `erp.record_purchase` → `purchase_bills` (vendor, bill no/date, item, qty, taxable, tax) + PURCHASE journal |
| Vendor payments, bank-originated | `erp.record_payment` → `ext.bank_txns` line (payee account **as the bank shows it**) + `settlements` (doc_type PURCHASE or ADVANCE) + PAYMENT journal |
| Receipts from customers | `erp.record_receipt` → bank line + settlements; D4 THIRD_PARTY_PAYER / PAYER_IS_RP |
| Graph + cycles | `risk_graph.build_edges` (SALE / PURCHASE / PAYMENT_IN / PAYMENT_OUT + identity links), `decompose()` |
| Scores + explanation | `risk_graph.score` (A, E, R, C), `app/explain.py` (exact SHAP; use `explain.explain_invoice`) |
| Continuous hook | `erp.write_doc` → `risk_graph.on_event` after every commit |
| Risk history | append-only `risk_snapshots` (`RG-*` full runs, `EV-*` per event) |
| Findings / AJEs / memo / workpaper | `findings.py`, `memo.py`, `workpaper.py`; partner decides in the UI |
| Investigator | `app/investigator.py` (Agents SDK over MCP stdio, audit token, CostMeter caps) |
| Plants + scoring | `app/plants.py`, `data/answer_key.json`, `app/demo_audit.py`, `app/evaluate.py` |

## 4. Task queue (C2: top to bottom)

| ID | Build | Files | Done when |
|---|---|---|---|
| **MT-1** | **P2P records.** Tables `purchase_orders` (id, vendor_id, po_date, item_id, qty, rate_paise, payment_terms `ADVANCE`/`ON_DELIVERY`/`CREDIT_30`/`CREDIT_60`, status) and `goods_receipts` (id, po_id, received_on, item_id, qty, received_by, grn_no) in erp.db, both append-only (no UPDATE; a return to the vendor is a new `goods_receipts` row with `kind = 'RETURN'` and qty > 0). `purchase_bills` gets `po_id` (nullable). Services `erp.create_purchase_order`, `erp.record_goods_receipt` (warehouse role), `record_purchase(po_id=…)`; all through `write_doc`. Client MCP tools for both (04). Seed: every routine purchase in the clean year becomes PO → GRN → bill → payment (credit terms), clean = zero P2P hits | `schema/erp.sql`, `app/erp.py`, `app/tools_client.py`, `app/seed.py`, `vault/03`, `vault/04`, `tests/test_p2p.py` | clean 7k year: every bill has a PO + GRN; tests green |
| **MT-2** | **D15 purchase-to-pay detectors** (100% of bills and payments): `SHORT_RECEIPT` (billed or paid qty > received qty; impact = (billed − received) × PO rate), `PRICE_VARIANCE` (bill rate > PO rate + 2%), `PAYMENT_WITHOUT_RECEIPT` (paid, no GRN, terms not ADVANCE), `DUPLICATE_PAYMENT` (same bill paid twice, or same vendor + amount within 7 days with no second bill), `BENEFICIARY_MISMATCH` (bank payee account ≠ vendor master account; reuse D1's account normalisation), `UNRECORDED_LIABILITY` (GRN on/before period end, bill dated after, no accrual journal), `ADVANCE_UNSETTLED` (advance > 90 days, no GRN). Before flagging, check later GRNs, credit notes and advance terms (the "explain first" rule). Family **P** in `risk_graph.FAMILY`. **Plants** (plants.py + answer key): the ABC example (₹5 L paid, 60/100 received), a duplicate ₹75,000 payment, a price variance, a wrong-beneficiary payment, a 28 Mar GRN / 3 Apr bill, one P-plant that *is* explained by a later GRN (must stay clean) | `app/analytics.py` (new `d15`), `app/plants.py`, `app/risk_graph.py` (FAMILY only), `vault/05`, `tests/test_detectors.py` | `python -m app.demo_audit` on 7k: P family 100% caught, 0 sev ≥ 4 false positives, explained plant clean |
| **MT-3** | **Money trail** `app/money_trail.py`: `trace(object_id, hops=2)` for an invoice, bill, payment, bank txn or party → `{nodes, edges, numbers}`; each edge `{from, to, kind, amount_paise, date, doc_ids, source: BANK/PORTAL/BOOKS/IDENTITY, status: VERIFIED/CLAIMED/INFERRED, evidence_refs}`; `numbers = {verified_paise, affected_paise, recorded_paise}` with the rules in §1 (no downstream attribution, min-span for cycles). MCP tool `trace_money` (audit roles, paginated) + REST `GET /api/money-trail/{object_id}` | `app/money_trail.py`, `app/tools_audit.py`, `app/api_server.py`, `vault/04`, `tests/test_money_trail.py` | the ABC case returns verified ₹5 L (bank), received ₹3 L, affected ₹2 L; an A→B→C chain shows both edges and no attribution |
| **MT-4** | **Cases** `app/cases.py`: group every severity ≥ 4 hit by root object (invoice / bill / payment / party) into a case `AUD-0001…` with title (code-based, no client text), counterparty, the three numbers (from MT-3), risk score + confidence, hit list, evidence list, status `OPEN` / `EXPLAINED` / `EVIDENCE_REQUESTED` / `ESCALATED` / `ADJUSTMENT_PROPOSED`. Tables `cases` + append-only `case_events` in audit.db. Actions by audit_staff: explain (note required), request evidence (creates a pbc request, opaque to the client), escalate, propose adjustment (→ a PROPOSED finding with balanced AJE lines; the partner decides it as today). Idempotent rebuild after every analytics run. MCP tools `list_cases`, `get_case`, `act_on_case` + REST §6 | `app/cases.py`, `schema/audit.sql`, `app/tools_audit.py`, `app/api_server.py`, `vault/03`, `vault/04`, `tests/test_cases.py` | 7k demo: one case per planted root cause (no duplicates for NO_MOVEMENT + EWB_REQUIRED_MISSING on one invoice); actions append events; client token gets 403 |
| **MT-5** | **Multi-agent investigation**: extend `app/investigator.py` into an orchestrator with four specialist agents as tools (risk, evidence, money-flow, reporting), all MCP clients with the audit token; tools they may call include `get_case`, `trace_money`, `trace_sale`, `run_readonly_sql`, `list_audit_items`. Output schema: facts (each citing record ids), verified vs claimed amounts (copied from tool output, never computed by the model), discrepancies, missing evidence, open questions, conclusion `SUPPORTED` / `UNRESOLVED` / `INSUFFICIENT_EVIDENCE`, suggested action. Saved as a case event `AI_INVESTIGATION` (PROPOSED, never a decision). CostMeter caps unchanged; Sol for dev, Astra only for demo. REST `POST /api/cases/{id}/investigate` | `app/investigator.py`, `app/api_server.py`, `tests/test_investigator.py` | one live Sol run on the ABC case < $0.10; the answer cites ids and keeps verified ≠ claimed |
| **MT-6** | **Year-end layer** `app/yearend.py`: `timeline(party_id=None)` = monthly series (sales, receipts, credit notes, open exceptions, company band per month from `risk_snapshots` / a replay); `march_april_links()` = every March document with an April reversal / CN / return / late dispatch and the D3/D9 hits on it; `freeze(engagement_id)` = year-end anchor + snapshot run id. REST `GET /api/yearend/timeline`, `GET /api/yearend/march-april` | `app/yearend.py`, `app/api_server.py`, `tests/test_yearend.py` | the planted March→April cases (PI1, PI2, PC1-PC3) all appear in `march_april_links` |
| **MT-7** | **Reports A and B** `app/reports.py`: `continuous(engagement_id)` and `year_end(engagement_id)` → markdown + html (same style as `memo.py`), DRAFT until sign-off, no audit opinion; numbers only from deterministic modules; optional AI executive summary (reporting agent) clearly labelled. REST `GET /api/reports/continuous`, `GET /api/reports/year-end` (`?format=md|html|json`) | `app/reports.py`, `app/api_server.py`, `tests/test_reports.py` | both reports render on the 7k demo; every amount traces to a case / finding id |
| **MT-8** | **Docs + demo**: `HOW_IT_WORKS.md` (three layers + money trail), `docs/pitch/demo_video_script.md` (add the "trace this ₹5 lakh payment" beat), `vault/09` statuses, `docs/FEASIBILITY.md` (latency of trace / cases / investigation) | docs only | team can demo the full story from the docs |

## 5. Detector / family additions (for 05 and `risk_graph.FAMILY`)

`D15` purchase-to-pay → family **P**. Severity: `SHORT_RECEIPT` 5, `PAYMENT_WITHOUT_RECEIPT` 5, `DUPLICATE_PAYMENT` 5,
`BENEFICIARY_MISMATCH` 5, `UNRECORDED_LIABILITY` 4, `PRICE_VARIANCE` 4, `ADVANCE_UNSETTLED` 3. Bank-sourced and
GRN-sourced codes join `risk_graph.HARD` (hard evidence floor). SHAP (`app/explain.py`) handles any new code
automatically; ask Claude only if the score formula itself changes.

## 6. REST contract the frontend will call (all `dependencies=[AUDIT]` unless noted)

Amounts are integer paise plus a `*_formatted` string from `money.fmt_inr`. Lists take `limit` (≤ 100) and `offset`.

```text
GET  /api/cases?status=&band=&limit=&offset=
     -> {total, items: [{case_id, title, root_type, root_id, counterparty_id, counterparty_name, band, risk_score,
         confidence, verified_paise, affected_paise, status, opened_at, codes: [..]}]}
GET  /api/cases/{case_id}
     -> {case: {...same fields...}, hits: [{detector, code, severity, reason, impact_paise}],
         documents: [{doc_type, doc_id, doc_no, date, amount_paise, source, status}],
         money_trail: {nodes: [{id, type, label}], edges: [{from, to, kind, amount_paise, date, doc_ids, source, status,
                       evidence_refs}]},
         numbers: {verified_paise, affected_paise, recorded_paise, risk_score, confidence},
         explanation: "<deterministic text, ids only>", suggested_action: "<text>",
         history: [{at, by, action, note}], investigation: {<latest AI_INVESTIGATION payload>} | null}
POST /api/cases/{case_id}/action   body {action: EXPLAINED|REQUEST_EVIDENCE|ESCALATE|PROPOSE_ADJUSTMENT, note,
                                         doc_kind?, aje_lines?}   (audit_staff) -> {case, event}
POST /api/cases/{case_id}/investigate  (audit_staff; 409 when the LLM is off or the day cap is hit)
     -> {investigation, usd, tool_calls, model}
GET  /api/money-trail/{object_id}?hops=2 -> {nodes, edges, numbers}
GET  /api/yearend/timeline?party_id= -> {months: [{ym, sales_paise, receipts_paise, cn_paise, open_exceptions, band}]}
GET  /api/yearend/march-april -> {items: [{march_doc, april_events: [...], hits: [...], affected_paise}]}
POST /api/yearend/freeze  (audit_staff) -> {anchor, analytics_run, snapshot_run, company, cases}   (added MT-6)
GET  /api/reports/continuous?format=json|md|html
GET  /api/reports/year-end?format=json|md|html
```

If a field turns out impossible, change it here in the same commit and say so in `PROGRESS.md` so the frontend
follows.

## 7. Frontend that Claude builds on top (for context; C2 doesn't touch `web/`)

`/cases` (risk-ranked case list with the three numbers), `/cases/[id]` (records, money-trail graph with
VERIFIED / CLAIMED / INFERRED edge styles, SHAP for the invoice, actions, "Investigate with AI"), `/reports`
(A and B), year-end timeline on the overview.
