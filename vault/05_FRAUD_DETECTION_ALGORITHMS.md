# 05 - Fraud Detection Engine & ICAI Regulatory Mappings

This document explains the **11 Planted Fraud & Anomaly Scenarios**, their mathematical/algorithmic detection logic, and the corresponding **ICAI Standards on Auditing (SAs)** and **Ind AS** standards to cite.

---

## 1. The 11 Planted Irregularities & Detection Algorithms

### 1. Undisclosed Related Parties (Fuzzy Entity Resolution)
- **The Fraud**: Client sells to a company owned by a director's family member or associate at inflated prices without disclosing them on the official Related Party (RP) list.
- **Regulatory Standard**: **SA 550** (*Related Parties*) & **Ind AS 24** (*Related Party Disclosures*).
- **Detection Algorithm**:
  1. Extract director & relative attributes: PAN, phone, email, registered address, bank account number.
  2. Extract customer attributes from `parties`.
  3. Run multi-vector matching:
     - **Exact Match**: Customer PAN matches director/relative PAN, or customer Bank Account / Phone matches.
     - **Fuzzy Address Match**: Use `rapidfuzz.fuzz.token_sort_ratio(addr1, addr2)`. If score > 85%, flag as potential undisclosed RP.
     - **PAN 4th Character Check**: If 4th char is `'P'` (individual) or `'C'` (company) and initials match director's family.
- **Output Finding**: `"Potential Undisclosed Related Party detected: Customer 'Alpha Logistics' shares address and phone number with Director Rajesh Sharma (Similarity 92%). Standard: SA 550."`

---

### 2. Related Party Starting Mid-Year (Effective Dates)
- **The Fraud**: A customer becomes a related party on, say, 15-October (e.g., director joins board). Client either tags all year's sales or tags none.
- **Regulatory Standard**: **Ind AS 24** & **SA 550**.
- **Detection Algorithm**:
  ```python
  if party.is_declared_rp:
      if invoice.date < party.rp_effective_from:
          # Transaction occurred BEFORE relationship existed
          tag = "Non-Related Party (Pre-affiliation)"
      elif party.rp_effective_to and invoice.date > party.rp_effective_to:
          tag = "Non-Related Party (Post-resignation)"
      else:
          tag = "Related Party"
  ```
- **Output Finding**: Flags any sales miscategorized outside their effective affiliation window.

---

### 3. Wrong Period / Cut-Off Manipulation
- **The Fraud**: Goods were loaded on a truck on 03-April-2025, but the invoice was dated 30-March-2025 to inflate FY 2024-25 revenue.
- **Regulatory Standard**: **Ind AS 115** (*Revenue from Contracts with Customers - Transfer of Control*) & **SA 500**.
- **Detection Algorithm**:
  1. Retrieve all invoices where `invoice_date` is between 20-March and 31-March.
  2. Check corresponding `dispatches.delivery_date` (or `dispatches.lr_date` if FOB shipping point).
  3. If `dispatch_date` > 31-March, control was **not** transferred in FY 2024-25.
- **Output Finding**: `"Cut-off Error: Revenue of ₹18,40,000 booked in FY 24-25 on Invoice INV-892, but Lorry Receipt (LR-4421) confirms dispatch occurred on 04-April-2025. Standard: Ind AS 115."`

---

### 4. Turnover with No Physical Movement (Ghost Invoices)
- **The Fraud**: Client issues invoices on paper to inflate revenue. No goods ever leave the warehouse.
- **Regulatory Standard**: **SA 240** (*The Auditor's Responsibilities Relating to Fraud in an Audit of Financial Statements*).
- **Detection Algorithm**:
  1. For every invoice in `invoices`:
     - Query linked `dispatch_id`.
     - If `dispatch_id IS NULL` OR `lr_number` is missing/empty, AND invoice base amount > ₹50,000 (statutory E-way bill requirement threshold).
- **Output Finding**: `"Ghost Invoice Detected: Invoice INV-912 for ₹12,50,000 has no corresponding Dispatch Note, E-Way Bill, or Lorry Receipt. Standard: SA 240."`

---

### 5. Period-End Concentration & Sales Stuffing
- **The Fraud**: Company crams 30% of its annual sales into the final 5 days of March.
- **Regulatory Standard**: **SA 240** (Paragraph A37 - *Journal entries and year-end adjustments*).
- **Detection Algorithm**:
  1. Calculate daily sales mean ($\mu$) and standard deviation ($\sigma$) across the entire fiscal year.
  2. Compute Z-score for daily sales between 25-March and 31-March:
     $$Z = \frac{X_{\text{daily}} - \mu}{\sigma}$$
  3. If $Z > 3.0$ (statistically significant spike $> 3\sigma$), trigger an audit alert for abnormal period-end concentration.

---

### 6. Statutory Document Inconsistencies (Three-Way Match)
- **The Fraud**: Client creates an invoice for ₹10,00,000 in books, but the E-Way bill was generated for ₹6,00,000 (tax evasion or exaggerated sales).
- **Regulatory Standard**: **CGST Act 2017 (Rule 138)** & **SA 500**.
- **Detection Algorithm**:
  1. Compare:
     - `invoices.total_amount`
     - `dispatches.eway_bill_amount`
     - `gstr1_returns.declared_amount`
  2. If $|\text{Invoice Amount} - \text{E-Way Amount}| > 1.00$, raise a discrepancy flag.

---

### 7. Revenue Not Derived from a Commercial Sale
- **The Fraud**: Accountant credits "Sales Revenue" account via a manual journal entry (JV) without any underlying Sales Order or Invoice.
- **Regulatory Standard**: **SA 240** & **SA 500**.
- **Detection Algorithm**:
  1. In `ledger_entries`, find all rows where `account_code == 'SALES_REVENUE'` and `credit > 0`.
  2. Check `reference_type`. If `reference_type == 'MANUAL_JV'` or `reference_id` cannot be resolved to an active invoice in `invoices`.
- **Output Finding**: `"Unsubstantiated Revenue Entry: Credit of ₹25,00,000 to Sales Revenue via Manual JV #449 with no underlying customer invoice or shipping proof. Standard: SA 240."`

---

### 8. Forged or Reused Evidence
- **The Fraud**: Client uploads the exact same LR or E-Way Bill PDF to justify two different invoices.
- **Regulatory Standard**: **SA 240** (*Falsification of Audit Evidence*).
- **Detection Algorithm**:
  1. Track `evidence_file_hash` (SHA-256) of uploaded LR documents.
  2. Query duplicate document hashes or duplicate `(lr_number, transporter_name)` tuples across distinct invoices.
- **Output Finding**: `"Reused Evidence Detected: Lorry Receipt LR-9902 was submitted for both INV-401 and INV-455. File hash matches exactly. Standard: SA 240."`

---

### 9. Post-Year-End Credit Note Reversals (Channel Stuffing Clean-Up)
- **The Fraud**: Massive sales booked on 30-March are quietly reversed via Credit Notes on 10-April.
- **Regulatory Standard**: **Ind AS 10** (*Events after the Reporting Period*) & **SA 560** (*Subsequent Events*).
- **Detection Algorithm**:
  1. Query `credit_notes` where `cn_date` is in April or May of the subsequent financial year.
  2. Link `original_invoice_id` to determine original invoice date.
  3. If original invoice date is in the last 15 days of March $\rightarrow$ classify as probable channel stuffing reversal.

---

### 10. Circular Trading Loops (Carousel Fraud)
- **The Fraud**: $A \to B \to C \to A$. Goods or paper rotate in a ring to inflate turnover.
- **Regulatory Standard**: **PMLA (Prevention of Money Laundering Act)** & **GST Anti-Evasion Rules**.
- **Detection Algorithm**:
  1. Build a directed graph $G = (V, E)$ using Python's `networkx`:
     - Nodes $V$: Parties (Customers, Suppliers, Company).
     - Edges $E$: Invoiced sales transactions with weights = total value.
  2. Execute `networkx.simple_cycles(G)`.
  3. Filter cycles where cycle length $\ge 3$ and total loop turnover exceeds materiality threshold.
- **Output Finding**: `"Circular Trading Ring Detected: Cycle detected across Party A → Party B → Party C → Party A totaling ₹1.45 Crores in non-genuine turnover. Standard: SA 240 / GST Section 132."`

---

### 11. Post-Sampling Tampering (Stale Evidence Alert)
- **The Fraud**: Client modifies an invoice (e.g. changing date or amount) *after* the auditor has already selected it in the TOD sample.
- **Regulatory Standard**: **SA 230** (*Audit Documentation*).
- **Detection Algorithm**:
  1. Store `snapshot_hash = SHA256(invoice_fields)` at the moment of sampling.
  2. When re-verifying or generating workpapers, compute `current_hash`.
  3. If `snapshot_hash != current_hash`, set `is_stale = 1`.
- **Output Finding**: `"ALERT: Sample #08 (INV-771) evidence is STALE. Record modified by client post-sample selection. Standard: SA 230."`
