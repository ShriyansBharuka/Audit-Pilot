# IDEAS & FUTURE ROADMAP: AuditPilot AI × Tally Integration

> Status note (Claude, 2026-10-10 21:30): sections 1–5 are **roadmap and positioning** (none of the Tally connectors
> exist yet; today the client uploads its register / uses the mock ERP). Section 6 describes the **SHAP that is built**
> (`app/explain.py`, the web app's `/shap` page). Checked against commit 12214c1.

> **Core Thesis:** AuditPilot AI is **not a replacement for Tally**, but an intelligent, non-invasive **"Auditor & Vigilance Co-Pilot"** that sits on top of Tally (and other ERPs like SAP and Zoho Books).
> 
> Tally is where the business records transactions; AuditPilot AI is the independent watchdog that verifies whether those transactions reflect real-world truth.

---

## 1. Product Positioning: The Two Market Modes

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TALLY PRIME / ERP SYSTEM                        │
│             (Where accountants type vouchers: F8, F6, F7)              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Real-time Sync / Export
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        AUDITPILOT AI ENGINE                            │
│  • Compares books with ground truth (E-Way bills, LRs, Bank feeds)     │
│  • 15 deterministic detectors (D0 to D14), 100% of the population      │
│  • Continuous AuditGraph Risk Scoring & Circular Trade Cycles          │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
       [ MODE 1: EXTERNAL AUDIT ]       [ MODE 2: INTERNAL VIGILANCE ]
       For Statutory CAs                For CFOs & Management
       • 100% reconciliation            • Real-time fraud detection
       • SA 530 reproducible sampling   • Early warning on rogue vouchers
       • 4-sheet workpapers & AJEs      • Pre-audit compliance readiness
```

### Mode 1: External Statutory Audit (For CA Firms)
- **Problem Solved:** Currently, clients give CAs a sanitized Excel export from Tally. Auditors can test only 25–35 samples manually.
- **AuditPilot Solution:** The CA firm connects AuditPilot AI to the client's Tally data. It audits 100% of transactions against external records (GST portal, e-way bills, bank statements), surfaces irregularities with evidence, and generates engagement-ready workpapers for the CA to review.

### Mode 2: Continuous Vigilance / Co-Pilot (For Companies & CFOs)
- **Problem Solved:** Companies discover employee embezzlement, fake invoices, or year-end stuffing months later during the annual audit.
- **AuditPilot Solution:** An enterprise "fraud firewall" that monitors Tally entries 365 days a year, alerting the CFO the moment a suspicious voucher is posted.

---

## 2. Technical Integration Methods with Tally

How AuditPilot AI can technically plug into Tally in production:

### Option A: Tally XML / ODBC Gateway (Zero-Code for User)
- **How it works:** Tally Prime runs an internal HTTP/XML and ODBC server on port `9000`.
- **Integration:** AuditPilot AI sends lightweight XML requests (`Export Data` requests) to pull:
  - All Sales Vouchers (`F8`)
  - Journal Vouchers (`F7`)
  - Credit Notes (`Alt + F6`)
  - Party Ledgers and Masters
- **Pros:** Completely standard; requires zero code changes to Tally.

### Option B: TDL Extension (Tally Definition Language Add-On)
- **How it works:** We write a small TDL script (`.tcp` file) that loads into Tally Prime.
- **Capabilities:**
  - Emits real-time webhooks or event logs to AuditPilot AI whenever an accountant accepts an `F8 Sales Voucher` or `F7 Journal Voucher`.
  - Can show a visual **"AuditPilot Risk Badge"** directly on the Tally voucher screen:
    - 🟢 *Green:* Validated with active E-Way bill and clean party history.
    - 🔴 *Red Alert:* "Warning: No physical dispatch record found / Potential Related Party match."
- **Distribution:** Can be published as an official add-on on the **Tally Shop (Tally Marketplace)**.

### Option C: Automated Ingestion & Folder Watcher
- **How it works:** Accountants already know how to export their *Sales Register*, *Day Book*, and *Trial Balance* to Excel/XML.
- **Integration:** AuditPilot AI runs a folder-watcher or upload portal that instantly ingests any Tally export, verifies the raw hash, and runs the audit pipeline in seconds.

---

## 3. High-Value Audit Enhancements over Tally

Tally has known structural gaps that accountants exploit to falsify books. AuditPilot AI specifically plugs these holes:

| Vulnerability in Tally | How Fraudsters Exploit It | How AuditPilot AI Neutralizes It |
| :--- | :--- | :--- |
| **Voucher Backdating** | Accountant presses `F2`, changes the date to March 31, and enters an invoice on April 15. | **Detector D13:** uses the entry order in the hash-chained ERP log (`erp_log.seq`), not a clock, to expose a document dated before entries that were recorded earlier (BACKDATED_ENTRY, SEQUENCE_BREAK, IRN_LATE). |
| **Manual Journal Vouchers (F7)** | Passing fake sales entries (`Dr Debtors, Cr Sales`) with no dispatch or commercial backing. | **Detector D7:** flags revenue postings that don't come from an invoice (REVENUE_WITHOUT_SALE), unusual contra accounts, post-closing and round-amount entries. |
| **Undisclosed Related Parties** | Selling to family or sister concerns without declaring the conflict of interest. | **Detector D1:** links parties through **exact** shared identifiers (PAN incl. the PAN inside a GSTIN, bank account, phone, email, address key) and director / relative links, with a guard against shared service providers; then D2 checks the client's RP list and its dates. No fuzzy name matching. |
| **Silent Edits to Old Vouchers** | Changing amounts or dates on old vouchers after year-end. | **D12 (integrity) / Ibrahim's ledger:** SHA-256 hash chain + anchors; an edit made outside the app (even straight into SQLite) shows up as OUT_OF_BAND_EDIT or a broken chain, and D11 marks affected samples STALE. |
| **April Credit Note Reversals** | Stuffing sales in late March to inflate numbers, then issuing Credit Notes in April to quietly reverse them. | **Detector D9:** Automatically matches post-year-end credit notes back to March invoices and calculates net revenue impact. |

---

## 4. Multi-ERP Expansion Roadmap

Beyond Tally, the same architecture can be connected to any accounting or ERP package:
1. **Zoho Books / QuickBooks Online:** Direct REST API webhooks for cloud-first startups.
2. **Busy Accounting Software:** The secondary desktop market leader in North India (ODBC/XML).
3. **SAP ECC & SAP S/4HANA:** Enterprise connector using SAP BAPI / RFCs to audit high-volume corporate sales registers.
4. **Shopify & ShipReady:** E-commerce sales channel connector pulling real-time consumer orders and refunds.

---

## 5. Talking Points for Presentation & Demo (The "Hook")

When presenting this project to judges:
1. **The Commercial Story:** *"We didn't build another accounting app. India already has Tally, and companies love it. We built the AI brain that verifies whether what was typed into Tally actually happened in the physical world."*
2. **Market Opportunity:** every active company in India (well over a million) must have its accounts audited every year (Companies Act 2013, s.139).
3. **Continuous Auditing:** *"Instead of a CA coming in once a year and relying on 30 samples, AuditPilot AI turns the audit into an always-on, 100% population check, and later a Tally Prime extension."*

---

## 6. Explainable AI: exact SHAP of the risk score (built)

> **Why it matters:** under **SA 230** (documentation) and **SA 500** (evidence) a CA can't rely on a black-box score.
> If the tool says an invoice is high risk, the partner must be able to show, factor by factor, **why**. NFRA's July
> 2026 paper on technology in audit makes the same point: tool output becomes evidence only after the auditor
> evaluates it.

### What we compute (`app/explain.py`, page `/shap`)
Shapley values come from cooperative game theory (Lloyd Shapley, 1953): each "player" gets its average marginal
contribution over every order in which players could join. Ours:

- **Players:** each risk hit on the invoice (a detector code, e.g. `PREMATURE`, `NO_MOVEMENT`) plus the customer's
  entity risk **E**. Not raw columns, so correlated fields (base / tax / total) can't split credit arbitrarily.
- **Model explained:** the real AuditGraph score `R = max(0.7·A + 0.3·E, 60 if hard evidence)`, where A is the
  noisy-OR of the hits. **Baseline** = a clean invoice of a clean customer (0).
- **Exact, not sampled:** with 2–7 players all 2^n coalitions are enumerated in milliseconds; the attributions
  **sum to the score exactly**, and the page shows that check. E's share is split over its five terms
  (0.35 C circular trading, 0.25 F other flagged sales, 0.15 T year-end concentration, 0.15 H open exceptions, 0.10 N
  related neighbours).
- **Global view:** mean |attribution| per risk code across every invoice scored ≥ 30 (≈ 0.2 s at 7k invoices).

Real example from the 7,003-invoice demo company (invoice G2/4754/25, dated 30 Mar 2026):

```
Baseline (clean invoice, clean customer)                          0.0
  + 49.0  PREMATURE (D3, severity 5): revenue before control passed
  + 21.0  INVOICE_DATE_VS_REMOVAL (D3, severity 3)
  +  5.7  Customer entity risk E = 19
            ├ +1.6 other flagged sales (F = 22)
            ├ +1.8 year-end concentration (T = 41)
            └ +2.2 open exceptions (H = 50)
──────────────────────────────────────────────────────────────────
Risk score R = 75.7  (HIGH)      check: Σφ = 75.70 = model output
```

All attributions are ≥ 0 by design: in this model, evidence of a problem adds risk and a clean check adds nothing,
so there are no "mitigating" bars.

### Next (roadmap)
- Write the top three attributions into the Sales TOD sheet as the reason a KEY sample was selected.
- Expose `explain_risk` as an MCP tool so agents (and our investigator) can cite the decomposition.
