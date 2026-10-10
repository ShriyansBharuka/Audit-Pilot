# 04 - MCP Tool Catalog & RBAC Specification

This document details the **Model Context Protocol (MCP)** tools exposed by the application, their input/output schemas, and how **Identity-Based RBAC** is enforced to uphold **Auditor Independence (SA 200)**.

---

## 1. Role-Based Identity & Security Model

The MCP Server exposes a unified tool surface. Every tool invocation evaluates the caller's identity context:

```python
# Context passed via environment, session headers, or tool parameter
caller_identity: Literal["client", "auditor"]
```

### The Inviolable Security Rules:
1. **Auditor Independence (SA 200)**: Any tool that modifies the ERP (orders, dispatches, invoices, credit notes) **must reject calls with `caller_identity == "auditor"`** with a fatal error:
   ```json
   {
     "status": "error",
     "code": "SA_200_INDEPENDENCE_VIOLATION",
     "message": "Auditors are prohibited from executing management functions or modifying records in the system of record."
   }
   ```
2. **Client Audit Restriction**: Any tool that performs audit sign-offs or generates formal audit opinions is restricted to `"auditor"`.

---

## 2. Client Identity Tools (Mini ERP Operations)

These tools allow the client agent (or judges simulating a company) to operate the business.

### 1. `create_sales_order`
- **Allowed Roles**: `client`
- **Description**: Creates a new commercial sales order.
- **Parameters**:
  - `customer_id` (str): ID of the customer from master.
  - `order_date` (str: YYYY-MM-DD): Date of order.
  - `items` (list): Array of `{ item_name, quantity, unit_price, tax_rate }`.
- **Output**: `{ "so_number": "SO-2025-0104", "total_amount": 118000.00, "status": "CONFIRMED" }`

### 2. `record_dispatch`
- **Allowed Roles**: `client`
- **Description**: Generates physical movement records (Lorry Receipt & E-way Bill).
- **Parameters**:
  - `so_id` (str): Linked Sales Order ID.
  - `dispatch_date` (str: YYYY-MM-DD): Date goods leave premises.
  - `transporter_name` (str): Logistics provider.
  - `vehicle_number` (str): Vehicle registration.
  - `lr_number` (str): Transporter Lorry Receipt number.
  - `eway_bill_number` (str): 12-digit GST e-way bill number.
  - `delivery_date` (str: YYYY-MM-DD, optional): Actual proof of delivery date.
- **Output**: `{ "dispatch_id": "DISP-2025-0104", "status": "RECORDED" }`

### 3. `issue_invoice`
- **Allowed Roles**: `client`
- **Description**: Issues a tax invoice and automatically triggers balanced double-entry postings in the hash-chained ledger.
- **Parameters**:
  - `so_id` (str): Sales order ID.
  - `dispatch_id` (str, optional): Dispatch ID (omitted in planted ghost invoice frauds).
  - `invoice_date` (str: YYYY-MM-DD): Date on invoice.
  - `accounting_entry_date` (str: YYYY-MM-DD): Date posted to financial ledger.
- **Output**: Returns invoice details, generated IRN, and ledger entry numbers posted.
- **Trigger**: If this invoice modifies a previously sampled transaction, a `STALE_SAMPLE_FLAG` is automatically set in `audit_samples`.

### 4. `issue_credit_note`
- **Allowed Roles**: `client`
- **Description**: Issues a post-sales reversal or rebate against an earlier invoice.
- **Parameters**:
  - `original_invoice_id` (str): Invoice being credited.
  - `cn_date` (str: YYYY-MM-DD): Date of credit note.
  - `amount` (float): Reversal base amount.
  - `reason` (str): Commercial reason for credit note.
- **Output**: Credit note ID and reversing ledger postings.

### 5. `upload_audit_evidence`
- **Allowed Roles**: `client`
- **Description**: Client fulfills auditor's evidence request by submitting document hashes and files for a sample.
- **Parameters**:
  - `sample_id` (str): ID of requested audit sample.
  - `document_type` (str): `'INVOICE'`, `'EWAY_BILL'`, or `'LR'`.
  - `file_hash` (str): SHA-256 of the document file.
  - `file_metadata` (object): Number, date, amounts declared on document.

---

## 3. Auditor Identity Tools (Audit Engine & Workpapers)

These tools are invoked by the auditor AI agent to perform tests of details, analyze fraud, and generate reports.

### 1. `get_sales_register`
- **Allowed Roles**: `auditor`, `client`
- **Description**: Extracts the full sales register verbatim. Returns client-reported data untouched.
- **Parameters**:
  - `financial_year` (str): e.g. `'2024-25'`.
- **Output**: Complete array of all recorded invoices.

### 2. `verify_ledger_integrity`
- **Allowed Roles**: `auditor`
- **Description**: Traverses the general ledger from genesis block to current block, recomputing SHA-256 hashes and confirming zero broken links and debits == credits.
- **Parameters**: None.
- **Output**:
  ```json
  {
    "total_entries": 1420,
    "chain_valid": true,
    "balanced_books": true,
    "broken_at_entry": null,
    "status": "TAMPER_FREE"
  }
  ```

### 3. `run_tod_sampling`
- **Allowed Roles**: `auditor`
- **Description**: Executes reproducible SA 530 risk-based sampling. Picks 25–35 items with high-value coverage, related-party weighting, and customer diversity.
- **Parameters**:
  - `seed` (int, default=42): Deterministic random seed.
  - `sample_size` (int, default=30): Number of samples to pick.
  - `high_value_threshold` (float, optional): Threshold for 100% testing.
- **Output**: Array of sampled transactions with detailed **Plain-Language Selection Reason** (e.g. *"Selected: Related Party + Top 5% Value ($₹14,50,000$)"*).

### 4. `run_cutoff_tod`
- **Allowed Roles**: `auditor`
- **Description**: Evaluates cut-off risk (Ind AS 115) by sampling 10 invoices before 31 March and 15 after 31 March, comparing Invoice Date vs LR Dispatch Date vs Accounting Entry Date.
- **Parameters**:
  - `cutoff_date` (str, default='2025-03-31'): Boundary date.
  - `window_before` (int, default=10): Pre-period sample count.
  - `window_after` (int, default=15): Post-period sample count.
- **Output**: Mapped records showing `cut_off_violation: true/false` and overstated amounts.

### 5. `detect_planted_fraud`
- **Allowed Roles**: `auditor`
- **Description**: Executes all 11 fraud detection modules (NetworkX cycle detection, RapidFuzz entity matching, duplicate LR checks, statistical spikes).
- **Parameters**: None.
- **Output**: Structured list of findings, impact amounts, standard citations (SA 240, SA 550, Ind AS 115), and affected parties.

### 6. `generate_workpaper`
- **Allowed Roles**: `auditor`
- **Description**: Generates the official 4-sheet Excel workbook (`.xlsx`) and JSON representation:
  1. *Sales Register*
  2. *Sales TOD*
  3. *Sales Cut-off TOD*
  4. *Credit Note TOD*
- **Parameters**:
  - `engagement_id` (str): Engagement identifier.
  - `export_excel` (bool, default=True): Returns path to generated `.xlsx`.

### 7. `propose_adjusting_entries`
- **Allowed Roles**: `auditor`
- **Description**: Synthesizes all audit findings into formal **Adjusting Journal Entries (AJEs)** for management to adjust the financial statements.
- **Output**: Structured entries with Account Name, Dr Amount, Cr Amount, and Narration.

### 8. `sign_off_workpaper`
- **Allowed Roles**: `auditor`
- **Description**: Records the Engagement Partner's digital sign-off, hashes the final workpaper, and locks the engagement.
- **Parameters**:
  - `engagement_id` (str)
  - `partner_name` (str)
  - `membership_number` (str)
  - `conclusion_summary` (str)
