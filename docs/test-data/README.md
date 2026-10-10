# Test sign-up, sign-in and data input

Run the app (`http://localhost:3100`) with the API on `:8001`. Use any e-mail addresses you like: "Confirm email" is
off in the Supabase project, so no mail is sent and you are signed in straight away. Use a password of at least
8 characters (for example `AuditPilot#2026`). Use a private window for the second person, or sign out between them.

## 1. Auditor: sign up and create the organisation

1. Open `/` and click **Get started**, or open `/signup`.
2. Sign up as the engagement partner, for example `partner.test@example.com`.
3. On **Set up your organisation**, enter:

   | Field | Value |
   |---|---|
   | Company name | Velas Marine Pvt Ltd |
   | PAN | AAFCV4821K |
   | Financial year | 2025-26 |
   | GSTIN | 27AAFCV4821K1Z2 |

   A wrong PAN, or a GSTIN that does not contain the PAN, is refused with a message.
4. You land on **Overview** for the new, empty organisation as its engagement partner.
5. Go to **Admin → Organizations**. Under **Members**, invite `cfo.test@example.com` as **Client admin**. It shows
   as *invited*. Sign out (top right menu).

## 2. Client: sign up through the invite

1. Sign up as `cfo.test@example.com`. The invite is accepted automatically: the menu shows **Evidence, Upload data,
   Enter records** only. The client never sees the audit pages.

## 3. Client: enter records (Enter records)

Enter them in this order, so the invoice numbers match the register file in step 4:

| Tab | What to enter |
|---|---|
| Party | Coastal Dredgers Pvt Ltd · CUSTOMER · GSTIN 27AAACC5123D1Z8 · state 27 |
| Party | Mangal Shipyards Pvt Ltd · CUSTOMER · GSTIN 29AABCM7742Q1ZP · state 29 (inter-state, IGST) |
| Item | Ball valve DN25 · HSN 8481 · 18% · list rate 4500.00 |
| Item | Hydraulic pump HP-40 · HSN 8413 · 18% · list rate 125000.00 |
| Invoice | Coastal Dredgers · G2 · 2026-03-20 · Ball valve DN25 · qty 10 · rate 4500.00 → **G2/0001/25** |
| Invoice | Mangal Shipyards · G2 · 2026-03-30 · Hydraulic pump HP-40 · qty 2 · rate 125000.00 → **G2/0002/25** |
| Credit note | against G2/0001/25 · RATE_DIFF · taxable 4500.00 |
| Journal | any date · narration · two lines, Debit = Credit (the form will not save an unbalanced entry) |

## 4. Client: upload files (Upload data)

| Card | File in this folder |
|---|---|
| Sales register | `velas_sales_register.csv` |
| Related-party list | `velas_related_parties.csv` |

Each upload shows the rows received and the server's SHA-256 fingerprint. The register deliberately differs from the
books: `G2/0001/25` matches, `G2/0002/25` shows a taxable value of 2,60,000 against 2,50,000 in the books, and
`G2/0003/25` does not exist in the books at all.

## 5. Auditor: see what the audit found

Sign back in as the partner. **Overview** shows the detector hits; **Analytics → Findings** lists the proposed findings,
for example *NOT_IN_SOR on register_row 3* (the invoice that is only in the register) plus control gaps in the
hand-entered data (no e-way bill or dispatch, not in GSTR-1, late IRN, journals posted after closing).
**Reports → Memo** drafts the memorandum from them. Only the partner can confirm or reject a finding.

## Demo company (unchanged)

Konkan Marine Controls Ltd (7,587 invoices) stays on access tokens: on the sign-in page click **Sign in with an
access token** and pick a demo persona (or paste a token from `identities.json`). E-mail accounts never get a role
in the demo company.
