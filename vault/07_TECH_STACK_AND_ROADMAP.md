# 07 - Tech Stack, 4-Person Team Split & Implementation Roadmap

This document outlines the selected technology stack, project folder structure, work allocation for the 4 team members (highlighting Ibrahim's scope), and a step-by-step execution roadmap.

---

## 1. Selected Tech Stack

| Tier | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | **Python 3.11+ with FastAPI** | Ultra-fast development, native async, automatic OpenAPI docs (`/docs`), strong typing with Pydantic. |
| **MCP Implementation** | **FastMCP (Anthropic `mcp` SDK)** | Official Python Model Context Protocol SDK. Turns Python functions into tools with `@mcp.tool()` decorators. |
| **Database & Ledger** | **SQLite (`audit.db`)** | Zero installation for judges; single file; fully supports ACID transactions, triggers, and foreign keys. |
| **Graph & Fraud Libs** | **`networkx`** (Cycles), **`rapidfuzz`** (Fuzzy RPs), **`scipy`/`numpy`** (Z-scores) | Industry-standard libraries for graph cycle detection ($A \to B \to C \to A$) and entity resolution. |
| **Excel Generator** | **`openpyxl`** | Generates professional multi-tab `.xlsx` files with colored headers, borders, and number formatting. |
| **Frontend** | **React (Vite) + Tailwind CSS** | Clean corporate UI: Live ERP tab, 4-sheet workpaper viewer, fraud visualizer, CA sign-off modal. |

---

## 2. 4-Person Work Allocation Matrix

This split ensures all 4 members can build in parallel without merge conflicts.

```
┌────────────────────────────────────────────────────────┐
│ Member 1 (Ibrahim)                                     │
│ Scope: Double-Entry Immutable Ledger & Cryptography    │
│ • Database schema for ledger_entries                   │
│ • Double-entry balancing enforcement (Dr == Cr)        │
│ • SHA-256 hash chaining (prev_hash -> entry_hash)     │
│ • Zero-mutation SQLite triggers                        │
│ • Hash verification test suite (tamper detection)      │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ Member 2                                               │
│ Scope: Mini ERP System of Record & MCP Gateway         │
│ • Commercial models: Orders, Dispatches, Invoices, CNs │
│ • FastMCP Server setup (stdio + SSE transports)        │
│ • Identity-based RBAC (Auditor vs Client permissions)  │
│ • Stale sample listener (alert if client alters record)│
│ • Client upload portal & webhook notification          │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ Member 3                                               │
│ Scope: Audit Engine, Sampling & Fraud Algorithms       │
│ • SA 530 Sampling (Seed=42, High-Value, RP weighted)   │
│ • Circular trading graph cycle detector (networkx)     │
│ • Undisclosed RP fuzzy matcher (rapidfuzz)             │
│ • Cut-off analyzer (Ind AS 115 date comparison)        │
│ • Three-way document match (Invoice vs E-Way vs LR)    │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ Member 4                                               │
│ Scope: Deliverables, Workpapers, Memo & React UI       │
│ • 4-Sheet Excel workbook generator (openpyxl)          │
│ • Findings memo generator with proposed AJEs           │
│ • React UI: 4-sheet workpaper grid & status badges     │
│ • Fraud alert panel & circular trade visualizer        │
│ • CA digital sign-off workflow                         │
└────────────────────────────────────────────────────────┘
```

---

## 3. Recommended Project Folder Structure

```text
Auditing Tool/
├── vault/                              # Knowledge Vault (Requirements & Specs)
│   ├── README.md
│   ├── 01_PROBLEM_STATEMENT.md
│   ├── 02_SYSTEM_ARCHITECTURE.md
│   ├── 03_DATABASE_SCHEMA.md
│   ├── 04_MCP_TOOLS_SPEC.md
│   ├── 05_FRAUD_DETECTION_ALGORITHMS.md
│   ├── 06_WORKPAPERS_AND_DELIVERABLES.md
│   └── 07_TECH_STACK_AND_ROADMAP.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI REST API entry point
│   │   ├── config.py
│   │   ├── database.py                 # SQLite connection & schema init
│   │   ├── ledger/                     # Ibrahim's module
│   │   │   ├── engine.py               # Double-entry posting logic
│   │   │   ├── hasher.py               # SHA-256 chain calculation
│   │   │   └── verifier.py             # Full chain integrity checker
│   │   ├── erp/                        # Mini ERP (Member 2)
│   │   │   ├── router.py
│   │   │   ├── services.py             # Orders, Dispatches, Invoices
│   │   │   └── models.py
│   │   ├── mcp_server/                 # FastMCP Gateway (Member 2)
│   │   │   ├── server.py               # MCP server instance
│   │   │   ├── rbac.py                 # SA 200 independence enforcement
│   │   │   └── tools.py                # Registered MCP tools
│   │   ├── audit/                      # Audit Engine (Member 3)
│   │   │   ├── sampler.py              # SA 530 deterministic sampling
│   │   │   ├── cutoff.py               # Ind AS 115 cutoff testing
│   │   │   ├── fraud_detectors.py      # RapidFuzz, NetworkX, Z-score
│   │   │   └── stale_checker.py        # Post-sample alteration detector
│   │   └── deliverables/               # Workpaper & Memo (Member 4)
│   │       ├── excel_generator.py      # openpyxl 4-tab workbook
│   │       ├── memo_generator.py       # Findings & AJEs builder
│   │       └── signoff.py              # CA digital sign-off
│   ├── tests/
│   │   ├── test_ledger_tampering.py    # Proves hash break on silent edit
│   │   ├── test_rbac_independence.py   # Proves auditor cannot create SO
│   │   ├── test_fraud_scenarios.py     # Verifies all 11 frauds are caught
│   │   └── test_sampling_seed.py       # Verifies deterministic samples
│   ├── data/
│   │   └── seed_mock_data.py           # Generates 8,000 realistic sales + planted fraud
│   └── requirements.txt
└── frontend/                           # React UI (Member 4)
    ├── index.html
    ├── package.json
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── LiveERPView.jsx
    │   │   ├── WorkpaperTabs.jsx
    │   │   ├── FraudDashboard.jsx
    │   │   ├── CircularGraph.jsx
    │   │   └── CASignoffModal.jsx
    │   └── services/
    │       └── api.js
    └── tailwind.config.js
```

---

## 4. 5-Phase Implementation Roadmap

### Phase 1: Core Foundation & Ibrahim's Ledger (Milestone 1)
- Set up SQLite schema with foreign keys and trigger locks.
- Implement double-entry debit/credit balance verification.
- Implement SHA-256 hash chaining: $H_n = \text{SHA256}(H_{n-1} + \dots)$.
- Write `test_ledger_tampering.py` (demonstrates that updating a single SQLite row breaks all subsequent hashes).

### Phase 2: Mini ERP & FastMCP Gateway (Milestone 2)
- Implement commercial endpoints: Orders $\to$ Dispatches (LR & E-way) $\to$ Invoices $\to$ Credit Notes.
- Set up `FastMCP` with tools exposed for both Client and Auditor.
- Add identity enforcement: block `auditor` from mutating ERP state.
- Implement stale sample tracking when records change post-sampling.

### Phase 3: Audit Engine & Planted Fraud Detectors (Milestone 3)
- Build SA 530 deterministic sampling (`seed=42`, high-value top 5%, related-party weighting).
- Implement Cut-off TOD ($\pm 15$ invoices around 31-March vs LR dates).
- Implement NetworkX cycle detection for circular trading.
- Implement RapidFuzz for undisclosed related party detection.
- Implement 3-way match (Invoice $\leftrightarrow$ E-way Bill $\leftrightarrow$ LR).

### Phase 4: 4-Sheet Workpaper, Findings Memo & UI (Milestone 4)
- Build `openpyxl` generator producing the 4-tab `.xlsx` workpaper.
- Build Findings Memo generator with formatted **Adjusting Journal Entries (AJEs)**.
- Build React interface with:
  - 4-tab workpaper viewer.
  - Fraud alert drawer.
  - CA sign-off modal with digital stamp.

### Phase 5: Planted Dataset & Judge Demo Rehearsal (Milestone 5)
- Create `seed_mock_data.py` with 7,000 genuine sales and exactly the 11 planted fraud scenarios.
- Connect an AI agent via MCP and run a mock audit round.
- Verify that every single planted anomaly is flagged with the exact ICAI standard citation.
