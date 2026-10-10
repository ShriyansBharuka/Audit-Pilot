# 01 · Problem Statement 04: verbatim text, figures, plain-language explainer

> Revised by Claude, 2026-10-10. §0 is the **verbatim** PS, copied from `Elevate 1.0 PS list.pdf` (pages 8–10, page footers removed). §1 describes what the PDF's figures show. §2 onward is Antigravity's plain-language explainer, kept with corrections: it is a **paraphrase**, so when it and §0 differ, §0 wins. Methods are specified in 03–07.

## 0. Verbatim problem statement

**PROBLEM STATEMENT 04 · AI-Run Statutory Revenue Audit**

**Background**
A mid-size manufacturer records 6,000 to 8,000 sales a year, yet its statutory auditor can test only a few dozen. That testing still runs on spreadsheets. The client exports a sales register and a related-party list, the audit team copies them into a workpaper, picks samples on judgment, and chases invoices and transport documents over email. The auditor sees only what the client exports, never the systems that recorded what was promised, what physically moved and what was reversed after year end. Fake-invoice networks, circular trading, period-end stuffing and hidden related-party sales keep surfacing in enforcement actions, almost always behind paperwork that looked complete.

**Problem Statement · Core**
The client uploads its sales ledger through a client interface, along with details of its related parties, and the system is notified of the upload. The ledger is carried into a new file that serves as the audit workpaper: the client's data is pasted exactly as provided, and each customer is marked as a related or non-related party by tracing it against the related-party details. Since 6,000 to 8,000 sales cannot all be tested, a separate Sales TOD sheet selects around 25 to 35 samples. The selection may be random but must account for risk, especially related parties, where the chance of bogus sales is high. It should cover as many areas as possible: different customers, high amounts, and related and non-related parties. A Sales Cut-off TOD takes roughly the last 10 invoices before 31 March and the first 10 to 15 after it, verifying the corresponding dispatch or delivery dates and accounting entries, since period-end sales are the most likely to be manipulated. The selected samples are sent to the client automatically, and the client uploads the supporting details for each one, such as the invoice, e-way bill and LR copy, from which testing begins.

**Reference: what the auditor works with today**
Fig. 1: Extract of the client's sales register as received.
Fig. 2: Sales TOD sheet with objective, work done and selected samples.
Fig. 3: Sales Cut-off TOD sheet with invoices around the period end.

**Beyond the Core**
The register is only a report of the business, so solutions must also build the system of record behind it and audit that instead. This covers the full commercial life of a sale: first customer interaction, commitment and pricing, physical movement of goods, revenue and tax recognition, cash settlement, and the promotions that drive demand. Everything must post to a double-entry ledger that cannot be silently altered. No schema or module breakdown is given; deciding what must exist to prove a sale really happened is part of the problem.

The whole system must be exposed as a Model Context Protocol server, so that an AI agent holding only an identity can run the business as a client employee or audit it as an independent auditor, with exactly that identity's permissions. An auditor identity must never change business data, and any client change made after testing begins must be detected and traced to the affected samples.

The engine will be judged on what it catches. Every difference between the exported register and the system of record is a finding, not a cleaning step. Related parties may be undisclosed, may begin partway through the period, or may be linked only through shared identifiers. Period allocation follows transfer of control, not invoice date. Turnover with no physical movement behind it, period-end concentration of sales and discounts, inconsistencies across statutory documents and tax filings, revenue entries that did not originate from a sale, and evidence that is forged or belongs to another transaction must all surface. Credit notes, especially those issued after the period end, are tested too. Every sample selection must be reproducible and carry its reasoning. The planted irregularities will not be disclosed, and judges will exercise the system live through their own agent with no code changes allowed. The output is a workpaper an engagement partner would sign (Sales Register, Sales TOD, Sales Cut-off TOD, Credit Note TOD), a findings memo with impact and proposed adjustments, and a tamper-evident audit trail.

Solutions should be grounded in the Standards on Auditing and the applicable accounting and indirect-tax framework, with a human auditor confirming every conclusion. Continuous auditing, multi-entity consolidation, a counterparty graph exposing cycles, regional-language document handling, plain-language justification of any finding, and an on-premise mode are brownie points, as is extending the approach to purchases, inventory or payroll.

The challenge is therefore to move revenue assurance from testing an exported spreadsheet to interrogating the business itself: continuous, explainable, robust to manipulation, and operable by an AI agent under strict independence.

**CORE QUESTION:** How much of a real statutory revenue audit can an AI agent run end to end, against a business it cannot alter and on evidence it cannot trust, while still producing the workpaper an auditor would sign?

## 1. What the figures show (read from the PDF images; build to this)

The figures are excerpts of a **real** audit workbook. **Never reuse its company, customer or GSTIN data in our demo**: ours is the fictional *Konkan Marine Controls Ltd*.

- **Fig. 1 (register as received), 21 columns:** Bill no. · Date (DD-MM-YYYY) · Job No. · Customer · Ledger Account · State Code · GST No. · Total Cost (= taxable value) · Discount · Packing · Freight · Insurance · IGST · CGST · SGST · TCSCollection · Round · Gross Amt. · Tax (e.g. "IGST 18%(…", "CGST/SGST…") · BU (business unit) · E Invoice (Complete / Incomplete). Quirks our parser and detectors must handle:
  - several bill series/units (`S/…`, `G/…`, `G2/…`, `G11/…`, `G15/…`);
  - **credit notes mixed in as negative rows** (`CN/0008/…`, −2,50,000);
  - blank GSTINs on large rows;
  - State Code `0`;
  - lakh-style number formats;
  - "E Invoice: Incomplete" on rows that do have a GSTIN;
  - two consecutive invoices to the same customer, same date, same amount (a duplicate-billing pattern).
- **Fig. 2 (Sales TOD):**
  - Header block: client name · "Limited review for the period ended 30/09/2024" · **Area: Sales TOD** · **Objective:** "To check the accuracy and occurrence of the sales transaction".
  - **Work Done:** 1 Obtained Sales register from the management · 2 Reconciled sales register with revenue as per financials · 3 Extracted the sales listing and performed sampling for TOD · 4 Tested the samples with the underlying sales invoices · 5 Checked that the voucher is correctly accounted for (correct amount, correct party, correct sales GL, correct period, correct tax amount).
  - Then the population total, and the columns Sr No. · Unit · Quarter · Month · Bill no. · Date · Job No. · Customer · BU · Related/Non Related · Total Taxable value.
  - Tabs: *Sales Reg.*, *Sales TOD*, *Sales Cut-off TOD*, *Credit Note TOD*.
- **Fig. 3 (Sales Cut-off TOD):**
  - Same header style, **Area: Sales Cut off TOD**.
  - Columns: Sr No. · Unit · Quarter · Month · Bill no. · Date · Job No. · Customer · Ledger Account · State Code · GST No. · Total Cost · Discount · Packing · Freight · Insurance …
  - Rows around **both** quarter ends (28–30 Jun, 27–30 Sep), some highlighted yellow. Includes a "SALES ACCOUNT- SERVICE" line (**services have no e-way bill/LR**) and an "FZC" overseas customer (export).
- **Takeaways:**
  - The period end is a **parameter** (the figures use 30/09 for a limited review; the PS text says 31 March).
  - The judges' own register will probably look like Fig. 1.
  - Our sheets reproduce these layouts (`06`).

---

## 2. Explainer (paraphrase of the PS for the team; not verbatim)

### 2.1 The real-world setting
Statutory audit (required by law; in India under the Companies Act) means an independent chartered accountant checks a company's financial statements every year and signs an opinion that they are "true and fair". Banks, investors and the tax department rely on that signature.

Revenue is the riskiest number. Companies that want to look bigger, get bigger loans or hit targets inflate it. Common tricks:
- **Fake invoices**: a sale raised on paper to a customer who never received anything.
- **Circular trading**: A sells to B, B to C, C back to A. Money and invoices go round in a loop, turnover looks huge, and nothing real happened.
- **Period-end stuffing**: booking lots of sales in the last days of March so they count this year, then quietly reversing them afterwards.
- **Hidden related-party sales**: selling to a company owned by a director's relative, at non-arm's-length prices, without disclosing the relationship.

The auditor's problem: 6,000–8,000 sales a year, of which only a few dozen can be checked physically, and only via an Excel export the client chooses to give.

### 2.2 How it's done today (the three figures)
- **Sales Register (Fig. 1)**: the client's list of every sale.
- **Sales TOD (Fig. 2)**: Test of Details, i.e. pick transactions and check each against evidence.
- **Sales Cut-off TOD (Fig. 3)**: check that sales just before and after the period end are in the right year.
- The auditor then emails the client: "send invoice, e-way bill and LR for these 30 sales".
  - **E-way bill**: a GST document generated online before moving goods whose **consignment value (including tax) exceeds ₹50,000** (CGST Rule 138). It records vehicle, from/to and date, which makes it strong proof that goods moved. It is valid 1 day per 200 km and can be cancelled only within 24 h.
  - **LR (Lorry Receipt)**: the transporter's receipt for the goods.
  - **E-invoice / IRN**: the Invoice Reference Number from the government's invoice registration portal, mandatory for B2B invoices of businesses with aggregate turnover above **₹5 crore** (since 1 Aug 2023; unchanged in 2026). An IRN can be cancelled only within 24 h, and businesses at ₹10 crore+ must report within 30 days.

### 2.3 The core (minimum)
1. **Client upload** of the sales register + related-party list through a client interface; the upload notifies the system.
2. **Workpaper creation**: copy the client's data **exactly as given** (no cleaning, because the original is evidence) and add a Related / Non-Related column by tracing customers to the RP list.
3. **Sales TOD sampling (25–35)**: risk-based, not purely random. It weights related parties and spreads across customers, high values, RP and non-RP. Selections must be **reproducible and carry reasons**. We achieve that by **recording** a random seed and the population snapshot. A fixed public seed would let the client predict the sample, which goes against SA 240's unpredictability requirement (`05 §15`).
4. **Cut-off TOD**: about the last 10 invoices before the period end and the first 10–15 after. Compare invoice date, dispatch/delivery dates (LR, e-way bill, POD) and the accounting entry date. *Example: an invoice dated 30 March whose LR shows the truck left on 4 April is revenue in the wrong year.*
5. **Auto-request evidence**: the samples are sent to the client automatically; the client uploads invoice, e-way bill and LR.
6. **Testing**: match the documents with the register and the system of record (amounts, dates, customer, GSTIN, quantities).

### 2.4 Beyond the core
- **The system of record**, not just the register. This covers enquiry → commitment and pricing → physical movement → revenue and tax → cash → promotions and reversals. Deciding which records prove a sale is itself judged (our answer: `02 §2`, `03`).
- **A double-entry ledger that can't be silently altered.** Every transaction posts equal debits and credits. A sale of ₹1,18,000 is Dr Customer 1,18,000 / Cr Sales 1,00,000 / Cr GST 18,000. Nothing is ever updated or deleted: corrections are reversing entries, and the logs are hash-chained with anchors held by the auditor (`03 §6`).
- **MCP server with identity-based permissions.** An agent holding only an identity can run the business (client roles) or audit it (auditor role), with exactly that identity's permissions. The auditor must never change business data, enforced by the server, not by trust. Client changes made after testing begins must be detected and traced to the affected samples (*"Sample 12 is stale: its LR date was changed by warehouse user X after testing started"*).
- **Judging:** judges plug their own agent into our server, live, with no code changes. Tools must be self-explanatory and robust.

### 2.5 What we're judged on: catching undisclosed, planted irregularities
**Every difference between the register and the system of record is a finding, never a cleaning step.** The families named in the PS (methods in `05`):

| Irregularity | What it looks like | Detector |
|---|---|---|
| Register ≠ system of record | fabricated or omitted rows, altered amounts/dates/customers | D0 |
| Undisclosed related parties | customer linked to a director only through PAN-in-GSTIN, bank, phone, email or address | D1 |
| RP starting partway through the period | related only from, e.g., October; or declared with the wrong dates | D2 |
| Wrong period (cut-off) | invoice in March, control transferred in April (by delivery terms) | D3 |
| Turnover with no physical movement | invoice with no dispatch/LR/POD, or a fake e-way bill | D4, D6 |
| Period-end concentration | sales **and discounts** spike in the last days | D5 |
| Statutory document inconsistencies | invoice ≠ e-way bill ≠ IRN ≠ GSTR-1 ≠ GSTR-3B ≠ books | D6 |
| Revenue not from a sale | manual journal crediting revenue, no invoice behind it | D7 |
| Forged or reused evidence | the same LR for two invoices, another transaction's e-way bill, an edited PDF | D8, D14 |
| Credit notes after the period end | pre-period sales reversed by CNs **any time after the period end, up to the audit report** | D9 |
| Circular trading (brownie) | A → B → C → A, or cash round trips | D10 |
| Changes after testing began | an LR/POD/party edit, or a direct database edit | D11, D12 |

### 2.6 Deliverables
1. **Workpaper with four sheets**: Sales Register, Sales TOD, Sales Cut-off TOD, Credit Note TOD (`06`).
2. **Findings memo**: each issue, its impact (₹, which year) and proposed adjusting entries.
3. **Tamper-evident audit trail** of everything the system and agents did.
4. **A human auditor confirms every conclusion**: the AI proposes, the human partner signs.

### 2.7 The rulebooks
- **Standards on Auditing (ICAI):**
  - SA 200 (independence/ethics), SA 230 (documentation), SA 240 (fraud: journal-entry testing, unpredictability), SA 315/330 (risk and responses).
  - SA 320/450 (materiality, evaluating misstatements), SA 500 (evidence), SA 505 (external confirmations), SA 520 (analytics), SA 530 (sampling), SA 550 (related parties), SA 560 (subsequent events), SA 580 (representations), SA 705 (modified opinions: partner's call).
- **Accounting:** Ind AS 115 (revenue on transfer of control; bill-and-hold B79–B82; returns and variable consideration), Ind AS 24 (RP disclosure), Ind AS 10 (events after the period). For non-Ind AS companies: AS 9, AS 18, AS 4.
- **Companies Act 2013:** s.2(76) related party · s.184 MBP-1 disclosure of interest · s.188 RP transactions · s.143(12) fraud reporting (≥ ₹1 crore to the Central Government) · s.144 services an auditor must not provide · Companies (Accounts) Rules r.3(1) edit log. CARO 2020.
- **GST:** CGST Act s.12 (time of supply), s.15(3) (post-supply discounts), s.31 + Rule 46 (invoice), s.34 (credit notes; 30 November limit), s.37/39 (GSTR-1/3B); Rule 48 (e-invoice), Rule 55 (delivery challan), Rule 138 (e-way bill); IGST Act s.10 (place of supply).

### 2.8 Brownie points
Continuous auditing · multi-entity consolidation · a counterparty graph with cycles · regional-language documents (e.g. a Marathi/Hindi LR) · plain-language justification · on-premise mode · extending to purchases, inventory or payroll.

### 2.9 In one sentence
> Build a mini business system (enquiry → order → dispatch → invoice → payment, on a tamper-evident ledger, mirrored by mock government portals), expose it to AI agents with strict, credential-bound client-vs-auditor permissions, and test 100% of it against the register the client exported, so that planted irregularities surface with reasons, ₹ impact and proposed entries, in a workpaper a CA would sign.
