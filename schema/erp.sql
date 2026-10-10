-- erp.db: the client's system of record (vault/03 §2). Applied by db.init_all; idempotent.
-- Money is *_paise INTEGER >= 0 (except invoices.round_off_paise, signed); rates in basis points; dates TEXT
-- 'YYYY-MM-DD'; timestamps ISO-8601 +05:30. Constraints enforce integrity, never business policy (03 §1).
-- Flags: [V] amend_record only, [F] cancel/credit note only, [A] append-only, [H] hash-chained.

-- 1 [V] parties. id 'SELF' is the audited company. pan null -> derive from gstin[2:12].
CREATE TABLE IF NOT EXISTS parties (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('ENTITY','PERSON')),
  tags TEXT NOT NULL DEFAULT '',                -- CSV of SELF,CUSTOMER,VENDOR,TRANSPORTER,DIRECTOR,KMP,RELATIVE
  name TEXT NOT NULL,
  pan TEXT, gstin TEXT, state_code TEXT,
  address TEXT NOT NULL DEFAULT '', pincode TEXT NOT NULL DEFAULT '',
  phone TEXT, email TEXT, bank_account TEXT, ifsc TEXT,
  recorded_by TEXT NOT NULL, recorded_at TEXT NOT NULL);

-- 2 [V] party_links: the RP truth, with dates
CREATE TABLE IF NOT EXISTS party_links (
  id TEXT PRIMARY KEY,
  from_party TEXT NOT NULL REFERENCES parties(id),
  to_party TEXT NOT NULL REFERENCES parties(id),
  relation TEXT NOT NULL CHECK (relation IN ('DIRECTOR_OF','KMP_OF','SHAREHOLDER_OF','RELATIVE_OF','CONTROLS','PARTNER_OF')),
  pct_bp INTEGER CHECK (pct_bp IS NULL OR pct_bp BETWEEN 0 AND 10000),
  effective_from TEXT NOT NULL, effective_to TEXT,
  source TEXT NOT NULL CHECK (source IN ('MBP-1','DIR-12','REGISTER','OTHER')));

-- 3 [V] items (charges are items too: CHG-PACKING, CHG-FREIGHT, CHG-INSURANCE). hsn '99...' = service
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, hsn TEXT NOT NULL, uom TEXT NOT NULL,
  gst_rate_bp INTEGER NOT NULL CHECK (gst_rate_bp >= 0),
  list_rate_paise INTEGER NOT NULL DEFAULT 0 CHECK (list_rate_paise >= 0),
  cost_paise INTEGER NOT NULL DEFAULT 0 CHECK (cost_paise >= 0));

-- 4 [V] schemes: the promotions that drive demand
CREATE TABLE IF NOT EXISTS schemes (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('TRADE_DISCOUNT','VOLUME_REBATE','CASH_DISCOUNT','FREE_QTY')),
  rate_bp INTEGER NOT NULL DEFAULT 0 CHECK (rate_bp >= 0), min_qty INTEGER,
  valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, announced_on TEXT NOT NULL, approved_by TEXT);

-- 5 [V] sales_orders: a lead is an SO in ENQUIRY (delivery terms / credit days come later, so nullable)
CREATE TABLE IF NOT EXISTS sales_orders (
  id TEXT PRIMARY KEY, so_no TEXT UNIQUE,
  party_id TEXT NOT NULL REFERENCES parties(id),
  status TEXT NOT NULL DEFAULT 'ENQUIRY' CHECK (status IN ('ENQUIRY','QUOTED','CONFIRMED','CLOSED','LOST')),
  enquired_on TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('EMAIL','PHONE','VISIT','PORTAL','SHOPIFY')),
  contact_name TEXT, contact_phone TEXT, contact_email TEXT,
  quoted_on TEXT, confirmed_on TEXT, customer_po_no TEXT,
  delivery_terms TEXT CHECK (delivery_terms IS NULL OR delivery_terms IN
    ('EX_WORKS','FOR_DISPATCH','FOR_DESTINATION','BILL_AND_HOLD','CONSIGNMENT')),
  credit_days INTEGER CHECK (credit_days IS NULL OR credit_days >= 0),
  scheme_id TEXT REFERENCES schemes(id),
  bill_and_hold_json TEXT);                    -- Ind AS 115 B81 checklist

-- 6 so_lines
CREATE TABLE IF NOT EXISTS so_lines (
  so_id TEXT NOT NULL REFERENCES sales_orders(id), line_no INTEGER NOT NULL,
  item_id TEXT NOT NULL REFERENCES items(id),
  qty INTEGER NOT NULL CHECK (qty >= 0), rate_paise INTEGER NOT NULL CHECK (rate_paise >= 0),
  discount_paise INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0),
  PRIMARY KEY (so_id, line_no));

-- 7 [V] movements (IN = sales return). A POD is an amend (record_delivery).
CREATE TABLE IF NOT EXISTS movements (
  id TEXT PRIMARY KEY,
  direction TEXT NOT NULL CHECK (direction IN ('OUT','IN')),
  party_id TEXT NOT NULL REFERENCES parties(id),
  so_id TEXT REFERENCES sales_orders(id),
  moved_on TEXT NOT NULL, from_pincode TEXT, to_pincode TEXT,
  transporter_id TEXT REFERENCES parties(id), vehicle_no TEXT, lr_no TEXT, lr_date TEXT, gate_pass_no TEXT,
  delivered_on TEXT, received_by TEXT);

-- 8 movement_lines
CREATE TABLE IF NOT EXISTS movement_lines (
  movement_id TEXT NOT NULL REFERENCES movements(id), item_id TEXT NOT NULL REFERENCES items(id),
  qty INTEGER NOT NULL CHECK (qty >= 0),
  PRIMARY KEY (movement_id, item_id));

-- 10 [F] invoices. No stored totals: always SUM the lines. Number system-assigned via doc_counters.
CREATE TABLE IF NOT EXISTS invoices (
  id TEXT PRIMARY KEY, invoice_no TEXT NOT NULL UNIQUE,
  series TEXT NOT NULL, supplier_gstin TEXT NOT NULL, invoice_date TEXT NOT NULL,
  party_id TEXT NOT NULL REFERENCES parties(id), so_id TEXT REFERENCES sales_orders(id),
  buyer_gstin TEXT, place_of_supply TEXT NOT NULL,
  irn TEXT,                                    -- as recorded by the client
  round_off_paise INTEGER NOT NULL DEFAULT 0,  -- signed, small
  status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED','CANCELLED')),
  cancelled_on TEXT);

-- 9 [V] invoice_movements: many-to-many; ewb_no is whatever the client typed (may be fake)
CREATE TABLE IF NOT EXISTS invoice_movements (
  invoice_id TEXT NOT NULL REFERENCES invoices(id), movement_id TEXT NOT NULL REFERENCES movements(id),
  ewb_no TEXT,
  PRIMARY KEY (invoice_id, movement_id));

-- 11 invoice_lines
CREATE TABLE IF NOT EXISTS invoice_lines (
  invoice_id TEXT NOT NULL REFERENCES invoices(id), line_no INTEGER NOT NULL,
  item_id TEXT NOT NULL REFERENCES items(id), hsn TEXT NOT NULL,
  qty INTEGER NOT NULL CHECK (qty >= 0), rate_paise INTEGER NOT NULL CHECK (rate_paise >= 0),
  discount_paise INTEGER NOT NULL DEFAULT 0 CHECK (discount_paise >= 0),
  scheme_id TEXT REFERENCES schemes(id),
  taxable_paise INTEGER NOT NULL CHECK (taxable_paise >= 0),
  gst_rate_bp INTEGER NOT NULL CHECK (gst_rate_bp >= 0),
  igst_paise INTEGER NOT NULL DEFAULT 0 CHECK (igst_paise >= 0),
  cgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (cgst_paise >= 0),
  sgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (sgst_paise >= 0),
  PRIMARY KEY (invoice_id, line_no));

-- 12 [F] credit_notes
CREATE TABLE IF NOT EXISTS credit_notes (
  id TEXT PRIMARY KEY, cn_no TEXT NOT NULL UNIQUE, cn_date TEXT NOT NULL,
  party_id TEXT NOT NULL REFERENCES parties(id),
  reason TEXT NOT NULL CHECK (reason IN ('SALES_RETURN','RATE_DIFF','SCHEME_REBATE','QUALITY','OTHER')),
  reason_text TEXT, scheme_id TEXT REFERENCES schemes(id),
  return_movement_id TEXT REFERENCES movements(id),
  irn TEXT,
  status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED','CANCELLED')));

-- 13 cn_lines. invoice_id is nullable on purpose: an unlinked CN is itself a flag (D9 UNLINKED_CN)
CREATE TABLE IF NOT EXISTS cn_lines (
  cn_id TEXT NOT NULL REFERENCES credit_notes(id), line_no INTEGER NOT NULL,
  invoice_id TEXT REFERENCES invoices(id), item_id TEXT REFERENCES items(id), qty INTEGER CHECK (qty IS NULL OR qty >= 0),
  taxable_paise INTEGER NOT NULL CHECK (taxable_paise >= 0),
  igst_paise INTEGER NOT NULL DEFAULT 0 CHECK (igst_paise >= 0),
  cgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (cgst_paise >= 0),
  sgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (sgst_paise >= 0),
  PRIMARY KEY (cn_id, line_no));

-- 14 [F] settlements: one row per (bank txn, document). bank_txn_id -> ext.bank_txns (no cross-file FK)
CREATE TABLE IF NOT EXISTS settlements (
  id TEXT PRIMARY KEY,
  direction TEXT NOT NULL CHECK (direction IN ('RECEIPT','PAYMENT')),
  settled_on TEXT NOT NULL, party_id TEXT NOT NULL REFERENCES parties(id),
  doc_type TEXT NOT NULL CHECK (doc_type IN ('INVOICE','PURCHASE','ADVANCE','OTHER')), doc_id TEXT,
  amount_paise INTEGER NOT NULL CHECK (amount_paise >= 0),
  bank_txn_id TEXT, mode TEXT);

-- 15 [F] purchase_bills (closes round-trip cycles for D10; purchase-to-pay for D15). po_id is nullable on purpose:
-- a bill with no purchase order is itself something to look at
CREATE TABLE IF NOT EXISTS purchase_bills (
  id TEXT PRIMARY KEY, vendor_id TEXT NOT NULL REFERENCES parties(id), bill_no TEXT NOT NULL, bill_date TEXT NOT NULL,
  item_id TEXT REFERENCES items(id), qty INTEGER CHECK (qty IS NULL OR qty >= 0),
  taxable_paise INTEGER NOT NULL CHECK (taxable_paise >= 0), tax_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_paise >= 0),
  po_id TEXT REFERENCES purchase_orders(id));

-- 43 [A] purchase_orders (vault/13 MT-1): what was ordered, at what price, on what payment terms
CREATE TABLE IF NOT EXISTS purchase_orders (
  id TEXT PRIMARY KEY, po_no TEXT NOT NULL UNIQUE, vendor_id TEXT NOT NULL REFERENCES parties(id), po_date TEXT NOT NULL,
  item_id TEXT NOT NULL REFERENCES items(id), qty INTEGER NOT NULL CHECK (qty > 0),
  rate_paise INTEGER NOT NULL CHECK (rate_paise >= 0),
  payment_terms TEXT NOT NULL DEFAULT 'CREDIT_30' CHECK (payment_terms IN ('ADVANCE','ON_DELIVERY','CREDIT_30','CREDIT_60')),
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','CANCELLED')));

-- 44 [A] goods_receipts: what physically arrived (GRN). A return to the vendor is a new row, kind RETURN, qty > 0
CREATE TABLE IF NOT EXISTS goods_receipts (
  id TEXT PRIMARY KEY, grn_no TEXT NOT NULL UNIQUE, po_id TEXT NOT NULL REFERENCES purchase_orders(id),
  received_on TEXT NOT NULL, item_id TEXT NOT NULL REFERENCES items(id), qty INTEGER NOT NULL CHECK (qty > 0),
  kind TEXT NOT NULL DEFAULT 'RECEIPT' CHECK (kind IN ('RECEIPT','RETURN')), received_by TEXT);

-- 16-19: key DDL copied exactly from 03 §2
CREATE TABLE IF NOT EXISTS accounts (code TEXT PRIMARY KEY, name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('ASSET','LIABILITY','EQUITY','INCOME','EXPENSE')),
  is_revenue INTEGER NOT NULL DEFAULT 0 CHECK (is_revenue IN (0,1)));
CREATE TABLE IF NOT EXISTS journals (no INTEGER PRIMARY KEY, voucher_date TEXT NOT NULL,
  voucher_type TEXT NOT NULL CHECK (voucher_type IN ('OPENING','SALES','CREDIT_NOTE','RECEIPT','PURCHASE','PAYMENT','JOURNAL','REVERSAL')),
  source_type TEXT, source_id TEXT, reverses_no INTEGER REFERENCES journals(no), aje_ref TEXT,
  narration TEXT NOT NULL, posted_by TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal_lines (journal_no INTEGER NOT NULL REFERENCES journals(no), line_no INTEGER NOT NULL,
  account_code TEXT NOT NULL REFERENCES accounts(code), party_id TEXT REFERENCES parties(id),
  dr_paise INTEGER NOT NULL DEFAULT 0 CHECK (dr_paise >= 0), cr_paise INTEGER NOT NULL DEFAULT 0 CHECK (cr_paise >= 0),
  CHECK ((dr_paise = 0) <> (cr_paise = 0)), PRIMARY KEY (journal_no, line_no));
CREATE TABLE IF NOT EXISTS erp_log (seq INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
  tool TEXT NOT NULL, action TEXT NOT NULL, doc_type TEXT NOT NULL, doc_id TEXT NOT NULL,
  before_json TEXT, after_json TEXT NOT NULL, reason TEXT, prev_hash TEXT NOT NULL UNIQUE, hash TEXT NOT NULL);

-- 20 doc_counters: one consecutive series per unit per FY (CGST Rule 46(b))
CREATE TABLE IF NOT EXISTS doc_counters (
  series TEXT NOT NULL, fy_start TEXT NOT NULL, next_no INTEGER NOT NULL DEFAULT 1 CHECK (next_no >= 1),
  PRIMARY KEY (series, fy_start));

-- indexes for the 100%-population detectors (D0-D14)
CREATE INDEX IF NOT EXISTS ix_parties_pan ON parties(pan);
CREATE INDEX IF NOT EXISTS ix_parties_gstin ON parties(gstin);
CREATE INDEX IF NOT EXISTS ix_links_to ON party_links(to_party);
CREATE INDEX IF NOT EXISTS ix_so_party ON sales_orders(party_id);
CREATE INDEX IF NOT EXISTS ix_mov_so ON movements(so_id);
CREATE INDEX IF NOT EXISTS ix_mov_vehicle ON movements(vehicle_no);
CREATE INDEX IF NOT EXISTS ix_invmov_mov ON invoice_movements(movement_id);
CREATE INDEX IF NOT EXISTS ix_inv_party ON invoices(party_id);
CREATE INDEX IF NOT EXISTS ix_inv_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS ix_cn_party ON credit_notes(party_id);
CREATE INDEX IF NOT EXISTS ix_cnl_inv ON cn_lines(invoice_id);
CREATE INDEX IF NOT EXISTS ix_settle_doc ON settlements(doc_type, doc_id);
CREATE INDEX IF NOT EXISTS ix_jrn_source ON journals(source_type, source_id);
CREATE INDEX IF NOT EXISTS ix_jl_account ON journal_lines(account_code);
CREATE INDEX IF NOT EXISTS ix_log_doc ON erp_log(doc_type, doc_id);
CREATE INDEX IF NOT EXISTS ix_po_vendor ON purchase_orders(vendor_id);
CREATE INDEX IF NOT EXISTS ix_grn_po ON goods_receipts(po_id);
CREATE INDEX IF NOT EXISTS ix_pb_po ON purchase_bills(po_id);

-- [A] guards (03 §2): journals, journal_lines, erp_log. Guards, not proof: proof is erp_log + anchors (03 §6).
CREATE TRIGGER IF NOT EXISTS erp_log_no_update BEFORE UPDATE ON erp_log BEGIN SELECT RAISE(ABORT, 'append-only: erp_log'); END;
CREATE TRIGGER IF NOT EXISTS erp_log_no_delete BEFORE DELETE ON erp_log BEGIN SELECT RAISE(ABORT, 'append-only: erp_log'); END;
CREATE TRIGGER IF NOT EXISTS journals_no_update BEFORE UPDATE ON journals BEGIN SELECT RAISE(ABORT, 'append-only: journals'); END;
CREATE TRIGGER IF NOT EXISTS journals_no_delete BEFORE DELETE ON journals BEGIN SELECT RAISE(ABORT, 'append-only: journals'); END;
CREATE TRIGGER IF NOT EXISTS journal_lines_no_update BEFORE UPDATE ON journal_lines BEGIN SELECT RAISE(ABORT, 'append-only: journal_lines'); END;
CREATE TRIGGER IF NOT EXISTS journal_lines_no_delete BEFORE DELETE ON journal_lines BEGIN SELECT RAISE(ABORT, 'append-only: journal_lines'); END;

-- [F] guards: identity columns of financial docs never change (status/cancelled_on may, via cancel_document)
CREATE TRIGGER IF NOT EXISTS invoices_f BEFORE UPDATE OF invoice_no, series, supplier_gstin, invoice_date, party_id, so_id, buyer_gstin, place_of_supply, irn, round_off_paise ON invoices
BEGIN SELECT RAISE(ABORT, 'financial document: use cancel_document or issue_credit_note'); END;
CREATE TRIGGER IF NOT EXISTS invoices_no_delete BEFORE DELETE ON invoices BEGIN SELECT RAISE(ABORT, 'financial document: never deleted'); END;
CREATE TRIGGER IF NOT EXISTS credit_notes_f BEFORE UPDATE OF cn_no, cn_date, party_id, reason, reason_text, scheme_id, return_movement_id, irn ON credit_notes
BEGIN SELECT RAISE(ABORT, 'financial document: use cancel_document'); END;
CREATE TRIGGER IF NOT EXISTS credit_notes_no_delete BEFORE DELETE ON credit_notes BEGIN SELECT RAISE(ABORT, 'financial document: never deleted'); END;
-- the lines of an [F] document are part of it
CREATE TRIGGER IF NOT EXISTS invoice_lines_f BEFORE UPDATE ON invoice_lines BEGIN SELECT RAISE(ABORT, 'financial document: use cancel_document or issue_credit_note'); END;
CREATE TRIGGER IF NOT EXISTS invoice_lines_no_delete BEFORE DELETE ON invoice_lines BEGIN SELECT RAISE(ABORT, 'financial document: never deleted'); END;
CREATE TRIGGER IF NOT EXISTS cn_lines_f BEFORE UPDATE ON cn_lines BEGIN SELECT RAISE(ABORT, 'financial document: use cancel_document'); END;
CREATE TRIGGER IF NOT EXISTS cn_lines_no_delete BEFORE DELETE ON cn_lines BEGIN SELECT RAISE(ABORT, 'financial document: never deleted'); END;
-- settlements and purchase bills have no status: never edited, never deleted (correct by reversal)
CREATE TRIGGER IF NOT EXISTS settlements_f BEFORE UPDATE ON settlements BEGIN SELECT RAISE(ABORT, 'financial document: post a reversal'); END;
CREATE TRIGGER IF NOT EXISTS settlements_no_delete BEFORE DELETE ON settlements BEGIN SELECT RAISE(ABORT, 'financial document: never deleted'); END;
CREATE TRIGGER IF NOT EXISTS purchase_bills_f BEFORE UPDATE ON purchase_bills BEGIN SELECT RAISE(ABORT, 'financial document: post a reversal'); END;
CREATE TRIGGER IF NOT EXISTS purchase_bills_no_delete BEFORE DELETE ON purchase_bills BEGIN SELECT RAISE(ABORT, 'financial document: never deleted'); END;
-- [A] purchase orders and goods receipts (MT-1): corrections are new rows (a RETURN receipt, a new PO), never edits
CREATE TRIGGER IF NOT EXISTS purchase_orders_no_update BEFORE UPDATE ON purchase_orders BEGIN SELECT RAISE(ABORT, 'append-only: purchase_orders'); END;
CREATE TRIGGER IF NOT EXISTS purchase_orders_no_delete BEFORE DELETE ON purchase_orders BEGIN SELECT RAISE(ABORT, 'append-only: purchase_orders'); END;
CREATE TRIGGER IF NOT EXISTS goods_receipts_no_update BEFORE UPDATE ON goods_receipts BEGIN SELECT RAISE(ABORT, 'append-only: goods_receipts'); END;
CREATE TRIGGER IF NOT EXISTS goods_receipts_no_delete BEFORE DELETE ON goods_receipts BEGIN SELECT RAISE(ABORT, 'append-only: goods_receipts'); END;
