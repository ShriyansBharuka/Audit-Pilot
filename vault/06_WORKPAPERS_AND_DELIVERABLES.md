# 06 - Workpapers & Findings Memo Deliverables

This document specifies the exact formatting, columns, and content required for the **4-Sheet Audit Workpaper (`.xlsx`)** and the **Findings Memo with Proposed Adjusting Journal Entries (AJEs)**.

---

## 1. Workpaper Sheet 1: Sales Register (Raw Copy)

> **Auditor Rule**: Never alter or clean client data. Retain every original column verbatim, and append one new auditor column.

### Column Specification:
1. `Client_Invoice_No` (Original text)
2. `Client_Invoice_Date` (Original date)
3. `Client_Customer_Name` (Original text)
4. `Client_GSTIN` (Original text)
5. `Client_Base_Amount` (Original float)
6. `Client_Tax_Amount` (Original float)
7. `Client_Total_Amount` (Original float)
8. `Auditor_RP_Status` *(Added by Auditor Engine)*:
   - Values: `Declared Related Party` | `Undisclosed Related Party (Identified by Auditor)` | `Non-Related Party` | `Non-Related Party (Pre-affiliation)`

---

## 2. Workpaper Sheet 2: Sales TOD (Test of Details)

Contains **25 to 35 risk-weighted samples** selected under **SA 530**.

### Column Specification:
1. `Sample_ID` (e.g. `SMPL-01`)
2. `Invoice_No`
3. `Invoice_Date`
4. `Customer_Name`
5. `RP_Classification`
6. `Invoice_Amount_INR`
7. `Selection_Stratum` (`High-Value (> Threshold)` | `RP Risk` | `Random Diverse`)
8. `Plain_Language_Selection_Reason` (e.g. *"Selected: Related Party + Top 5% Value"*)
9. `Evidence_Invoice_Verified` (`YES` / `NO` / `NOT_PROVIDED`)
10. `Evidence_EWay_Bill_Verified` (`YES` / `NO` / `MISMATCH`)
11. `Evidence_LR_Verified` (`YES` / `NO` / `DISPATCH_AFTER_YEAR_END`)
12. `Three_Way_Match_Status` (`MATCHED` / `DISCREPANCY_FOUND`)
13. `Stale_Sample_Alert` (`NORMAL` / `STALE - EDITED POST-SAMPLE`)
14. `Auditor_Exception_Notes`

---

## 3. Workpaper Sheet 3: Sales Cut-Off TOD

Focuses on invoices immediately preceding and following the financial year boundary (31-March).

### Sample Selection Rule:
- Last **10 invoices** recorded before 31-March.
- First **15 invoices** recorded on or after 01-April.

### Column Specification:
1. `Invoice_No`
2. `Invoice_Date`
3. `LR_Number`
4. `Physical_Dispatch_Date` (From Lorry Receipt)
5. `Delivery_Date` (Transfer of control under Ind AS 115)
6. `Accounting_Entry_Date`
7. `Financial_Year_Recorded` (e.g. `FY 2024-25`)
8. `Correct_Financial_Year` (e.g. `FY 2025-26`)
9. `Cut_Off_Error_Flag` (`OK` / `REVENUE_PREMATURELY_RECOGNIZED` / `REVENUE_DELAYED`)
10. `Overstated_Revenue_Amount` (₹ amount to be reversed)

---

## 4. Workpaper Sheet 4: Credit Note TOD

Tracks post-year-end credit notes to detect channel stuffing reversals.

### Sample Selection Rule:
- All credit notes issued in April and May following year-end where original invoice was dated in March.

### Column Specification:
1. `Credit_Note_No`
2. `Credit_Note_Date`
3. `Original_Invoice_No`
4. `Original_Invoice_Date`
5. `Days_Elapsed_Between_Sale_And_Credit`
6. `Credit_Amount_INR`
7. `Stated_Commercial_Reason`
8. `Stuffing_Risk_Indicator` (`HIGH_RISK_REVERSAL` / `GENUINE_COMMERCIAL_RETURN`)

---

## 5. Findings Memo & Proposed Adjusting Journal Entries (AJEs)

The memo is the formal document presented to the Engagement Partner and Board Audit Committee.

### Structure of the Findings Memo:

```markdown
# STATUTORY AUDIT FINDINGS MEMORANDUM
Entity: Bharat Manufacturing Ltd. | FY: 2024-25
Prepared By: Statutory Audit Automation Engine
Reviewed By: Engagement Partner, CA Rajesh Gupta (FCA 124589)

---

## 1. Executive Summary
- Total Population Audited: 7,840 Sales Invoices (₹ 142.80 Crores)
- Samples Tested (Sales TOD): 32 Samples (Coverage: 34.2% of turnover by value)
- Cut-off Invoices Tested: 25 Invoices (± 15 days around 31-March-2025)
- Net Overstatement of Revenue Identified: ₹ 48,20,000.00
- Recommended Status: Qualified Opinion unless Proposed AJEs are posted.

---

## 2. Table of Specific Audit Findings

| Finding ID | Category | Primary Standard | Invoice / Doc Ref | Amount Impact (₹) | Affected FY |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **F-01** | Cut-off Premature Revenue | Ind AS 115 / SA 500 | INV-2025-0891 | ₹ 18,40,000 | FY 2024-25 |
| **F-02** | Ghost Invoice (No Movement) | SA 240 | INV-2025-0912 | ₹ 12,50,000 | FY 2024-25 |
| **F-03** | Undisclosed Related Party | SA 550 / Ind AS 24 | Multiple (Alpha Log) | ₹ 24,00,000 | FY 2024-25 |
| **F-04** | Circular Trading Ring | SA 240 / Sec 132 | Parties A → B → C | ₹ 1,45,00,000 | FY 2024-25 |

---

## 3. Proposed Adjusting Journal Entries (AJEs)

### AJE 01: Reversal of Premature Cut-Off Revenue (INV-2025-0891)
Standard: Ind AS 115 (Revenue on Transfer of Control)
Goods left factory on 04-April-2025 per LR-4421, but revenue booked on 30-March-2025.

    Debit:   Sales Revenue Account           ₹ 15,59,322.00
    Debit:   GST Output IGST Payable         ₹  2,80,678.00
    Credit:  Sundry Debtors (Customer)                       ₹ 18,40,000.00
    (Being reversal of revenue prematurely recorded in FY 24-25 prior to transfer of physical control)

### AJE 02: Cancellation of Fictitious Revenue (Ghost Invoice INV-2025-0912)
Standard: SA 240 (Fraudulent Financial Reporting)
No dispatch note, E-Way Bill, or Lorry Receipt found for transaction exceeding ₹50,000 threshold.

    Debit:   Sales Revenue Account           ₹ 10,59,322.00
    Debit:   GST Output CGST Payable         ₹    95,339.00
    Debit:   GST Output SGST Payable         ₹    95,339.00
    Credit:  Sundry Debtors                                  ₹ 12,50,000.00
    (Being derecognition of fictitious sales transaction lacking shipping and movement evidence)

---

## 4. Engagement Partner Digital Sign-Off
- **Engagement Partner**: CA Rajesh Gupta, FCA
- **ICAI Membership Number**: 124589
- **Audit Conclusion**: "I have reviewed the working papers, automated sample testing results, and fraud indicators. Proposed AJEs #01 through #04 must be accepted by management prior to signing the Independent Auditor's Report."
- **Workpaper Integrity Hash**: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- **Sign-Off Timestamp**: 2026-10-10 17:30:00 IST
```
