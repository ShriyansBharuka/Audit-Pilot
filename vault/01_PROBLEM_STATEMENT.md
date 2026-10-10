# 01 - Problem Statement 04 (Original & Full Context)

> **Verbatim text of the original challenge description, real-world setting, and judging criteria.**

---

## 1. The real-world setting

Statutory audit (an audit required by law; in India, under the Companies Act) means an independent chartered accountant checks a company’s financial statements every year and signs an opinion that they are “true and fair.” Banks, investors and the tax department rely on that signature.

Revenue (sales) is the riskiest number in those statements. Companies that want to look bigger, get bigger bank loans or hit targets inflate it. Common tricks:

- **Fake invoices**: a sale raised on paper to a customer who never received anything.
- **Circular trading**: A sells to B, B to C, C back to A. Money and invoices go round in a loop, turnover looks huge, and nothing real happened.
- **Period-end stuffing**: booking lots of sales in the last days of March so they count in this financial year, then quietly reversing them in April.
- **Hidden related-party sales**: selling to a company owned by the director’s cousin at inflated prices without disclosing the relationship.

The auditor’s problem: a mid-size manufacturer makes 6,000–8,000 sales a year, and the auditor can physically check only a few dozen. Worse, the auditor only sees an Excel export the client chooses to give. They never see the underlying systems.

---

## 2. How it’s done today (the three figures in the PS)

- **Sales Register (Fig. 1)**: the client exports a list of every sale: invoice number, date, customer, amount, GST and so on.
- **Sales TOD (Fig. 2)**: TOD means Test of Details (picking individual transactions and checking each against evidence). The sheet states the objective (e.g. “verify sales are genuine and correctly recorded”), the work done, and the selected samples.
- **Sales Cut-off TOD (Fig. 3)**: cut-off means checking that each sale is recorded in the correct financial year. The auditor takes invoices just before and after 31 March and checks when the goods actually left or arrived.

The auditor then emails the client: *“send invoice, e-way bill and LR for these 30 sales.”*

- **Invoice**: the bill.
- **E-way bill**: a GST permit generated online before moving goods worth over ₹50,000. It records the vehicle, from/to and date, so it’s strong proof that goods actually moved.
- **LR (Lorry Receipt)**: the transporter’s receipt confirming they took the goods.

All of this lives in spreadsheets and email.

---

## 3. The Core: what you must build at minimum

The flow, step by step:

- **Step 1: Client upload.** A client-side interface where the company uploads:
  - its sales ledger (the register), and
  - its related-party list (people and companies connected to the business: directors, their relatives, group companies).
  - The system must be notified when the upload happens, e.g. by an event or webhook (an automatic message your system sends when something happens) that kicks off the audit process.

- **Step 2: Create the workpaper.** A workpaper is the auditor’s working file and the official record of the audit. Your system:
  - copies the client’s data exactly as given, with no cleaning or fixing, because the original is evidence;
  - adds a column marking each customer as Related Party / Non-Related Party by matching against the related-party list.

- **Step 3: Sales TOD sampling (25–35 samples).** You can’t test 8,000 sales, so you pick a sample. The selection must be:
  - risk-based, not purely random: related-party sales get extra weight because bogus sales are likelier there;
  - spread out, covering different customers, high-value sales, and both related and non-related parties.
  - A common approach: take all high-value items above a threshold, then risk-weighted random picks from the rest, while ensuring customer diversity. The randomness should use a fixed seed (a starting number for the random generator, so the same input always gives the same sample). The “Beyond the Core” section requires selections to be reproducible.

- **Step 4: Cut-off TOD.** Pick about the last 10 invoices before 31 March and the first 10–15 after. For each, compare:
  - the invoice date,
  - the dispatch/delivery date from the e-way bill and LR,
  - the accounting entry date.
  - *Example*: an invoice dated 30 March whose LR shows the truck left on 4 April is revenue booked in the wrong year.

- **Step 5: Auto-request evidence.** The system sends the selected samples to the client automatically, and the client uploads the invoice, e-way bill and LR for each one.

- **Step 6: Testing begins.** Match the documents against the register. Do amounts, dates, customer, GSTIN (the customer’s GST registration number) and quantities all agree?

The Core alone is roughly a decent web app: upload, process, sample, request, collect.

---

## 4. Beyond the Core: where the real competition is

### 4a. Build the “system of record,” not just the register
The PS says the register is only a report of the business. Anyone can type a fake row into Excel. So you must build the actual business system that a real sale would pass through, and audit that. A sale’s full life:

| Stage | What exists in a real business | What it proves |
| :--- | :--- | :--- |
| First customer interaction | Enquiry or lead record | The customer is real and approached you |
| Commitment and pricing | Quotation, Sales Order (SO), price list | Agreed terms; abnormal prices stand out |
| Physical movement | Dispatch note, e-way bill, LR, delivery proof (POD) | Goods actually moved, and when |
| Revenue and tax recognition | Invoice, GST entry, e-invoice IRN | Revenue booked and tax reported |
| Cash settlement | Bank receipt and payment matching | The customer actually paid |
| Promotions | Discount schemes, rebates, credit notes | Year-end discounts or reversals that hide stuffing |

*(IRN: Invoice Reference Number, issued by the government portal when a company above ₹5 crore turnover raises an e-invoice.)*

The PS deliberately gives no schema. Deciding which tables and modules must exist to prove a sale happened is part of what you’re judged on.

### 4b. Double-entry ledger that can’t be silently altered
Double-entry means every transaction posts at least two equal and opposite entries. A sale of ₹1,18,000, for example:
- Debit Customer ₹1,18,000
- Credit Sales ₹1,00,000
- Credit GST Payable ₹18,000

Debits always equal credits, so the books balance.

“Cannot be silently altered” means no row is ever updated or deleted. Corrections are new reversing entries, and the whole log is hash-chained: each entry stores a fingerprint of the previous one, so editing any old entry breaks every fingerprint after it and tampering is detectable. This is Ibrahim’s area.

### 4c. Expose everything as an MCP server
MCP (Model Context Protocol) is a standard that lets an AI agent discover and call your system’s functions as “tools,” e.g. `create_sales_order`, `get_ledger`, `select_samples`.

The twist is identity-based permissions. The agent connects holding only an identity:
- **Client employee identity**: can run the business (create orders, dispatch, invoice, receive payment) within that role’s permissions.
- **Auditor identity**: can read everything and run audit tools, but must never change business data. That’s auditor independence, and it has to be enforced by your server, not by trust.

Plus: if the client changes anything after testing has begun, your system must detect it and show which samples it affects. Example: the client edits invoice #4521’s date after it was sampled, and the system flags “Sample 12 evidence is now stale.”

How judging works: judges will plug their own AI agent into your MCP server and try to run the business and the audit live, with no code changes allowed. Your tools must be self-explanatory and robust.

---

## 5. What you’re judged on: catching planted fraud

The judges’ data will contain hidden irregularities. Every difference between the exported register and the system of record is a finding, so never silently “clean” it. Here’s what to catch and how:

| Irregularity | What it looks like | How to detect |
| :--- | :--- | :--- |
| **Undisclosed related parties** | Customer not on the related-party list but actually connected | Match shared identifiers between customers and directors/known RPs: PAN, address, phone, email, bank account, GSTIN |
| **RP starting mid-year** | Becomes related from, say, October | Relationships need effective dates; tag only sales after that date |
| **Wrong period (cut-off)** | Invoice in March, goods moved in April | Recognise revenue on transfer of control (when the customer gets the goods), using delivery/LR dates rather than invoice date |
| **Turnover with no physical movement** | Invoice exists, no dispatch/e-way bill/LR | Trace every invoice to a movement record |
| **Period-end concentration** | Sales and discounts spike in the last days of March | Daily sales/discount analysis; flag statistical outliers |
| **Statutory document inconsistencies** | Invoice amount ≠ e-way bill value ≠ GST return | Three-way match: invoice ↔ e-way bill ↔ GSTR-1 (the monthly GST return listing all sales) |
| **Revenue not from a sale** | Ledger credit to “Sales” through a manual journal entry with no invoice or order behind it | Check every sales-ledger entry has a source document |
| **Forged or reused evidence** | The same LR attached to two invoices, a vehicle number that doesn’t match, an edited PDF | Duplicate detection (file hashes, LR/e-way numbers reused), field cross-checks |
| **Credit notes after year-end** | Big March sales reversed by credit notes in April or May | Credit Note TOD: link each credit note to its original invoice and flag post-period reversals of pre-period sales |
| **Circular trading** | A → B → C → A | Build a counterparty graph and run cycle detection (a brownie point, but a strong one) |

Also required: every sample selection must be reproducible and carry its reasoning, e.g. “selected because related party + amount in top 5%.”

---

## 6. Final deliverables

1. **Workpaper with four sheets**: Sales Register, Sales TOD, Sales Cut-off TOD, and Credit Note TOD. It must be good enough that an engagement partner (the senior CA who signs the audit report) would accept it.
2. **Findings memo**: each issue found, its impact (₹ amount, which year it affects), and proposed adjustments, meaning the correcting journal entries, e.g. “reverse ₹12.4L sales from FY25-26 into FY26-27.”
3. **Tamper-evident audit trail**: a log of everything the system and agents did, hash-chained.

A human auditor must confirm every conclusion: the AI proposes, the human signs off.

---

## 7. The rulebooks to ground it in

- **Standards on Auditing (SAs) from ICAI**:
  - `SA 500` (audit evidence)
  - `SA 530` (audit sampling)
  - `SA 550` (related parties)
  - `SA 240` (fraud)
  - `SA 230` (audit documentation)
  *(Citing these in your reasoning and memo will impress judges).*
- **Accounting**:
  - `Ind AS 115` (revenue on transfer of control) for larger companies, `AS 9` for smaller ones.
- **Indirect tax**:
  - GST rules on invoices, e-invoicing (IRN), e-way bills, GSTR-1/3B returns, and credit notes.

---

## 8. Brownie points (optional extras)

- Continuous auditing (testing as transactions happen, not once a year)
- Multi-entity consolidation (auditing a group of companies together)
- Counterparty graph exposing cycles
- Regional-language document handling (e.g. reading a Marathi or Hindi LR)
- Plain-language justification of every finding
- On-premise mode (runs on the company’s own servers, no cloud)
- Extending to purchases, inventory or payroll

---

## In one sentence

> **Build a mini business system (orders → dispatch → invoice → payment, on a tamper-proof ledger), expose it to AI agents with strict client vs auditor permissions, and build an audit engine that compares what the client reports against what actually happened, catches planted fraud, and produces a workpaper a CA would sign.**
