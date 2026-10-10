# Handoff: platform extras (Power BI package, analytics charts, documentation agent, org/role switching)

You're implementing four features for AuditPilot. Read `AGENTS.md`, `CLAUDE.md` and `vault/README.md` first. They override anything here, and the non-negotiable rules there (identity from the token only, integer paise, append-only tables, human-only sign-off, no `mcp.server.fastmcp`) apply in full.

**Deadline pressure:** judging is in hours. Ship in the order below and commit after each feature, so a later failure never costs an earlier win. If a feature can't be finished cleanly, ship the smaller version described under "minimum" and say so in `vault/PROGRESS.md`.

## Where things are (corrections to the original request)

- **The UI is the Next.js app in `web_v2/`**, not Streamlit `ui/app.py`. "Organizations & Depts", "Integrations & Power BI" and the analytics views are pages in `web_v2/src/app/*`. Leave `ui/app.py` working but don't build these features there.
- **Don't edit `web/`.** It's the version currently being demoed on port 3100, and `web_v2/` replaces it later. If you run on Shriyans's laptop: don't stop anything on ports 3100, 3200 or 8001. Run your own dev server on 3300 (`cd web_v2 && npx next dev -p 3300`) and your own API on 8002 (`python -m uvicorn app.api_server:app --port 8002`, then point the app at it with `NEXT_PUBLIC_API_URL=http://localhost:8002`). On another machine: `cd web_v2 && npm ci` first. `web_v2/node_modules` is gitignored, and the local copy is a junction to `web/node_modules`.
- **`web_v2` styling** is Supabase-like dark: neutral greys, one green accent (the `indigo-*` classes resolve to green in `globals.css`), plain text instead of coloured pills, `rounded-md`/`rounded-lg`, no shadows, no bold monospace, short labels. Follow `web_v2/src/app/page.tsx` as the reference: a bordered stat strip and a plain table. Don't add explanatory paragraphs, formulas or model internals to the UI.
- **REST API:** add endpoints to `app/api_server.py` and client calls to `web_v2/src/lib/api.ts`. Auth is the existing Bearer token, and the role comes from the token.
- **No chart library is installed**, and the web app's only dependencies are `lucide-react` and Supabase. Draw charts as inline SVG (see `web_v2/src/app/shap/page.tsx` and the `CycleRing` in `web_v2/src/app/network/page.tsx`). For tooltips, use React hover state or an SVG `<title>`. Don't add Recharts or another chart dependency.
- **Already built, so reuse rather than rewrite:**
  - `app/analytics.py` already computes Benford (`BENFORD_FIRST_DIGIT`) and the D5 year-end codes (`END_WINDOW_SHARE`, `DISCOUNT_SPIKE`, `NEW_CUSTOMER_AT_YEAR_END`, `SCHEME_WINDOW`).
  - `app/memo.py` (`build`, `_aje_table`, `_html`) and `app/reports.py` (`year_end`, `continuous`, `render(report, fmt)`) already produce memo and report content in json/md/html.
  - `GET /api/integrations/powerbi` already serves a JSON dataset.
  - `POST /api/auth/token-login` and `GET /api/identities` already exist. The login screen already lists demo personas when `DEMO_ROLE_SWITCHER=1`.
- **Money stays integer paise** in every file and endpoint. Power BI gets paise columns, and DAX divides by 100. Use stdlib `csv`, `zipfile`, `statistics` and `math`; no pandas, numpy or floats on client money. Floats are fine only for derived statistics such as z-scores, chi-square and percentages.

## 1. Power BI dataset package (do first: lowest risk)

- `GET /api/integrations/powerbi/package` returns a zip (auditor roles only) containing:
  - `Fact_Invoices.csv`: invoice_no, invoice_date, party_id, taxable_paise, tax_paise, total_paise, risk_score, sample_status
  - `Dim_Customers.csv`: party_id, name, state_code, is_related_party, entity_risk_E
  - `Dim_Detectors.csv`: detector_id, name, standard, severity (take names and standards from the detector table used by the overview page; keep one source of truth in Python)
  - `Fact_Findings_AJEs.csv`: finding_id, invoice_no (nullable), category, status, impact_paise, aje_account, aje_debit_paise, aje_credit_paise
  - `measures.dax` with Total Revenue, Materiality Threshold, Flagged Fraud Volume, Cut-off Error %, RP Exposure %
- `GET /api/v1/powerbi/feed` is the JSON "Web" source. Make it an alias of, or wrapper around, the existing `/api/integrations/powerbi`, and don't duplicate the queries.
- Excel/CSV safety: client text is untrusted. Prefix any cell starting with `= + - @` with `'` (formula injection).
- UI: a "Download dataset" button on `web_v2/src/app/integrations/page.tsx`.
- Test (`tests/test_powerbi_export.py`): the zip has the 5 files, every invoice key in the facts exists in `Dim_Customers`, money columns are integers, and the formula-injection guard works.
- **Minimum:** the zip with the 4 CSVs and the DAX file, no UI polish.

## 2. Analytics charts

Backend: one endpoint `GET /api/audit/analytics/charts` (auditor roles), computed from ERP (read-only `db.connect('erp', role)`), returning:
- **Daily volume:** the count and total paise per day for the FY, mean and stdev of daily totals, and a z-score per day. Flag days with z ≥ 3 and mark the last 10 days of March.
- **Benford:** first-digit counts 1–9 across invoice totals, expected proportions `log10(1+1/d)`, chi-square, and `flagged = chi2 > 15.507` (df 8, α 0.05). Reuse or extract the digit logic already in `analytics.py`, and don't keep two copies.
- **Risk:** a histogram of invoice risk scores in bands (<30, 30–69, ≥70), plus scatter points `{invoice_no, total_paise, risk_score, category}`. The category comes from the invoice's top detector hit. Cap the scatter at about 2,000 points and keep all high-risk ones.

Frontend: new page `web_v2/src/app/analytics/page.tsx` plus a sidebar entry "Analytics" in `web_v2/src/components/Navigation.tsx`:
- **Volume:** a line chart with a ±3σ band, highlighting the March period-end window.
- **Benford:** paired bars (actual vs expected) with a one-line verdict ("Consistent with Benford" / "Deviates: χ² 23.4").
- **Risk:** a histogram and a scatter (log-scale x for amount), with hover tooltips.

Labels stay short, and there are no formulas in the UI.

Test (`tests/test_analytics_charts.py`): Benford expected proportions sum to 1; chi-square is 0 for a perfectly Benford sample and large for uniform digits; a synthetic spike day gets z ≥ 3.

**Minimum:** Benford and volume charts only.

## 3. Documentation agent (statutory revenue audit memorandum)

- MCP tool `generate_statutory_audit_report` in `app/tools_audit.py` (audit roles), plus `POST /api/audit/deliverables/statutory-memo`. Follow the Gateway pattern and error format in `vault/04 §2–3`, and add the tool to the `vault/04` tools list in the same commit (a contract change).
- Content is assembled deterministically from `memo.build` and `reports.year_end` (findings F-xxx, detector hits, SHAP summary, sampling metadata, materiality):
  - executive summary and scope
  - ROMM evaluation against materiality
  - observations grouped by standard (SA 240, SA 550, Ind AS 115, CGST Rule 138)
  - an AJE summary table
- An LLM may only polish prose, and only when an API key is set (follow `reports._ai_summary`), and the output is marked **PROPOSED / DRAFT**. Never put client text into server-written prose: quote it as data.
- Export: Markdown, and PDF via `pymupdf` (already in requirements; render the HTML from `memo._html` or plain text). Store nothing in append-only tables beyond what the existing memo flow already does.
- UI: on `web_v2/src/app/findings/page.tsx` or a new `web_v2/src/app/report/page.tsx`, add a "Draft memo" button, a rendered preview, and "Download .md" / "Download .pdf". Confirming or signing off stays partner-only, through the existing flow.
- Test (`tests/test_statutory_memo.py`): the memo contains every PROPOSED finding id and the AJE totals match the findings (integer paise); a client string with `ignore previous instructions` appears only inside a quote/data block.
- **Minimum:** the Markdown memo through REST and the UI preview; PDF is a bonus.

## 4. Role and organisation switching (riskiest: do last)

- **Role switching:** no role parameter anywhere. "Switch persona" means signing in with another token. Add "Switch user" to the user menu in `web_v2/src/components/Navigation.tsx`, which shows the existing persona list from `/api/identities` (demo mode only, and never the partner token, as today).
- **Organisations:** the ERP schema has no tenant column. Every table is single-company, and `config.ENGAGEMENT_ID` picks the engagement. Don't add `org_id` columns across the schema at this stage. Instead:
  - Implement each tenant as its own data directory (`data/tenants/<slug>/erp.db`, `audit.db`) with its own engagement, and resolve the active tenant server-side for the request. If you add a tenant selector header, it may only pick among tenants the token's principal is allowed to see. It must never grant a role.
  - Seed tenant 2, "Sahyadri Shipyards Enterprises", with `app.seed` into its own directory (small, e.g. `--invoices 300`), and keep Konkan Marine Controls Ltd as the default.
  - "+ New organization" (name, PAN, GSTIN, FY) creates an empty tenant directory and engagement. Validate PAN and GSTIN formats.
  - Document the tenant model in `vault/03` and `vault/07` in the same commit (a contract change).
- The current `web_v2/src/app/orgs/page.tsx` reads Supabase directly from the browser via `supabaseService`. Don't extend that path, and route through the REST API instead.
- Test: a token sees only its tenants; switching the tenant changes `/api/audit/overview` `entity_name` and the invoice count; tenant 2 data never appears under tenant 1.
- **Minimum, if time runs out:** the persona switcher plus a read-only org list showing the two seeded tenants, with switching disabled ("coming soon"). Don't ship half-wired tenant filtering.

## Done means

1. `python -m pytest -q` passes with no regressions, and `python -m app.selftest` passes. Paste both results.
2. `cd web_v2 && npx tsc --noEmit` is clean.
3. `streamlit run ui/app.py` and `python -m app.mcp_server` still start.
4. One line per feature appended to `vault/PROGRESS.md` (`YYYY-MM-DD HH:MM · <ID> · done|partial · what · next`), using IDs EX-1 (Power BI), EX-2 (analytics), EX-3 (doc agent), EX-4 (orgs/roles).
5. One commit per feature, named `EX-n: <what>`. Run `git pull --rebase` before pushing. Never commit `.env`, `identities.json`, `data/`, `*.db` or `node_modules`. Push only when the human says so.
