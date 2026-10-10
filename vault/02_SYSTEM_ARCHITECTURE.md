# 02 - System Architecture & Component Design

This document describes the high-level architecture, module boundaries, data flows, and security constraints for the Statutory Audit & System of Record tool.

---

## 1. High-Level Architecture Diagram

```mermaid
flowchart TB
    subgraph Actors ["Users & AI Agents"]
        ClientAgent["Client Role / Company Accountant"]
        AuditorAgent["Auditor Role / Statutory CA"]
    end

    subgraph MCPLayer ["MCP Gateway (Model Context Protocol)"]
        RBAC["RBAC & Identity Verifier<br/>(Enforces SA 200 Auditor Independence)"]
        ClientTools["Client MCP Tools<br/>• create_order<br/>• record_dispatch<br/>• issue_invoice<br/>• issue_credit_note<br/>• upload_evidence"]
        AuditorTools["Auditor MCP Tools<br/>• get_sales_register<br/>• select_samples<br/>• verify_cutoff<br/>• detect_fraud<br/>• verify_ledger_hash<br/>• generate_workpaper<br/>• sign_off"]
    end

    subgraph BusinessSystem ["Mini ERP & System of Record"]
        Commercial["Commercial Engine<br/>Leads → Orders → Dispatches → Invoices → Credit Notes"]
        Ledger["Double-Entry Ledger Engine<br/>• Balancing Check (Dr = Cr)<br/>• SHA-256 Hash Chaining<br/>• Zero In-Place Mutations"]
        EventBus["Event & Change Notification<br/>• Trigger on new sales ledger upload<br/>• Detect post-sample tampering & alert 'stale'"]
    end

    subgraph AuditEngine ["Audit & Fraud Detection Engine"]
        Sampling["SA 530 Sampling Module<br/>(Fixed Seed, High-Value, RP Weighted)"]
        Matcher["3-Way Match & Cut-off Module<br/>(Invoice ↔ E-Way Bill ↔ LR ↔ GSTR-1)"]
        FraudDetectors["Specialized Fraud Detectors<br/>• NetworkX Cycle Finder (A→B→C→A)<br/>• RapidFuzz Entity Matcher (Undisclosed RPs)<br/>• Outlier Detector (Late March Stuffing)"]
    end

    subgraph Persistence ["Persistence Layer (SQLite)"]
        ERP_DB[("ERP Tables<br/>orders, dispatches, invoices, counterparties")]
        Ledger_DB[("Immutable Ledger<br/>ledger_entries, hash chain")]
        Workpaper_DB[("Workpaper Tables<br/>samples, findings, AJEs, signoffs")]
    end

    subgraph Deliverables ["Auditor Deliverables & UI"]
        Excel4Sheet["4-Sheet Workpaper (.xlsx)<br/>Register | TOD | Cut-off | Credit Notes"]
        FindingsMemo["Findings Memo & Proposed AJEs"]
        UIPortal["React CA Workstation UI"]
    end

    ClientAgent -->|identity=client| RBAC
    AuditorAgent -->|identity=auditor| RBAC
    RBAC -->|Allow ERP mutations| ClientTools
    RBAC -->|Allow read & audit only| AuditorTools
    RBAC -.->|Block auditor mutation (SA 200)| Commercial

    ClientTools --> Commercial
    Commercial --> Ledger
    Commercial --> ERP_DB
    Ledger --> Ledger_DB
    Commercial --> EventBus

    AuditorTools --> AuditEngine
    AuditEngine --> ERP_DB
    AuditEngine --> Ledger_DB
    AuditEngine --> Workpaper_DB
    EventBus -.->|Sample Stale Event| AuditEngine

    AuditEngine --> Excel4Sheet
    AuditEngine --> FindingsMemo
    AuditEngine --> UIPortal
```

---

## 2. Subsystem 1: Mini ERP & System of Record

The problem statement emphasizes that an auditor cannot trust an Excel sheet because anyone can fabricate rows. The Mini ERP is the ground truth.

### The 6 Stages of a Genuine Sale
1. **Commercial Commitment**: Sales Order (SO) agreed with counterparty terms and agreed pricing.
2. **Physical Movement**: Dispatch generation requiring:
   - **LR (Lorry Receipt)**: Transporter details, vehicle number, dispatch date.
   - **E-Way Bill**: Official 12-digit GST transit permit with validity dates.
   - **Delivery / POD**: Proof of delivery establishing transfer of control.
3. **Billing**: Invoice raised referencing SO and Dispatch.
4. **Accounting Posting**: Balanced double-entry posting to the ledger.
5. **Settlement**: Bank receipt matched against outstanding invoice debtor.
6. **Reversals / Adjustments**: Credit Notes or rebates referencing the original invoice.

---

## 3. Subsystem 2: Immutable Double-Entry Ledger (Ibrahim's Module)

### The Accounting Invariant
Every transaction creates at least two ledger lines:
$$\sum \text{Debits} = \sum \text{Credits}$$

For a standard invoice of ₹1,00,000 + 18% GST:
- `Debit`: Sundry Debtors (Customer Account) = ₹1,18,000
- `Credit`: Sales Revenue = ₹1,00,000
- `Credit`: GST Output Liability = ₹18,000

### The Cryptographic Invariant (Hash Chain)
- **Zero In-Place Updates**: `UPDATE` and `DELETE` queries are strictly forbidden. If an error occurs, a reversing journal entry (`REV-xxx`) must be inserted.
- **Hash Chaining**:
  $$\text{Hash}_n = \text{SHA-256}(\text{Hash}_{n-1} \,\|\, \text{EntryID} \,\|\, \text{Date} \,\|\, \text{Account} \,\|\, \text{Dr} \,\|\, \text{Cr} \,\|\, \text{RefID})$$
- **Tamper Detection**: An audit tool `verify_ledger_integrity` reads the chain sequentially from genesis ($H_0$). If any byte in SQLite was modified, the chain breaks at that index.

---

## 4. Subsystem 3: MCP Gateway & RBAC

Judges test the system by connecting their AI agents to your MCP server.

### The RBAC Matrix

| Capability | Client Identity | Auditor Identity | Enforcement Mechanism |
| :--- | :---: | :---: | :--- |
| Create Sales Order | ✅ Allowed | ❌ Blocked | MCP Gateway returns `SA 200 Independence Violation` |
| Record Dispatch / LR | ✅ Allowed | ❌ Blocked | MCP Gateway returns `SA 200 Independence Violation` |
| Issue Invoice | ✅ Allowed | ❌ Blocked | MCP Gateway returns `SA 200 Independence Violation` |
| Upload Evidence | ✅ Allowed | ❌ Blocked | MCP Gateway returns `SA 200 Independence Violation` |
| Read Sales Register | ✅ Allowed | ✅ Allowed | Read-only |
| Run TOD Sampling | ❌ Blocked | ✅ Allowed | Auditor audit tool |
| Run Cut-off Testing | ❌ Blocked | ✅ Allowed | Auditor audit tool |
| Run Fraud Detection | ❌ Blocked | ✅ Allowed | Auditor audit tool |
| Verify Ledger Chain | ❌ Blocked | ✅ Allowed | Auditor audit tool |
| Generate Workpaper | ❌ Blocked | ✅ Allowed | Auditor audit tool |
| Sign Off Workpaper | ❌ Blocked | ✅ Allowed | CA Engagement Partner only |

---

## 5. Subsystem 4: Change Detection & "Stale Sample" Alerting

A critical judging criterion:
> *"If the client changes anything after testing has begun, your system must detect it and show which samples it affects."*

### Implementation Mechanism:
1. When the Auditor runs `select_samples`, the system records:
   - `sample_id`, `invoice_id`, `sampled_at_timestamp`, `snapshot_hash`.
2. If the Client later calls `update_invoice` or adds a `credit_note` linked to that invoice:
   - An event triggers on the ledger / ERP.
   - The system flags the sample in the workpaper:
     > `⚠️ WARNING: Evidence for Sample #14 (INV-2025-0421) is STALE. Record modified by client post-sampling on 2026-04-05 14:22:10.`
