# 03 · Database schema (the only schema)

> Revised by Claude, 2026-10-10. Replaces Antigravity's first draft. If code and this file disagree, fix one of them and note it in `PROGRESS.md`.
> Tool names used below are defined in `04_MCP_TOOLS_SPEC.md`. Detector codes (D0–D14) are defined in `05`.

## 0. Why four files

The PS says *"an auditor identity must never change business data"*. We enforce that with **SQLite itself**, not with if-statements. An audit-role connection to the business files is opened read-only, so a buggy auditor tool physically cannot write.

| File | What it is | Client roles | Audit roles (`audit_staff`, partner UI) | Who writes it |
|---|---|---|---|---|
| `erp.db` | The client's system of record: masters, orders, movements, invoices, CNs, settlements, ledger, `erp_log` | read-write | **read-only** (`mode=ro` + `query_only`) | client tools via `erp.write_doc` / `ledger.post_journal` |
| `ext.db` | Independent third parties: mock IRP (e-invoice), e-way bill portal, GSTN returns, bank statement, MCA registry | read-only | read-only | only `portal.py` functions (triggered by client actions) and the seeder |
| `pbc.db` | "Prepared by client" channel: evidence requests, client submissions (register, RP list, evidence files), register exports | read requests, insert submissions | read-write | requests: audit tools; submissions: `intake.submit()` |
| `audit.db` | The auditor's file: engagement, frozen verbatim register, samples, risk hits, findings/AJEs, anchors, events, `audit_trail` | **no handle at all** | read-write | audit tools, the audit engine (system principal), the trail writer, partner UI |

The `orchestrator` role (n8n) gets read-only handles to `audit.db` and `pbc.db`, and none to `erp.db`.

## 1. Conventions (all files)

- **Money is `*_paise INTEGER`, always ≥ 0.** The only exceptions are `ext.bank_txns.amount_paise` (signed: + in, − out) and `invoices.round_off_paise` (signed, small). Tools take rupees as **strings** (`"118000.50"`) and convert with `to_paise()`. **No REAL / NUMERIC / DECIMAL column anywhere.** SQLite's `NUMERIC(15,2)` silently turns `118000.0` into `118000` and makes hashes fail.
- Rates are basis points (`gst_rate_bp = 1800` means 18%). Quantities are `INTEGER` in the item's base unit.
- Dates are `TEXT 'YYYY-MM-DD'`; timestamps are ISO-8601 `TEXT` with `+05:30`. All date logic runs in **Asia/Kolkata**. The FY is always derived from dates (FY 2025-26 = 2025-04-01..2026-03-31) and never stored as a string.
- Every connection runs `PRAGMA foreign_keys=ON; PRAGMA recursive_triggers=ON;`. Run `PRAGMA journal_mode=WAL` once at init. Every write is one `BEGIN IMMEDIATE` transaction.
- Cross-file references are plain TEXT ids (plus `erp_seq`). **Never `REFERENCES` across files**: SQLite foreign keys cannot cross schema boundaries.
- **Constraints enforce integrity, never business policy.** An invoice without an SO or movement, a return CN with no inward goods, or a rebate without a scheme must all be *recordable*, so the engine can catch them and judges can plant them.
- Invoice and CN numbers are **system-assigned** in one consecutive series per unit per FY (CGST Rule 46(b)), using `doc_counters`. Tools never accept a number, except `import_records`, which keeps the source numbers (and they are tested the same way).
- `recorded_at`, `recorded_by` and `posted_by` are set by the server and are never tool arguments.

Flags: **[H]** hash-chained by `chain.py` · **[A]** append-only (BEFORE UPDATE/DELETE → `RAISE(ABORT)`) · **[V]** changed only via `amend_record`, with every version kept in `erp_log` · **[F]** financial: never edited, only `cancel_document` (auto REVERSAL journal) or a credit note · **T1** build now · **T2** build if time allows.

## 2. erp.db: the client's system of record

| # | Table | Flags | Key columns |
|---|---|---|---|
| 1 | `parties` | V T1 | id PK, kind `ENTITY\|PERSON`, tags (CSV of `SELF,CUSTOMER,VENDOR,TRANSPORTER,DIRECTOR,KMP,RELATIVE`), name, pan?, gstin?, state_code?, address, pincode, phone?, email?, bank_account?, ifsc?, recorded_by, recorded_at. Row `id='SELF'` is the audited company. When pan is null, derive it from `gstin[2:12]`. |
| 2 | `party_links` | V T1 | id PK, from_party, to_party, relation `DIRECTOR_OF\|KMP_OF\|SHAREHOLDER_OF\|RELATIVE_OF\|CONTROLS\|PARTNER_OF`, pct_bp?, effective_from, effective_to?, source `MBP-1\|DIR-12\|REGISTER\|OTHER`. This is the RP truth, with dates. |
| 3 | `items` | V T1 | id PK, name, hsn (`99…` = service), uom, gst_rate_bp, list_rate_paise, cost_paise (for the COGS leg of cut-off AJEs). Charges are items too: `CHG-PACKING`, `CHG-FREIGHT`, `CHG-INSURANCE`. |
| 4 | `schemes` | V T1 | id PK, name, kind `TRADE_DISCOUNT\|VOLUME_REBATE\|CASH_DISCOUNT\|FREE_QTY`, rate_bp, min_qty?, valid_from, valid_to, announced_on, approved_by?. These are the "promotions that drive demand". |
| 5 | `sales_orders` | V T1 | id PK, so_no, party_id, status `ENQUIRY\|QUOTED\|CONFIRMED\|CLOSED\|LOST`, enquired_on, channel `EMAIL\|PHONE\|VISIT\|PORTAL\|SHOPIFY`, contact_name/phone/email, quoted_on?, confirmed_on?, customer_po_no?, delivery_terms `EX_WORKS\|FOR_DISPATCH\|FOR_DESTINATION\|BILL_AND_HOLD\|CONSIGNMENT`, credit_days, scheme_id?, bill_and_hold_json? (Ind AS 115 B81 checklist). A lead is an SO row in `ENQUIRY`. |
| 6 | `so_lines` | T1 | so_id, line_no, item_id, qty, rate_paise, discount_paise · PK(so_id, line_no) |
| 7 | `movements` | V T1 | id PK, direction `OUT\|IN` (IN = sales return), party_id, so_id?, moved_on, from_pincode, to_pincode, transporter_id?, vehicle_no?, lr_no?, lr_date?, gate_pass_no?, delivered_on?, received_by?. A POD is an amend (`record_delivery`). |
| 8 | `movement_lines` | T1 | movement_id, item_id, qty · PK(movement_id, item_id) |
| 9 | `invoice_movements` | V T1 | invoice_id, movement_id, ewb_no? (whatever the client typed; may be fake) · PK(invoice_id, movement_id). Many-to-many: one truck/LR can carry many invoices, and one invoice can split across loads. |
| 10 | `invoices` | F T1 | id PK, invoice_no UNIQUE, series (unit, e.g. `G2`), supplier_gstin (the unit's GSTIN), invoice_date, party_id, so_id?, buyer_gstin?, place_of_supply (state code), irn? (as recorded by the client), round_off_paise (signed), status `ISSUED\|CANCELLED`, cancelled_on? |
| 11 | `invoice_lines` | T1 | invoice_id, line_no, item_id, hsn, qty, rate_paise, discount_paise, scheme_id?, taxable_paise, gst_rate_bp, igst_paise, cgst_paise, sgst_paise · PK(invoice_id, line_no). **No stored header totals: always SUM the lines.** |
| 12 | `credit_notes` | F T1 | id PK, cn_no UNIQUE, cn_date, party_id, reason `SALES_RETURN\|RATE_DIFF\|SCHEME_REBATE\|QUALITY\|OTHER`, reason_text?, scheme_id?, return_movement_id?, irn?, status |
| 13 | `cn_lines` | T1 | cn_id, line_no, invoice_id? (**nullable**, because an unlinked CN is itself a flag), item_id?, qty?, taxable_paise, igst/cgst/sgst_paise. One CN may credit many invoices (s.34(1)). |
| 14 | `settlements` | F T1 | id PK, direction `RECEIPT\|PAYMENT`, settled_on, party_id, doc_type `INVOICE\|PURCHASE\|ADVANCE\|OTHER`, doc_id?, amount_paise, bank_txn_id? (→ ext.bank_txns), mode. One row per (bank txn, document). |
| 15 | `purchase_bills` | F T2 | id PK, vendor_id, bill_no, bill_date, item_id, qty, taxable_paise, tax_paise. This is enough to close round-trip cycles (D10). |
| 16 | `accounts` | V T1 | code PK, name, type `ASSET\|LIABILITY\|EQUITY\|INCOME\|EXPENSE`, is_revenue 0/1 |
| 17 | `journals` | A T1 | no INTEGER PK, voucher_date, voucher_type `OPENING\|SALES\|CREDIT_NOTE\|RECEIPT\|PURCHASE\|PAYMENT\|JOURNAL\|REVERSAL`, source_type?, source_id?, reverses_no?, aje_ref?, narration NOT NULL, posted_by, recorded_at |
| 18 | `journal_lines` | A T1 | journal_no, line_no, account_code → accounts, party_id?, dr_paise, cr_paise · CHECK single-sided · PK(journal_no, line_no) |
| 19 | `erp_log` | H A T1 | seq INTEGER PK, recorded_at, actor, role, tool, action `CREATE\|AMEND\|CANCEL\|POST\|IMPORT`, doc_type, doc_id, before_json?, after_json, reason?, prev_hash UNIQUE, hash. **The edit log**: every master, document and journal write appends here, in the same transaction. This is the audit trail/edit log required by Companies (Accounts) Rules 2014 r.3(1). |
| 20 | `doc_counters` | T1 | series, fy_start, next_no · PK(series, fy_start) |

Seed COA (`*` = is_revenue): BANK, DEBTORS, CREDITORS, INVENTORY, CONTRACT_LIABILITY, REFUND_LIABILITY, SALES\*, SALES_EXPORT\*, SALES_SERVICE\*, OTHER_OPERATING_REVENUE\*, SALES_RETURNS\*, DISCOUNTS_ALLOWED\*, OUTPUT_IGST, OUTPUT_CGST, OUTPUT_SGST, PURCHASES, COGS, INPUT_IGST, INPUT_CGST, INPUT_SGST, ROUND_OFF, SUSPENSE, DIRECTOR_LOAN, OTHER_INCOME.

System postings (inside the same transaction as the document):
- **Invoice** → SALES voucher: Dr DEBTORS[party] = total; Cr SALES (or the line's revenue account) = taxable; Cr OUTPUT_IGST, or OUTPUT_CGST + OUTPUT_SGST; ROUND_OFF as needed.
- **CN** → CREDIT_NOTE voucher (the mirror image).
- **Receipt** → RECEIPT voucher (Dr BANK / Cr DEBTORS[party]).
- **Cancel** → REVERSAL voucher with `reverses_no`.
- Never UPDATE a journal.

### Key DDL (copy exactly)

```sql
CREATE TABLE accounts (code TEXT PRIMARY KEY, name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('ASSET','LIABILITY','EQUITY','INCOME','EXPENSE')),
  is_revenue INTEGER NOT NULL DEFAULT 0 CHECK (is_revenue IN (0,1)));
CREATE TABLE journals (no INTEGER PRIMARY KEY, voucher_date TEXT NOT NULL,
  voucher_type TEXT NOT NULL CHECK (voucher_type IN ('OPENING','SALES','CREDIT_NOTE','RECEIPT','PURCHASE','PAYMENT','JOURNAL','REVERSAL')),
  source_type TEXT, source_id TEXT, reverses_no INTEGER REFERENCES journals(no), aje_ref TEXT,
  narration TEXT NOT NULL, posted_by TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE journal_lines (journal_no INTEGER NOT NULL REFERENCES journals(no), line_no INTEGER NOT NULL,
  account_code TEXT NOT NULL REFERENCES accounts(code), party_id TEXT REFERENCES parties(id),
  dr_paise INTEGER NOT NULL DEFAULT 0 CHECK (dr_paise >= 0), cr_paise INTEGER NOT NULL DEFAULT 0 CHECK (cr_paise >= 0),
  CHECK ((dr_paise = 0) <> (cr_paise = 0)), PRIMARY KEY (journal_no, line_no));
CREATE TABLE erp_log (seq INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
  tool TEXT NOT NULL, action TEXT NOT NULL, doc_type TEXT NOT NULL, doc_id TEXT NOT NULL,
  before_json TEXT, after_json TEXT NOT NULL, reason TEXT, prev_hash TEXT NOT NULL UNIQUE, hash TEXT NOT NULL);
-- [A] guard: repeat for journals, journal_lines, erp_log (and audit.db audit_trail, register_rows, sample_runs; pbc.db submissions)
CREATE TRIGGER erp_log_no_update BEFORE UPDATE ON erp_log BEGIN SELECT RAISE(ABORT, 'append-only: erp_log'); END;
CREATE TRIGGER erp_log_no_delete BEFORE DELETE ON erp_log BEGIN SELECT RAISE(ABORT, 'append-only: erp_log'); END;
-- [F] guard: header identity columns of financial docs never change (status/cancelled_on may, via cancel_document)
CREATE TRIGGER invoices_f BEFORE UPDATE OF invoice_no, series, supplier_gstin, invoice_date, party_id, so_id, buyer_gstin, place_of_supply, irn, round_off_paise ON invoices
BEGIN SELECT RAISE(ABORT, 'financial document: use cancel_document or issue_credit_note'); END;
CREATE TRIGGER invoices_no_delete BEFORE DELETE ON invoices BEGIN SELECT RAISE(ABORT, 'financial document: never deleted'); END;
```
Triggers are **guards, not proof**: someone holding the file can `DROP TRIGGER` or use `INSERT OR REPLACE`. Proof comes from `erp_log` plus the anchors (§6).

## 3. ext.db: independent third parties (read-only for every role)

| # | Table | Tier | Key columns |
|---|---|---|---|
| 21 | `einvoices` | T1 | irn PK (= sha256(supplier_gstin + fy + doc_type + doc_no), hex), ack_no, ack_at, supplier_gstin, buyer_gstin?, doc_type `INV\|CRN\|DBN`, doc_no, doc_date, taxable_paise, tax_paise, total_paise, signature (HMAC-SHA256 of the canonical payload with `PORTAL_SECRET`: our stand-in for the IRP-signed QR), status `ACT\|CNL`, cancelled_at? |
| 22 | `ewaybills` | T1 | ewb_no PK (12 digits), generated_at, valid_upto, supplier_gstin, doc_type, doc_no, doc_date, to_gstin?, from_pincode, to_pincode, distance_km, value_paise (**incl. tax**), hsn, vehicle_no, transport_doc_no?, reason `SUPPLY\|JOB_WORK\|SKD\|LINE_SALES\|OWN_USE\|EXHIBITION\|RETURN\|OTHERS`, status `ACT\|CNL`, cancelled_at? |
| 23 | `gstr1_docs` | T1 | gstin, period `YYYYMM`, section `B2B\|B2CL\|B2CS\|CDNR\|EXP`, doc_no?, doc_date?, buyer_gstin?, pos, taxable_paise, igst/cgst/sgst_paise, filed_at |
| 24 | `gstr3b` | T2 | gstin, period, outward_taxable_paise, igst/cgst/sgst_paise, filed_at · PK(gstin, period) |
| 25 | `bank_txns` | T1 | id PK, account_no (the client's), value_date, amount_paise (signed), cp_name, cp_account, cp_ifsc, utr, narration |
| 26 | `mca_appointments` | T2 | cin, company_name, din, person_name, person_pan?, designation, appointed_on, ceased_on? (independent director registry; seeded only) |

Portal rules (in `portal.py`):
- An IRN can be cancelled only within 24 h of `ack_at`, and an EWB within 24 h of `generated_at`; after that the portal refuses.
- An EWB is valid for 1 day per 200 km (normal cargo).
- Portal timestamps (`ack_at`, `generated_at`) come from the server clock, never from tool arguments.

## 4. pbc.db: the client ↔ auditor channel

| # | Table | Flags | Key columns |
|---|---|---|---|
| 27 | `evidence_requests` | T1 | id PK, engagement_id, sample_ref (opaque `S-014`, **no reasons/strata**), doc_kind `INVOICE\|EWAY_BILL\|LR\|POD\|CREDIT_NOTE\|RETURN_PROOF\|CONTRACT\|OTHER`, about_doc_no, requested_at, due_on, status `OPEN\|RECEIVED\|OVERDUE\|WAIVED` |
| 28 | `submissions` | A T1 | id PK, engagement_id?, kind `SALES_REGISTER\|RP_LIST\|EVIDENCE`, request_id?, filename, mime, size, sha256 (**server-computed**), stored_path (`evidence/<sha256>`, content-addressed, never overwritten), declared_json? (the client's own claims, stored as claims), submitted_by, submitted_at |
| 29 | `exports` | T1 | id PK, kind `SALES_REGISTER`, fy_start, sha256, stored_path, created_by, created_at (used by `upload_sales_register(base_export_id=…, edits=…)`) |

## 5. audit.db: the auditor's file (no client handle ever)

| # | Table | Flags | Key columns |
|---|---|---|---|
| 30 | `engagements` | T1 | id PK, entity_name, framework `IND_AS\|AS`, period_start, period_end (**drives every date default**), run_date?, materiality_paise, performance_materiality_paise, trivial_paise, register_submission_id?, rp_submission_id?, register_map_json, status `DRAFT\|TESTING\|READY_FOR_REVIEW\|SIGNED_OFF`, testing_started_at?, testing_started_seq?, signed_by?, signed_at?, signoff_hash? |
| 31 | `register_rows` | A T1 | engagement_id, submission_id, row_no, cells_json (**verbatim**: every cell's raw value + number_format, original column order), mapped_json (normalised fields used only for pairing) · PK(submission_id, row_no) |
| 32 | `rp_list_rows` | A T1 | engagement_id, submission_id, row_no, cells_json, mapped_json (name, pan?, gstin?, relation?, effective_from?, effective_to?) |
| 33 | `risk_hits` | T1 | id PK, engagement_id, analytics_run, detector `D0..D14`, code (e.g. `EWB_NOT_FOUND`), object_type, object_id, severity 1–5, impact_paise, reason (plain language, server-written, cites ids only), evidence_json, created_at |
| 34 | `findings` | T1 | id PK (`F-001`), engagement_id, detector, code, category, title, explanation, standards, doc_refs_json, evidence_json (register vs SoR vs ext values), taxable_impact_paise, tax_impact_paise, gross_impact_paise, affected_fy, confidence `HIGH\|MEDIUM\|LOW`, proposed_aje_json? (balanced COA lines; NULL for disclosure-only), status `PROPOSED\|CONFIRMED\|REJECTED\|MODIFIED`, prepared_by, prepared_at, decided_by?, decided_at?, decision_note? |
| 35 | `sample_runs` | A T1 | id PK, engagement_id, kind `SALES_TOD\|CUTOFF_TOD\|CN_TOD`, seed, size, params_json, as_of_seq, population_json, population_sha256, algo_version, run_by, run_at |
| 36 | `samples` | T1 | run_id, sample_no, doc_type, doc_id, register_row_no?, stratum `KEY\|HIGH_VALUE\|RP\|REPRESENTATIVE\|CUTOFF_BEFORE\|CUTOFF_AFTER\|CN_POST_PERIOD\|CN_LARGE\|ANALYTICS`, reason, risk_points, snapshot_seq, bundle_json, snapshot_hash, test_result_json?, tested_at?, tested_seq?, conclusion_proposed?, notes? · PK(run_id, sample_no). **No `is_stale` column: staleness is computed.** |
| 37 | `anchors` | T1 | id PK, engagement_id, label `UPLOAD\|TESTING_START\|TEST\|DELIVERABLES\|REVIEW\|SIGNOFF\|PERIODIC`, erp_seq, erp_hash, trail_seq, trail_hash, at |
| 38 | `events` | T1 | id PK, engagement_id?, kind `REGISTER_UPLOADED\|RP_LIST_UPLOADED\|SAMPLES_SELECTED\|EVIDENCE_RECEIVED\|STALE_DETECTED\|INTEGRITY_ALERT\|READY_FOR_REVIEW\|SIGNED_OFF`, payload_json, at, notified_at? (set when n8n acks) |
| 39 | `downloads` | T1 | key PK (random, one-time), path, sha256, roles_allowed, expires_at |
| 40 | `audit_trail` | H A T1 | seq PK, at, principal, role, transport `STDIO\|HTTP\|UI\|SYSTEM`, tool, args_json (evidence bytes replaced by their sha256; **tokens never logged**), outcome `OK\|DENIED\|ERROR`, result_sha256, erp_seq, erp_hash (**the anchor**: the erp_log head at that call), prev_hash UNIQUE, hash |
| 42 | `risk_snapshots` | A T1 | run_id, at, object_type `INVOICE\|CN\|PARTY\|COMPANY`, object_id, A, E, R, C (×1000 int), band `LOW\|REVIEW\|HIGH`, reasons_json · AuditGraph temporal risk history (`05 §19.6`), never overwritten |
| 41 | `llm_usage` | T2 | id, at, purpose, model, input_tokens, cached_tokens, output_tokens, usd_micros (CostMeter, see `10`) |

Identities are **not** a table. They live in `identities.json` (gitignored, generated by `python -m app.seed`). See `04 §1`.

## 6. Integrity primitives (Ibrahim; ~60 lines total)

`app/chain.py` is a port of ReliefNet `backend/app/ledger.py` (canonical-JSON SHA-256), used for `erp_log` and `audit_trail`:

```python
import hashlib, json
GENESIS = '0' * 64
def canon(d): return json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
def h(d): return hashlib.sha256(canon(d).encode()).hexdigest()

def append(conn, table, row):  # caller holds BEGIN IMMEDIATE; row = every column except seq/prev_hash/hash
    last = conn.execute(f'SELECT seq, hash FROM {table} ORDER BY seq DESC LIMIT 1').fetchone()
    row = {**row, 'seq': last[0] + 1 if last else 1, 'prev_hash': last[1] if last else GENESIS}
    row['hash'] = h(row)
    conn.execute(f'INSERT INTO {table} ({",".join(row)}) VALUES ({",".join("?" * len(row))})', list(row.values()))
    return row['seq'], row['hash']

def verify(conn, table, anchors=()):  # anchors: [(seq, hash)] stored in audit.db
    prev, by_seq = GENESIS, {}
    for r in conn.execute(f'SELECT * FROM {table} ORDER BY seq'):
        d = dict(r); stored = d.pop('hash')
        if d['prev_hash'] != prev or h(d) != stored:
            return {'valid': False, 'broken_at_seq': d['seq'], 'anchor_mismatch_at': None}
        prev = by_seq[d['seq']] = stored
    bad = next((s for s, hh in anchors if by_seq.get(s) != hh), None)
    return {'valid': bad is None, 'broken_at_seq': None, 'anchor_mismatch_at': bad}
```

Money boundary (`app/money.py`):
```python
from decimal import Decimal, ROUND_HALF_UP
def to_paise(s):  # '118000.50' -> 11800050. Rejects floats, negatives, >2 decimals. Never rounds client money.
    if not isinstance(s, str): raise ValueError('amount must be a string like "118000.50"')
    d = Decimal(s.replace(',', ''))
    if d < 0 or d != d.quantize(Decimal('0.01')): raise ValueError(f'bad amount {s!r}')
    return int(d * 100)
def tax_paise(taxable_paise, rate_bp):  # per line, half-up
    return int((Decimal(taxable_paise) * rate_bp / 10000).quantize(Decimal('1'), ROUND_HALF_UP))
```

Role-bound connections (`app/db.py`):
```python
import sqlite3
from pathlib import Path
CLIENT = {'sales', 'warehouse', 'accounts', 'client_admin'}
AUDIT = {'audit_staff', 'engagement_partner', 'system'}
RW = {'erp': CLIENT, 'pbc': AUDIT | CLIENT, 'audit': AUDIT}  # pbc: clients only INSERT submissions (service enforces)
def connect(db, role):
    if db == 'audit' and role not in AUDIT | {'orchestrator'}:
        raise PermissionError('PERMISSION_DENIED: client identities cannot open audit workpapers')
    rw = role in RW.get(db, set())          # ext.db: nobody but portal.py (role 'portal')
    if db == 'ext' and role == 'portal': rw = True
    uri = Path(DB_PATHS[db]).resolve().as_uri() + ('' if rw else '?mode=ro')  # as_uri() escapes the space in 'Auditing Tool'
    c = sqlite3.connect(uri, uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA recursive_triggers=ON')
    if not rw: c.execute('PRAGMA query_only=ON')
    return c
```

`erp.write_doc(conn, actor, role, tool, action, doc_type, doc_id, reason=None)`:
1. Call it **after** the tool has written its typed rows inside the transaction.
2. Read back the header plus its `*_lines` (lines sorted by line_no) and build `after_json = canon(...)`.
3. `before_json` = the previous `after_json` for this doc from `erp_log`.
4. Run `chain.append(conn, 'erp_log', …)`.

`amend_record` refuses [F] docs and names `cancel_document` / `issue_credit_note` in the error. `post_journal` rejects a voucher unless `SUM(dr) = SUM(cr) > 0`, every account exists, and every DEBTORS/CREDITORS line has a party.

`verify_integrity` runs five checks:
1. The `erp_log` chain, plus every anchor in `audit.anchors`.
2. For every [V]/[F] doc, the current rows equal its latest `after_json`. A mismatch is reported as **changed outside the application**.
3. Dr = Cr per journal.
4. The `audit_trail` chain.
5. Every trail row's (`erp_seq`, `erp_hash`) still matches `erp_log`.

Required tamper tests (`tests/test_tamper.py`):
- (a) A raw edit without rehash → `broken_at_seq = N`.
- (b) Edit + rehash of row N → broken at N+1.
- (c) A rewritten tail → chain valid **but** `anchor_mismatch_at` set.
- (d) A direct `UPDATE invoices` with triggers dropped → the out-of-band edit check fires.

## 7. Removed from the first draft (do not reintroduce)

- `ledger_entries` with free-text accounts.
- Every `NUMERIC(15,2)`.
- `parties.is_declared_rp` / `rp_effective_*`, because client claims don't belong on SoR rows (they live in `rp_list_rows`).
- `directors_and_relatives`, folded into `parties` + `party_links`.
- `invoices.dispatch_id`, replaced by `invoice_movements`.
- `invoices.accounting_entry_date` / `financial_year` / stored totals. The posting date is `journals.voucher_date`, and the FY is derived.
- `audit_samples.is_stale`.
- `audit_engagements.client_*_path` and `sampling_seed DEFAULT 42`.
- The `JSON` column type.
- Cross-file `REFERENCES`.
- A separate Ledger_DB or EventBus.
