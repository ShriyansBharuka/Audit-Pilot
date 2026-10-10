# AuditPilot AI — Production Next.js Web Application

## Overview

AuditPilot AI is equipped with a modern, production-grade web application built with **Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons**, connected to the existing Python statutory audit engine (SQLite databases, 46 MCP tools, AuditGraph, and tamper-evident ledgers) and **Supabase** for multi-tenant organization management, granular RBAC, report sharing, and fraud investigation collaboration.

---

## Architecture & Technology Stack

```
┌────────────────────────────────────────────────────────┐
│             Next.js 16 Web Application (web/)           │
│  - Modern Financial Slate & Obsidian UI / UX           │
│  - Multi-Persona Role Switcher & Judge Card Token Auth  │
│  - 100% Population Explorer (D0–D14 Substantive Tests)  │
│  - AuditGraph & Minimum-Span Circular Trading Explorer  │
│  - SHAP Explainability Studio (Waterfall Attributions)  │
│  - Findings Review Queue & Partner Sign-off Lock        │
│  - PBC Evidence Upload Dropzone with SHA-256 Hashes     │
│  - Power BI Direct Web Connector & n8n Webhook Runner   │
└───────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│     FastAPI / MCP Server  │   │       Supabase Cloud      │
│     (app/api_server.py)   │   │     (Project: Elevate)    │
│  - Port 8000 (REST + MCP) │   │  - 23 RLS-Secured Tables  │
│  - Reads/Writes SQLite    │   │  - Multi-Tenant Orgs      │
│    (erp, ext, pbc, audit) │   │  - Granular RBAC Matrix   │
│  - Token-bound Security   │   │  - Field-Level Sharing    │
│  - Hash-Chained Trail     │   │  - Fraud Hub Threads      │
└───────────────────────────┘   └───────────────────────────┘
```

---

## Implemented Workflows & Pages

| Route | View | Description |
|---|---|---|
| `/` | **Audit Overview** | Executive cockpit with total tested revenue (₹10.26 Cr), population coverage (303 invoices), 15 detectors summary (D0–D14), circular trading exposure (₹5.63 Cr), and partner sign-off readiness. |
| `/transactions` | **100% Population Explorer** | Interactive high-density data table with search, filter by risk band (`HIGH`, `REVIEW`, `LOW`) and detector (`D0`–`D14`). Features a slide-over document trail drawer (IRN, E-Way Bill, Lorry Receipt, POD, and Journal Entries). |
| `/network` | **AuditGraph & Circular Trading** | Visualizes accommodation networks and detects 4 minimum-span circular trading loops (Companies Act s.143(12)) with entity node details and cycle turnover values. |
| `/shap` | **SHAP Explainability Studio** | Mathematical decomposition of AuditGraph risk scores into exact positive (risk-escalating) and negative (risk-mitigating) feature contributions with interactive waterfall charts. |
| `/findings` | **Findings & Partner Sign-off** | Review queue of 31 proposed adjusting journal entries (AJEs) with balanced Dr/Cr COA inspection, mandatory partner review comments, and cryptographic sign-off modal. |
| `/evidence` | **Evidence & PBC Portal** | Tracks 118 auditor requests sent to the client, provides a drag-and-drop file upload with server-computed SHA-256 fingerprinting, and tamper detection. |
| `/orgs` | **Organizations & Departments** | Multi-tenant organization creation, department tree hierarchy, member invitations, and role management backed by Supabase RLS. |
| `/permissions` | **Granular RBAC Matrix** | Resource-level access control matrix (`can_view`, `can_edit`, `can_approve`, `can_export`) with live toggles and immutable permission change logs. |
| `/sharing` | **Report Sharing & Field Masking** | Published deliverables manager (`.xlsx` workpaper, memo, trail) with selective field masking (summary vs detailed) and access verification logging. |
| `/investigations` | **Fraud Investigation Hub** | Cross-company docket management for circular trading and revenue fraud cases, threaded discussion logs, and traceable final decisions. |
| `/integrations` | **Power BI & n8n Orchestrator** | Direct Microsoft Power BI JSON Web Connector endpoint, MCP connection card for AI coding agents, and live n8n webhook workflow execution triggers. |
| `/trail` | **Hash-Chained Audit Trail** | Cryptographically chained audit log (SHA-256 sequence) verifying non-repudiation of every audit action. |

---

## Running the Web Application

### 1. Seed or Restore Development Data
```bash
python -m app.seed --reset --invoices 300
python -m app.demo_audit
```

### 2. Start the Backend API & MCP Server
```bash
python -m uvicorn app.api_server:app --host 0.0.0.0 --port 8000 --reload
```
The REST API is live at `http://localhost:8000` (docs at `/docs`), and the MCP endpoint is at `http://localhost:8000/mcp`.

### 3. Start the Next.js Frontend
```bash
cd web
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Testing & Verification

- **API & Backend Test Suite:**
  ```bash
  python -m pytest tests/test_api_server.py -q
  ```
  *(11 tests passing in <1s)*

- **Comprehensive End-to-End Audit Engine Self-Test:**
  ```bash
  python -m app.selftest
  ```
  *(23 passed, 0 failed)*

- **Next.js Production Build:**
  ```bash
  cd web
  npm run build
  ```
  *(12 static routes compiled and optimized)*
