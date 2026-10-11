# Demo accounts (judging round)

Three fictional companies, each with its own audit team and client staff, seeded by `scripts/demo_seed.py`. They're
built into the server image, so every restart of the live backend starts from this same state.

- **Web app:** https://audit-pilot-rosy.vercel.app → **Sign in** with e-mail and password
- **Password for every account below:** `AuditPilot#Demo2026`
- The role comes from the organisation, not from the account: each person sees only their own organisation and only
  what their role allows.
- The demo company **Konkan Marine Controls Ltd** (7,587 invoices) is separate. Open it with **Sign in with an
  access token** and pick a persona.

> Anyone with this file can sign in, and a restart resets everything, including a partner sign-off. Before a judge
> session, open the backend's `/api/health` once (the free host sleeps after 15 minutes idle and takes about a minute
> to wake).

## Logins

| Organisation | Name | E-mail | Role | What to show |
|---|---|---|---|---|
| **Arnav Marine Systems Pvt Ltd** (marine equipment) | Nikhil Deshpande | `partner.arnav@example.com` | Engagement partner | Findings → confirm / reject → sign off |
| | Pooja Shetty | `staff.arnav@example.com` | Audit staff | Population, samples, evidence, memo, Connect an agent |
| | Ramesh Iyer | `cfo.arnav@example.com` | Client admin (CFO) | Evidence requests, Upload data, Enter records (all forms) |
| | Farah Khan | `accounts1.arnav@example.com` | Accounts | Invoice / credit note / journal forms, register upload |
| | Sandeep Patil | `accounts2.arnav@example.com` | Accounts | Same as above |
| | Kavya Menon | `sales1.arnav@example.com` | Sales | Party form only |
| | Arjun Salvi | `sales2.arnav@example.com` | Sales | Party form only |
| | Ganesh Pawar | `warehouse.arnav@example.com` | Warehouse | Evidence requests (LR, POD, e-way bills); no entry forms |
| **Medisync Pharma Distributors Pvt Ltd** (pharma distribution) | Anita Bhosale | `partner.medisync@example.com` | Engagement partner | Findings → confirm / reject → sign off |
| | Rahul Verma | `staff.medisync@example.com` | Audit staff | Population, samples, evidence, memo, Connect an agent |
| | Suresh Nair | `cfo.medisync@example.com` | Client admin (CFO) | Evidence requests, Upload data, Enter records |
| | Priyanka Jain | `accounts1.medisync@example.com` | Accounts | Invoice / credit note / journal forms |
| | Imran Shaikh | `accounts2.medisync@example.com` | Accounts | Same as above |
| | Deepa Kulkarni | `sales1.medisync@example.com` | Sales | Party form only |
| | Vivek Rane | `sales2.medisync@example.com` | Sales | Party form only |
| | Manoj Gaikwad | `warehouse.medisync@example.com` | Warehouse | Evidence requests |
| **Torqline Auto Components Ltd** (auto components) | Prakash Mehta | `partner.torqline@example.com` | Engagement partner | Findings → confirm / reject → sign off |
| | Sneha Gokhale | `staff.torqline@example.com` | Audit staff | Population, samples, evidence, memo, Connect an agent |
| | Ajay Kulkarni | `cfo.torqline@example.com` | Client admin (CFO) | Evidence requests, Upload data, Enter records |
| | Ritu Agarwal | `accounts1.torqline@example.com` | Accounts | Invoice / credit note / journal forms |
| | Sameer Joshi | `accounts2.torqline@example.com` | Accounts | Same as above |
| | Neha Kadam | `sales1.torqline@example.com` | Sales | Party form only |
| | Rohan Bhat | `sales2.torqline@example.com` | Sales | Party form only |
| | Santosh More | `warehouse.torqline@example.com` | Warehouse | Evidence requests |

## What is in each organisation

FY 2025-26, entered through the same REST and MCP calls the app and an agent use, on the dates the business happened:

- 8 customers (inter-state ones are billed with IGST)
- 4 items, a director and a transporter
- 35 invoices: two a month, an 8-invoice spike in the last ten days of March, and 3 in early April
- dispatches with LRs, e-way bills over ₹50,000, proofs of delivery and customer receipts
- 3 credit notes, 2 manual journals and monthly GSTR-1 returns
- the client's sales register and related-party list, uploaded by the client
- a sales TOD and a cut-off TOD; the client has answered about half of the ~140 evidence requests

**Planted, and found (10 PROPOSED findings per organisation, nothing else):**

| # | What the client did | Finding code | Arnav | Medisync | Torqline |
|---|---|---|---|---|---|
| 1 | Register lists an invoice that is not in the books | `NOT_IN_SOR` | G2/0029/25 | G2/0033/25 | G2/0033/25 |
| 2 | Register leaves a real sale out | `MISSING_FROM_REGISTER` | G2/0009/25 | G2/0011/25 | G2/0011/25 |
| 3 | Register inflates a taxable value by 10% | `TAXABLE_DIFF` | G2/0014/25 | G2/0017/25 | G2/0017/25 |
| 4 | Register pulls a 2 April sale into the year, dated 31 March | `FY_DIFF` | G2/0001/26 | G2/0001/26 | G2/0001/26 |
| 5 | RP list omits the director's trading company (it banks in the director's own account) | `UNDISCLOSED_RP` | Seabird Marine Traders | Apex Carewell Distributors | Velocity Auto Traders |
| 6 | 30 March sale to that company, never dispatched | `NO_MOVEMENT` | G2/0026/25 | G2/0030/25 | G2/0030/25 |
| 7 | The same sale reversed by a credit note on 12 April | `POST_PERIOD_REVERSAL` | CN/G2/0001/26 | CN/G2/0001/26 | CN/G2/0001/26 |
| 8 | Billed 31 March, goods left on 2 April | `PREMATURE` (cut-off) | G2/0028/25 | G2/0032/25 | G2/0032/25 |
| 9 | Top-side journal Dr Suspense / Cr Sales dated 31 March, keyed on 8 April | `REVENUE_WITHOUT_SALE` | ₹3.50 L | ₹2.40 L | ₹4.75 L |
| 10 | Ledger revenue doesn't tie to the invoices (the same journal) | `TIEOUT_RESIDUE` | ₹3.50 L | ₹2.40 L | ₹4.75 L |

The disclosed related company (Arnav Ocean Logistics, Medisync Wellness Clinics, Torqline Mobility Services) is on the
RP list and shows as **Related** with no finding. That's the contrast to point at.

## 5-minute walkthroughs

### Engagement partner (`partner.<org>@example.com`)
1. **Overview:** the detector hits for this organisation only.
2. **Analytics → Findings:** 10 PROPOSED findings, largest first. Open `UNDISCLOSED_RP`: the reason cites record ids
   (same bank account as the director), never client text.
3. Open `NOT_IN_SOR` and `FY_DIFF`: the register row against the books, with the ₹ impact and, where it applies, the
   proposed adjusting entry.
4. **Confirm** or **Reject** each finding. A comment is mandatory, and only the partner can do this.
5. When nothing is PROPOSED, **Sign off**: it writes the sign-off hash over the deliverables and the chain heads.
   Sign-off exists only in the web app; the partner's account can't be used by an agent over MCP.

### Audit staff (`staff.<org>@example.com`)
1. **Population → Register check:** 35 register rows against the books, with each difference listed.
2. **Evidence:** the requests the sampling sent, which are answered, and the files with their server SHA-256.
3. **Reports → Memo:** the draft statutory memorandum (PROPOSED / DRAFT) with the AJE summary; download the PDF.
4. Try to confirm a finding: staff can't, only the partner.
5. **Connect an agent:** create an agent token and connect Claude / ChatGPT over MCP. The agent works as audit staff
   in this organisation only.

### CFO (`cfo.<org>@example.com`)
1. The menu shows only **Evidence, Upload data, Enter records**. No audit pages, findings or reasons.
2. **Evidence:** the documents the auditor asked for (number, kind, due date) and which are still open. Upload a file
   against one open request.
3. **Upload data:** the register and RP list already sent, with their fingerprints.
4. **Enter records:** all five forms (party, item, invoice, credit note, journal).

### Sales (`sales1.<org>@example.com`)
1. **Enter records** shows the **Party** form only. Add a customer. Try tagging it VENDOR or DIRECTOR: the server
   refuses, because sales may create customers only.
2. The audit pages aren't in the menu, and opening one by URL gets *permission denied* from the server.

### Accounts / warehouse
- **Accounts:** invoice, credit note and journal forms. The invoice number is assigned by the system.
- **Warehouse:** answers LR, POD and e-way bill requests on **Evidence**. It has no entry forms.

## Rebuild or run it elsewhere

```bash
python scripts/demo_seed.py --inprocess        # what the Docker build runs (DATA_DIR=/app/seed-data)
python scripts/demo_seed.py --api http://localhost:8001 --mcp http://localhost:8000/mcp
```

`--inprocess` replays the year on its business dates. `--api` against a running server enters everything today, so
every document also shows control-gap findings (IRN more than 30 days late, journals posted after closing): about 80
per organisation instead of 10. Both modes need `SUPABASE_URL` and `SUPABASE_ANON_KEY`. Re-running leaves an
organisation that already has invoices alone; `DEMO_PASSWORD` overrides the password.
