# Project Vault: PS-04 Statutory Audit Automation & System of Record

Welcome to the **Knowledge Vault** for Problem Statement 04 (Statutory Audit Automation, Mini-ERP System of Record, and MCP Audit Engine).

This directory serves as the **single source of truth** for project requirements, regulatory standards, system architecture, database design, MCP tool specifications, fraud detection algorithms, and team division.

---

## 📂 Vault Contents & Reading Order

| File | Purpose | Key Details |
| :--- | :--- | :--- |
| **[`01_PROBLEM_STATEMENT.md`](file:///e:/Projects/Auditing%20Tool/vault/01_PROBLEM_STATEMENT.md)** | **Original Prompt & Requirements** | The verbatim problem statement, real-world context, core requirements, beyond-the-core criteria, and judging rules. |
| **[`02_SYSTEM_ARCHITECTURE.md`](file:///e:/Projects/Auditing%20Tool/vault/02_SYSTEM_ARCHITECTURE.md)** | **System Architecture** | High-level component diagrams, system data flows, event notifications, and RBAC boundary definitions. |
| **[`03_DATABASE_SCHEMA.md`](file:///e:/Projects/Auditing%20Tool/vault/03_DATABASE_SCHEMA.md)** | **Database & Ledger Schema** | SQLite schema for Mini ERP (Leads, SOs, Dispatches, Invoices) and the SHA-256 hash-chained immutable double-entry ledger. |
| **[`04_MCP_TOOLS_SPEC.md`](file:///e:/Projects/Auditing%20Tool/vault/04_MCP_TOOLS_SPEC.md)** | **MCP Tool Catalog & RBAC** | Model Context Protocol tool contracts, Client vs. Auditor role separation, and stale sample alert mechanics. |
| **[`05_FRAUD_DETECTION_ALGORITHMS.md`](file:///e:/Projects/Auditing%20Tool/vault/05_FRAUD_DETECTION_ALGORITHMS.md)** | **Fraud Engine & ICAI Standards** | Detection algorithms for all 11 planted fraud patterns (circular trading, undisclosed RPs, cut-off, stuffing, etc.) mapped to ICAI SAs. |
| **[`06_WORKPAPERS_AND_DELIVERABLES.md`](file:///e:/Projects/Auditing%20Tool/vault/06_WORKPAPERS_AND_DELIVERABLES.md)** | **Workpaper & Memo Format** | 4-tab workpaper structure (Sales Register, Sales TOD, Cut-off TOD, Credit Note TOD) and Findings Memo with Adjusting Journal Entries (AJEs). |
| **[`07_TECH_STACK_AND_ROADMAP.md`](file:///e:/Projects/Auditing%20Tool/vault/07_TECH_STACK_AND_ROADMAP.md)** | **Tech Stack & Team Division** | Python (FastAPI + FastMCP + SQLite) + React/Vite stack, 4-person responsibility matrix (including Ibrahim's role), and execution milestones. |

---

## 🤖 Instructions for AI Agents (Claude / Antigravity)
When executing reasoning or coding tasks on this project:
1. **Always read relevant vault files before answering or implementing.**
2. **Never modify business data from auditor contexts** (enforce SA 200 independence).
3. **Never silently clean or mutate client evidence**; every discrepancy between the client export and the underlying system of record is an audit finding.
4. **Ensure sample selections are deterministic and explainable** via a fixed random seed.
5. **Ensure all ledger entries strictly balance** ($\text{Debits} = \text{Credits}$) and remain cryptographically hash-chained.
