# 06 · Workpaper, findings memo, audit trail, partner sign-off

> Revised by Claude, 2026-10-10. Layouts follow the PS figures (Fig. 1 register, Fig. 2 Sales TOD, Fig. 3 Cut-off TOD). The reference workbook's tabs were *Sales Reg.*, *Sales TOD*, *Sales Cut-off TOD* and *Credit Note TOD*, and ours match.
> Built by `workpaper.py` (openpyxl) and `memo.py`. Until the partner signs, every output is marked **DRAFT – NOT REVIEWED BY ENGAGEMENT PARTNER** (a red merged row 1 on each sheet + `ws.oddHeader.center.text`).

## 1. Common header block (every sheet, as in Figs. 2–3)

| Row | Content |
|---|---|
| 1 | Client name (bold), e.g. *Konkan Marine Controls Ltd* |
| 2 | *Statutory audit for the year ended 31/03/2026* (italic). The text comes from `engagements.period_end`; a 30/09 period end prints "Limited review for the period ended 30/09/…", as in the figures |
| 4 | **Area:** Sales Register / Sales TOD / Sales Cut off TOD / Credit Note TOD |
| 6–7 | **Objective** + one line |
| 9–15 | **Work Done**, numbered |
| footer | Prepared by `<principal>` `<date>` · Reviewed by `<partner>` `<date>` (blank until sign-off) · erp_log head `seq/hash[:12]` · audit_trail head `seq/hash[:12]` · workbook SHA-256 in the memo |

Tick marks: ✓ agreed · ✗ exception (see finding) · NP not provided · NA not applicable · ST stale (re-test).

## 2. Sheet 1: Sales Register (pasted exactly as provided)

- Header rows 1–4, then row 4 also gives the source: `submission S-…, file <name>, SHA-256 <hash>, uploaded by <principal> at <ts>`.
- The client's **header row and data rows are copied verbatim**, starting at row 6: same column order and headers, values, and number formats. No renaming, retyping, trimming or dropped columns. Fig. 1 alone has 21 columns (Bill no., Date, Job No., Customer, Ledger Account, State Code, GST No., Total Cost, Discount, Packing, Freight, Insurance, IGST, CGST, SGST, TCSCollection, Round, Gross Amt., Tax, BU, E Invoice), and judges may send a different set.
- Copy rules:
  - xlsx input is loaded twice (`data_only=False` and `True`). A formula cell gets its **cached value** + number format, and is listed in a note.
  - Every string cell is written with `cell.data_type = 's'` after assigning the value, so `=…` text never becomes a live formula and `#N/A` text never becomes an error cell.
  - CSV input: every cell stays a string (leading zeros and `0012` survive).
  - CN rows mixed into the register (e.g. `CN/0008/…` with negative amounts) stay where they are.
- **Auditor columns appended on the right** with a distinct fill and a `[Auditor]` prefix: `SoR_Match` (D0 code, `MATCHED` if clean), `SoR_Doc_Id`, `RP_Status` (DECLARED_RP / UNDISCLOSED_RP from <date> / NRP_BEFORE_RELATIONSHIP / NRP_AFTER_CESSATION / NRP; on the SoR customer and control date), `RP_Basis` (the D1/D2 path, short), `Risk_Codes`, `Finding_Refs`, `Notes`.
- The bottom gives the population count and taxable total, plus the D0 tie-out table (register vs ledger revenue vs SoR vs GSTR-1, and the residue).

## 3. Sheet 2: Sales TOD (Fig. 2 layout + the tests a partner expects)

- **Objective:** To check the occurrence, accuracy, classification and cut-off of sales transactions.
- **Work Done:**
  1. Obtained the sales register from management (submission ref, SHA-256) and pasted it unaltered in *Sales Register*.
  2. Reconciled the sales register with revenue as per the books and with GSTR-1 (D0 tie-out).
  3. Ran analytics over 100% of invoices (D0–D14) and selected samples under SA 530. Strata: KEY / HIGH_VALUE / RP / REPRESENTATIVE (PPS); seed `<seed>`, run `<id>`, reproducible with `reproduce_selection`.
  4. Requested the invoice, e-way bill, LR and POD for each sample, and traced each to the system of record: SO, movement, portal IRN/EWB/GSTR-1, ledger, bank.
  5. Checked that each voucher is correctly accounted for: correct amount, correct party, correct sales GL, correct period, correct tax amount (the five checks in Fig. 2).
  6. Checked for client changes to sampled records after testing began, and verified ledger and trail integrity.
- Row 16: population N invoices / ₹ taxable; sample n / ₹; coverage %.
- **Columns:**
  - Fig. 2's first 11: Sr No. | Unit | Quarter | Month | Bill no. | Date | Job No. | Customer | BU | Related/Non Related | Total Taxable value
  - then Stratum | Reason for selection | Invoice | E-way bill | LR | POD | Correct amount | Correct party | Correct sales GL | Correct period | Correct tax | Evidence (sha256[:10] list) | Stale | Exceptions / Finding ref | Auditor notes
  - Unit, Quarter (Indian FY Q1–Q4), Month, Job No. and BU come from the register row when present; otherwise they're derived (unit from series).
- **Conclusion (proposed):** "Except for the exceptions referenced (F-…), the sales transactions tested occurred and are accurately recorded. Proposed by `<agent>`; subject to engagement partner review." The partner's decision replaces "Proposed".

## 4. Sheet 3: Sales Cut-off TOD (Fig. 3 layout)

- **Objective:** To verify that sales near the period end are recorded in the period in which control of the goods transferred (Ind AS 115 paras 31–38; AS 9 for non-Ind AS entities).
- **Work Done:** selected the last 10 invoices up to the period end and the first 15 after it (plus analytics exceptions D3/D13 within ±30 days); obtained LR, e-way bill and POD; determined the control-transfer date from the delivery terms; compared it with the accounting (voucher) date.
- **Columns:**
  - Fig. 3's register columns, when present: Sr No. | Unit | Quarter | Month | Bill no. | Date | Job No. | Customer | Ledger Account | State Code | GST No. | Total Cost | Discount | Packing | Freight | Insurance | IGST | CGST | SGST | Gross Amt.
  - then Delivery terms | LR no. | LR date | E-way bill no. | EWB generated | POD date | Control-transfer date | Voucher date | Period recorded | Correct period | Result (OK / PREMATURE / DELAYED / UNRESOLVED) | Misstatement (taxable ₹) | Finding ref
- **Blocks:** *Before period end (last 10)* · *After period end (first 15)* · *Analytics exceptions outside the selection*.
- Rows flagged by the reviewer are highlighted yellow, as in the figure.

## 5. Sheet 4: Credit Note TOD

- **Objective:** To verify that credit notes are genuine, authorised, linked to the right sales and recorded in the right period. CNs issued after the period end are evaluated as adjusting events (Ind AS 10 / AS 4) and as variable consideration (Ind AS 115 paras 50–59, B20–B27).
- **Population:** every CN dated after the period end up to the run date; CNs above threshold in the last 15 days; CNs to RPs; every D9 hit.
- **Columns:** Sr No. | CN no. | CN date | Customer | RP status | Original invoice(s) | Original invoice date | Days invoice→CN | Taxable | Tax | Total | Reason (client_data) | Scheme (announced on) | Return movement (IN) / GRN | In GSTR-1 CDNR | Within s.34(2) limit | Post-period? | Stuffing risk (HIGH / NEEDS_EVIDENCE / SUPPORTED) | Proposed adjustment (₹) | Finding ref
- Stuffing risk is computed by D9, **never from the stated reason**.

## 6. Proposed adjusting journal entries (templates; balanced COA lines in `findings.proposed_aje_json`)

**Example used throughout:** taxable ₹15,59,322 + IGST ₹2,80,678 = gross ₹18,40,000.

| Finding | AJE (FY under audit) | GST treatment |
|---|---|---|
| **Cut-off: premature** (invoice 30-Mar, control 2-Apr) | Dr SALES 15,59,322 / Cr CONTRACT_LIABILITY 15,59,322 (or Cr DEBTORS[party] if the invoice gave no unconditional right to consideration; Ind AS 115 paras 106–108). **And** Dr INVENTORY / Cr COGS at cost (items.cost × qty) for goods still on hand at the period end | Output IGST **not reversed**: the time of supply is the invoice date (CGST s.12(2)(a), s.31(1)(a)), reported in March GSTR-1/3B. Note for the tax team |
| **Cut-off: delayed** (control before the period end, booked after) | Dr DEBTORS / Cr SALES (taxable) in the FY; mirror the COGS/INVENTORY legs | Tax point may have arisen earlier (interest exposure); tax team |
| **No movement / fictitious sale** | Dr SALES (taxable) + Dr OUTPUT_IGST or CGST/SGST (tax) / Cr DEBTORS[party] (gross) | Tax on a non-supply is not cleaned by a book entry; s.122/s.132 exposure; consider s.143(12) |
| **Revenue JV without a sale** | Reverse the JV: Dr SALES / Cr <JV contra> (e.g. DIRECTOR_LOAN, SUSPENSE) | none |
| **Post-period CN for a pre-period sale** | Dr SALES_RETURNS (taxable) / Cr REFUND_LIABILITY; for returns also Dr INVENTORY (right to recover goods, at cost) / Cr COGS | The CN reduces GST in the later period (s.34), so there is no FY GST entry |
| **Undisclosed or mis-dated RP** | **None** (`proposed_aje_json = NULL`): disclosure under Ind AS 24 para 18 + s.188 approval check | none |
| **Register ≠ SoR only** (books = SoR) | None to the books; management corrects the register. If the books ≠ SoR, handle per case | none |

AJEs are **proposals stored in audit.db**, never posted by the auditor. After the partner confirms, management may post one with `post_journal_entry(aje_ref=…)`, which D7 then recognises as `ACCEPTED_AJE`.

## 7. Findings memo (`memo.md` + printable `memo.html`)

```markdown
# Findings memorandum: statutory audit of revenue
Entity · Period · Framework (Ind AS / AS) · Prepared by <agent principal, date> · Reviewed by <partner, date | PENDING> · Status DRAFT | FINAL
1. Scope and approach: SA 315/330 risk response; SA 500 100% analytics (D0–D14) + tests of details; SA 530 sampling (seed, run ids);
   SA 240 journal-entry tests; SA 550 related parties; SA 560 subsequent events. Materiality (SA 320): OM ₹x, PM ₹y, clearly trivial ₹z.
2. Summary: population (count, ₹ taxable), samples (Sales TOD n, cut-off n, CN n), coverage %, findings by status, net effect on revenue (taxable).
3. Findings table: ID | Category | Standard | Doc refs | Taxable impact | Tax impact | FY | Confidence | Status (PROPOSED/CONFIRMED/REJECTED)
4. One section per finding: what we found (plain language, 2 sentences) · why it matters (standard) · evidence (doc refs, hashes, portal records) ·
   impact · proposed AJE · what the partner should check · management response (blank).
5. Summary of uncorrected misstatements vs materiality (SA 450): factual / judgemental / projected (projected only from the REPRESENTATIVE stratum, never KEY).
6. Matters for the partner's judgement (the AI never recommends an opinion):
   possible modification (SA 705) if uncorrected misstatements are material;
   Companies Act s.143(12): suspected fraud of ₹1 crore or more is reported to the Central Government (ADT-4), below that to the audit committee/board; CARO 2020 cl. 3(xi);
   RP disclosure (Ind AS 24) and s.188 approvals;
   control deficiencies to communicate (SA 265), e.g. one principal created a customer, its invoice and its credit note.
7. Integrity statement: erp_log head seq/hash; audit_trail head seq/hash; anchors verified at <times>; workbook and memo SHA-256.
8. Sign-off block (filled only by the partner UI).
```
Only CONFIRMED findings appear as findings in the FINAL memo. REJECTED ones are listed with the partner's reason, which matters to SA 230.

## 8. Tamper-evident audit trail export

`generate_deliverables` also writes:
- `audit_trail.jsonl`: every `audit.audit_trail` row as canonical JSON, including prev_hash/hash.
- `erp_log_head.json`: the head seq/hash and the anchor list.
- `scripts/verify_trail.py`: **stdlib only**. It recomputes both chains and checks that each anchor sits at its seq, so a partner or judge can verify offline: `python scripts/verify_trail.py audit_trail.jsonl`.

All files are served through one-time `/files/<key>` URLs (audit roles only), never as server paths.

## 9. Partner review and sign-off (Streamlit, `ptn_` token; not available over MCP)

1. **Queue:** every PROPOSED finding, with register vs SoR vs portal values, the documents, the agent's notes and its tool-call timeline (from `audit_trail`).
2. **Decide:** Confirm / Reject / Modify (impact, AJE lines) with a mandatory comment → `decided_by`, `decided_at` and `decision_note` come from the identity record.
3. **Sign off** is enabled only when no finding is PROPOSED, no sample is STALE and `verify_integrity` passes. The partner name and ICAI membership number come from the identity record, never from typed parameters. `signoff_hash = sha256(xlsx sha256 + memo sha256 + trail head + erp_log head)` → engagement `SIGNED_OFF` → deliverables regenerated without the DRAFT mark → an anchor labelled SIGNOFF.
4. **After sign-off**, triggers block UPDATE on that engagement's samples and findings. Later work becomes an addendum (reason, author, date; SA 230).
