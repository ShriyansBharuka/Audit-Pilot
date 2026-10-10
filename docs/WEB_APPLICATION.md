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
│  FastAPI REST API (:8001) │   │       Supabase Cloud      │
│     (app/api_server.py)   │   │     (Project: Elevate)    │
│  MCP server stays on :8000│   │  - 23 RLS-Secured Tables  │
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
| `/shap` | **SHAP Explainability** | **Exact Shapley values** of the real AuditGraph score (`app/explain.py`): each risk hit and the customer's entity risk E are players of R = max(0.7A + 0.3E, floor); all coalitions enumerated, attributions sum to the score (shown as a check); E split over its five terms; global mean-abs importance across flagged invoices. |
| `/findings` | **Findings & Partner Sign-off** | Review queue of 31 proposed adjusting journal entries (AJEs) with balanced Dr/Cr COA inspection, mandatory partner review comments, and cryptographic sign-off modal. |
| `/evidence` | **Evidence & PBC Portal** | Client roles: their open requests (sample ref + document kind only, never the reason) and a per-request upload, stored verbatim with a server SHA-256. Audit roles: request statuses and received files. |
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

### 2. Start the MCP server and the REST API
```bash
python -m app.mcp_server                                                    # :8000, agents (MCP)
DEMO_ROLE_SWITCHER=1 python -m uvicorn app.api_server:app --port 8001       # :8001, the web app's REST API
```
`DEMO_ROLE_SWITCHER=1` (local demos only) lets the login screen offer one-click personas; **the partner token is never
listed**, and without the flag `/api/identities` returns no tokens at all.

### 3. Start the Next.js Frontend
```bash
cd web
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) (`npm run dev -- -p 3001` if 3000 is taken) and sign in with a token.
Set `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_MCP_URL` when the API or MCP server isn't on localhost.

### Access model (same as MCP)
Every `/api/audit/*` and `/api/integrations/*` endpoint needs an **audit** token (`audit_staff` or `engagement_partner`);
client tokens get 403 and see only `/evidence`. Evidence upload needs a **client** token. Partner decisions and
sign-off need the **partner** token (UI only; it's refused on MCP).

---

## Testing & Verification

- **API & Backend Test Suite:**
  ```bash
  python -m pytest tests/test_api_server.py -q
  ```
  *(10 tests: role guards on every endpoint, no token leaks, exact SHAP on every flagged invoice, deliverables)*

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
