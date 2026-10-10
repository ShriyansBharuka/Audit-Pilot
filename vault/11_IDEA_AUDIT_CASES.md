# 11 · Idea: an audit-case assistant ("where did the money go, and what did we get for it?")

> Team idea, recorded by Claude 2026-10-10 19:15 so everyone has the same context. **Not a spec yet: no code changes
> from this file** until the team decides. Specs 01–10 still win. §3 is where we already are; §6 is open to the team.

## 1. The idea in short

Don't pitch "a fraud detector". Pitch **an AI audit assistant that rebuilds the company's financial story, checks
every transaction has a business reason, and hands the statutory auditor a short list of explainable cases**. Fraud
detection becomes one capability, not the whole product.

The core question for any transaction: **where did the money go, and what did we get in return?**

Worked example (purchase side): we pay a supplier ₹5,00,000.

| Record | Says |
|---|---|
| Purchase order | 100 units at ₹5,000 |
| Supplier invoice | ₹5,00,000 for 100 units |
| Warehouse receipt (GRN) | **60 units** received (₹3,00,000) |
| Bank | ₹5,00,000 paid in full |
| **Gap** | **₹2,00,000 potentially unsupported** (before tax, later deliveries, adjustments) |

An ordinary system accepts the invoice and pays. Ours asks: *why did we pay for 100 units when the warehouse
received 60?* Before raising it, it checks partial deliveries, later receipts, credit notes, advance terms and
adjustments. This is **three-way matching** (PO, GRN, invoice), a standard control in SAP and SAP Ariba; the new
part is turning it into an automated, evidence-linked investigation.

## 2. What the system would audit (four areas)

| Area | Matches | Flags |
|---|---|---|
| **A. Money out (expenditure)** | vendor, PO, contract price, GRN, invoice, ledger, bank payment | duplicate payments, price inflation, payments to unexpected accounts, missing goods, odd vendor activity |
| **B. Physical movement (inventory)** | opening stock + receipts − consumption − dispatches ± returns − write-offs = closing | movements with no transaction, missing stock records |
| **C. Money in (revenue)** | sales invoice, order, dispatch, delivery, receivable, receipt | unsupported sales, unexplained unpaid invoices, duplicate revenue, March sales reversed in April, unusual customers |
| **D. Year-end** | evidence vs accounting entries | cut-off, unrecorded liabilities, receivables, inventory valuation, journal adjustments, unusual reversals |

This maps to SA 315 (identify risks) and SA 500 (sufficient appropriate evidence).

Audit questions to build around (instead of bare risk scores):

| Question | Data | Finding |
|---|---|---|
| Did we pay twice? | invoices + bank payments | duplicate / excess payment |
| Did we receive what we paid for? | PO + invoice + GRN | quantity / quality gap |
| Did we pay the agreed price? | contract / PO + invoice | unexplained price variance |
| Did money reach the right company? | vendor master + bank | beneficiary mismatch |
| Does closing stock make sense? | inventory movements | stock roll-forward difference |
| Are recorded sales genuine? | sales + dispatch + delivery | unsupported revenue |
| Are counterparties unusually connected? | ownership / relationships | related-party or network risk |
| Right financial year? | event dates + ledger | cut-off difference |

Caveats from the idea:
- A GRN proves someone recorded a delivery, not that the quality or price was right. That needs inspection records,
  quotations, contracts or physical verification.
- Advances before delivery are legitimate, so classify the transaction type before flagging it.
- Company-generated records and hash chains can't prove a transaction happened on their own. Bank confirmations,
  third-party documents, physical verification and auditor-controlled evidence are what corroborate it.

March–April cases (31 March year-end), none automatically fraud:

| Situation | Investigate |
|---|---|
| Goods received 28 Mar, invoice dated 3 Apr | was the liability accrued at 31 Mar? |
| Sale recorded 30 Mar, dispatched 4 Apr | revenue in the right period under the delivery terms? |
| Sale 29 Mar, credit note 5 Apr | return, price adjustment, or premature revenue? |

## 3. Where the agent fits

Deterministic engine first (SQL, reconciliation, accounting rules, statistics) over everything. The LLM never compares
thousands of invoices; it investigates **after** a hit. Logical roles: evidence agent (collect records),
reconciliation agent (work the discrepancy), graph agent (trace relationships), reporting agent (write the
finding). These can be **one orchestrator with tools**. The agent must be able to say **"insufficient evidence"**
rather than invent an explanation or call something fraud.

The product the auditor sees is **a case workspace**, not red dots: e.g. `AUD-041 · High · invoice / warehouse
mismatch · ₹2,00,000 potentially unsupported`. Opening a case shows the original records, the transaction graph, the
exact reconciliation failure, the evidence and a suggested next step. The auditor marks it **explained / request
evidence / escalate / recommend an adjustment**. Output = auditor-reviewed, traceable workpapers.

Product identity: build for **Model B (external statutory auditor copilot)**, able to run continuously like
**Model A (internal audit assistant)**, so every transaction monitored in the year is already organised for the
year-end audit.

## 4. How much of this we already have (as of commit d85e6c6)

| Idea | Status in our build |
|---|---|
| Deterministic engine over 100% first, LLM only after | ✅ D0–D14 over every record; the investigator runs on a flagged item only |
| C. Revenue: invoice ↔ order ↔ dispatch ↔ delivery ↔ receipt | ✅ D3 cut-off, D4 movement + settlement, D6 IRN/EWB/GSTR-1, D9 credit notes, `trace_sale` |
| D. Year-end cut-off, reversals, journals | ✅ D3, D9 (post-period CNs), D7 (JET), D13 backdating; AJE proposals |
| March–April cases (sale 30 Mar / dispatch 4 Apr; CN in April) | ✅ planted and caught (C + I families); **liability side (GRN Mar / bill Apr) ❌** |
| Graph as the paper trail + counterparty network | ✅ AuditGraph (shared bank/PAN/director, round trips, min-span cycles), Network View |
| One orchestrator agent with tools, read-only, can say "insufficient evidence" | ✅ `app/investigator.py` over MCP with the audit token. **Live test today (Sol): 31 s, 3 tool calls, $0.024**; it concluded "an evidence gap, not fraud" and listed missing evidence + questions for the client |
| Continuous (Model A) + year-end (Model B) | ✅ `risk_graph.on_event` after every ERP write; n8n W4 schedule |
| Bank-originated corroboration | ✅ mock bank feed (`ext.bank_txns`), payer-account checks (D4 THIRD_PARTY_PAYER / PAYER_IS_RP) |
| Auditor accepts / challenges the agent | ✅ partly: findings are PROPOSED; partner confirms / rejects / modifies in the UI; auditor notes |
| Hash-chained alteration history | ✅ `erp_log` + `audit_trail` + D11 stale / D12 integrity |
| A. Expenditure: PO, GRN, three-way match, duplicate payment, price variance, beneficiary mismatch | ❌ only `purchase_bills` (vendor, bill, item, qty, value) + vendor payments, used for round-trip cycles. **No purchase orders, no GRNs, no P2P detectors** |
| B. Inventory roll-forward | ❌ dispatches only; no opening stock, inward receipts or stock ledger |
| Case workspace (group hits into cases with actions) | ⚠️ the data is there (risk_hits → findings → evidence), the UI shows findings, not "cases" yet |

## 5. Fit with PS-04: be careful

PS-04 is **"AI-Run Statutory *Revenue* Audit"**: the judges score the revenue workflow (register ↔ system, TOD, cut-off,
credit notes, related parties, stale evidence, the 4-sheet workpaper). The expenditure and inventory areas (A, B) are
**outside the PS**. Suggested framing:
- **Core demo stays revenue** (what we're judged on), told in this idea's language: *"where did the money come from,
  and did we really deliver?"*, with cases instead of scores.
- **Expenditure + inventory = roadmap slide**: "same engine, same graph, same agent: purchase-to-pay is the next
  module". Optionally one small P2P demo if there's spare time after the frontend.
- The **case workspace** is the part worth building now: it improves the revenue demo directly.

## 6. Open for the team (decide before any code)

1. Case workspace in the proper frontend? (Group by root cause: one invoice with NO_MOVEMENT + EWB_REQUIRED_MISSING =
   one case. Actions: explained / request evidence / escalate / propose AJE. Case ids like `AUD-041`.)
2. P2P: roadmap slide only, or a minimal module? Minimal module = `purchase_orders` + `goods_receipts` tables, seed
   plants (short receipt, duplicate payment, price variance, wrong beneficiary, GRN in March / bill in April), one
   detector set (three-way match), and the graph edges. That's a contract change (03 / 04 / 05), so it needs the
   vault edited first.
3. Inventory roll-forward: skip for the hackathon (needs opening stock and production data).
4. The idea's closing question: **which 10–15 procedures does a statutory auditor spend the most time on, and which
   can we automate safely?** First cut for revenue, with what we cover:

| # | Procedure (revenue) | Ours |
|---|---|---|
| 1 | Agree the sales register to the ledger and GST returns | ✅ D0 + tie-out |
| 2 | Vouch a sample of sales to order, invoice, dispatch, delivery, receipt | ✅ Sales TOD + evidence tests (D8) |
| 3 | Cut-off testing around 31 March | ✅ cut-off TOD + D3 |
| 4 | Post-year-end credit notes and returns | ✅ CN TOD + D9 |
| 5 | Related-party identification and disclosure | ✅ D1 / D2 |
| 6 | Analytical review (monthly trends, concentration, margins) | ⚠️ D5 concentration + Benford; no margin analysis |
| 7 | Journal entry testing on revenue accounts | ✅ D7 |
| 8 | GST reconciliation (books vs GSTR-1 / 3B, e-invoice, e-way bills) | ✅ D6 |
| 9 | Receivables confirmations | ❌ (Voroa was the slot; confirmations not built) |
| 10 | Receivables ageing and subsequent receipts | ⚠️ UNPAID_90D; no ageing report |
| 11 | Discounts, schemes, rebates | ✅ D5 SCHEME_WINDOW / DISCOUNT_SPIKE, D9 rebates |
| 12 | Change and integrity of evidence after testing | ✅ D11 / D12 |
| 13 | Misstatement summary vs materiality, AJEs, memo | ✅ SA 450 summary, AJEs, memo, workpaper |
| 14 | Partner review and sign-off | ✅ UI-only, human |
