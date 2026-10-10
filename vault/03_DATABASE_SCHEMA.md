# 03 - Database Schema Specification (SQLite)

This schema covers both the **Mini ERP System of Record** and the **Auditor Engine Tables**. It is written for SQLite (`audit.db`) with complete support for foreign keys, transaction constraints, and hash-chaining.

---

## 1. Master Data & Entity Resolution Tables

```sql
-- 1. Counterparty Master (Customers, Vendors)
CREATE TABLE parties (
    id TEXT PRIMARY KEY,                       -- e.g. 'PARTY-001'
    legal_name TEXT NOT NULL,
    trade_name TEXT,
    pan TEXT NOT NULL,                         -- 10-character Indian PAN (e.g., 'ABCDE1234F')
    gstin TEXT,                                -- 15-character GSTIN
    registered_address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    pincode TEXT NOT NULL,
    contact_phone TEXT,
    contact_email TEXT,
    bank_account_number TEXT,
    bank_ifsc TEXT,
    is_declared_rp BOOLEAN DEFAULT 0,          -- Client declared Related Party
    rp_effective_from DATE,                    -- Date from which entity became related
    rp_effective_to DATE,                      -- Date until which entity was related (null = current)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Director Master & Relatives Master (For undisclosed RP detection)
CREATE TABLE directors_and_relatives (
    id TEXT PRIMARY KEY,                       -- e.g. 'DIR-001'
    name TEXT NOT NULL,
    role TEXT NOT NULL,                        -- 'DIRECTOR', 'KMP', 'RELATIVE'
    relative_of_director_id TEXT REFERENCES directors_and_relatives(id),
    relationship TEXT,                         -- 'SPOUSE', 'BROTHER', 'FATHER', 'SON'
    pan TEXT NOT NULL,
    residential_address TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    bank_account_number TEXT
);
```

---

## 2. Mini ERP Commercial Workflow Tables

```sql
-- 3. Sales Orders
CREATE TABLE sales_orders (
    id TEXT PRIMARY KEY,                       -- e.g. 'SO-2025-001'
    so_number TEXT UNIQUE NOT NULL,
    customer_id TEXT NOT NULL REFERENCES parties(id),
    order_date DATE NOT NULL,
    total_base_amount NUMERIC(15, 2) NOT NULL,
    total_tax_amount NUMERIC(15, 2) NOT NULL,
    total_order_value NUMERIC(15, 2) NOT NULL,
    status TEXT DEFAULT 'CONFIRMED',           -- 'DRAFT', 'CONFIRMED', 'CANCELLED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Dispatches, E-Way Bills & Lorry Receipts (Physical Movement Proof)
CREATE TABLE dispatches (
    id TEXT PRIMARY KEY,                       -- e.g. 'DISP-2025-001'
    so_id TEXT NOT NULL REFERENCES sales_orders(id),
    dispatch_date DATE NOT NULL,               -- When goods physically left the factory
    transporter_name TEXT NOT NULL,
    lr_number TEXT NOT NULL,                   -- Lorry Receipt number
    lr_date DATE NOT NULL,
    vehicle_number TEXT NOT NULL,              -- e.g., 'MH-12-AB-1234'
    eway_bill_number TEXT,                     -- 12-digit GST portal e-way bill number
    eway_bill_date DATE,
    delivery_date DATE,                        -- Transfer of control date (Ind AS 115)
    evidence_file_path TEXT,                   -- Path to uploaded LR/E-way bill document
    evidence_file_hash TEXT,                   -- SHA-256 of the document for forgery check
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Sales Invoices
CREATE TABLE invoices (
    id TEXT PRIMARY KEY,                       -- e.g. 'INV-2025-001'
    invoice_number TEXT UNIQUE NOT NULL,
    so_id TEXT NOT NULL REFERENCES sales_orders(id),
    dispatch_id TEXT REFERENCES dispatches(id),-- NULL indicates ghost invoice (no movement)
    customer_id TEXT NOT NULL REFERENCES parties(id),
    invoice_date DATE NOT NULL,
    accounting_entry_date DATE NOT NULL,       -- When posted to financial books
    financial_year TEXT NOT NULL,              -- e.g. 'FY 2024-25'
    base_amount NUMERIC(15, 2) NOT NULL,
    cgst_amount NUMERIC(15, 2) NOT NULL,
    sgst_amount NUMERIC(15, 2) NOT NULL,
    igst_amount NUMERIC(15, 2) NOT NULL,
    total_amount NUMERIC(15, 2) NOT NULL,
    irn TEXT,                                  -- E-Invoice 64-char Hash (govt portal)
    status TEXT DEFAULT 'ISSUED',              -- 'ISSUED', 'CANCELLED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Credit Notes (Reversals & Rebates)
CREATE TABLE credit_notes (
    id TEXT PRIMARY KEY,                       -- e.g. 'CN-2026-001'
    cn_number TEXT UNIQUE NOT NULL,
    original_invoice_id TEXT NOT NULL REFERENCES invoices(id),
    cn_date DATE NOT NULL,
    reason TEXT NOT NULL,                      -- e.g. 'Sales Return', 'Year-end Rebate'
    base_amount NUMERIC(15, 2) NOT NULL,
    tax_amount NUMERIC(15, 2) NOT NULL,
    total_amount NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Double-Entry Immutable Ledger (Ibrahim's Module)

```sql
-- 7. Double-Entry General Ledger (Append-Only, Hash-Chained)
CREATE TABLE ledger_entries (
    id TEXT PRIMARY KEY,                       -- UUID or sequential format 'LE-00001'
    entry_number INTEGER NOT NULL UNIQUE,      -- Strictly strictly incrementing: 1, 2, 3...
    transaction_date DATE NOT NULL,
    reference_type TEXT NOT NULL,              -- 'INVOICE', 'CREDIT_NOTE', 'PAYMENT', 'MANUAL_JV'
    reference_id TEXT NOT NULL,                -- e.g. 'INV-2025-001'
    account_code TEXT NOT NULL,                -- e.g. 'DEBTORS', 'SALES_REVENUE', 'GST_OUTPUT_CGST'
    account_name TEXT NOT NULL,
    debit NUMERIC(15, 2) DEFAULT 0.00,
    credit NUMERIC(15, 2) DEFAULT 0.00,
    narration TEXT,
    prev_hash TEXT NOT NULL,                   -- SHA-256 of the previous ledger_entry (entry_number - 1)
    entry_hash TEXT NOT NULL,                  -- SHA-256(prev_hash + entry_number + date + account + debit + credit + ref_id)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Integrity trigger: Zero UPDATEs or DELETEs permitted
CREATE TRIGGER prevent_ledger_update
BEFORE UPDATE ON ledger_entries
BEGIN
    SELECT RAISE(FAIL, 'CRITICAL SECURITY VIOLATION: Ledger entries are immutable and cannot be updated.');
END;

CREATE TRIGGER prevent_ledger_delete
BEFORE DELETE ON ledger_entries
BEGIN
    SELECT RAISE(FAIL, 'CRITICAL SECURITY VIOLATION: Ledger entries are immutable and cannot be deleted.');
END;
```

---

## 4. Audit Engine & Workpaper Tables

```sql
-- 8. Audit Engagements
CREATE TABLE audit_engagements (
    id TEXT PRIMARY KEY,                       -- e.g. 'AUDIT-FY25'
    company_name TEXT NOT NULL,
    financial_year TEXT NOT NULL,
    client_sales_register_path TEXT,
    client_rp_list_path TEXT,
    sampling_seed INTEGER DEFAULT 42,
    status TEXT DEFAULT 'IN_PROGRESS',         -- 'IN_PROGRESS', 'REVIEWED', 'SIGNED_OFF'
    ca_signoff_by TEXT,
    ca_signoff_at TIMESTAMP,
    ca_signoff_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Sampled Transactions (Sales TOD & Cut-off TOD)
CREATE TABLE audit_samples (
    id TEXT PRIMARY KEY,                       -- e.g. 'SMPL-01'
    engagement_id TEXT REFERENCES audit_engagements(id),
    sample_type TEXT NOT NULL,                 -- 'SALES_TOD', 'CUTOFF_TOD', 'CREDIT_NOTE_TOD'
    invoice_id TEXT REFERENCES invoices(id),
    reason_for_selection TEXT NOT NULL,        -- e.g. 'High-Value (> ₹10L)', 'Related Party'
    stratum TEXT NOT NULL,                     -- 'HIGH_VALUE', 'RP_RISK', 'RANDOM_DIVERSE'
    snapshot_hash TEXT NOT NULL,               -- Hash of invoice fields when sampled
    is_stale BOOLEAN DEFAULT 0,                -- Flagged 1 if invoice modified post-sample
    audit_status TEXT DEFAULT 'PENDING',       -- 'VERIFIED', 'EXCEPTION_FOUND'
    exception_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Audit Findings & Proposed Adjusting Journal Entries (AJEs)
CREATE TABLE audit_findings (
    id TEXT PRIMARY KEY,                       -- e.g. 'FINDING-001'
    engagement_id TEXT REFERENCES audit_engagements(id),
    category TEXT NOT NULL,                    -- 'CUTOFF_ERROR', 'UNDISCLOSED_RP', 'CIRCULAR_TRADING', 'NO_DISPATCH'
    standard_violated TEXT NOT NULL,           -- 'Ind AS 115', 'SA 550', 'SA 240', 'Rule 138'
    invoice_id TEXT REFERENCES invoices(id),
    description TEXT NOT NULL,
    amount_impact NUMERIC(15, 2) NOT NULL,
    affected_fy TEXT NOT NULL,
    proposed_aje_json JSON NOT NULL,           -- Structured debits and credits to reverse/adjust
    is_accepted_by_ca BOOLEAN DEFAULT 0
);
```
