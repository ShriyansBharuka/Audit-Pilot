-- ext.db: independent third parties (vault/03 §3). Written only by portal.py (role 'portal') and the seeder;
-- read-only for every other role. Portal timestamps come from config.now(), never from tool arguments.

-- 21 einvoices: mock IRP. irn = sha256(supplier_gstin + fy + doc_type + doc_no) hex;
-- signature = HMAC-SHA256 of the canonical payload with PORTAL_SECRET (our stand-in for the signed QR)
CREATE TABLE IF NOT EXISTS einvoices (
  irn TEXT PRIMARY KEY, ack_no TEXT NOT NULL UNIQUE, ack_at TEXT NOT NULL,
  supplier_gstin TEXT NOT NULL, buyer_gstin TEXT,
  doc_type TEXT NOT NULL CHECK (doc_type IN ('INV','CRN','DBN')), doc_no TEXT NOT NULL, doc_date TEXT NOT NULL,
  taxable_paise INTEGER NOT NULL CHECK (taxable_paise >= 0),
  tax_paise INTEGER NOT NULL CHECK (tax_paise >= 0),
  total_paise INTEGER NOT NULL CHECK (total_paise >= 0),
  signature TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACT' CHECK (status IN ('ACT','CNL')), cancelled_at TEXT);

-- 22 ewaybills: valid 1 day per 200 km; cancellable within 24 h of generated_at
CREATE TABLE IF NOT EXISTS ewaybills (
  ewb_no TEXT PRIMARY KEY CHECK (length(ewb_no) = 12),
  generated_at TEXT NOT NULL, valid_upto TEXT NOT NULL,
  supplier_gstin TEXT NOT NULL, doc_type TEXT NOT NULL, doc_no TEXT NOT NULL, doc_date TEXT NOT NULL,
  to_gstin TEXT, from_pincode TEXT NOT NULL, to_pincode TEXT NOT NULL,
  distance_km INTEGER NOT NULL CHECK (distance_km >= 0),
  value_paise INTEGER NOT NULL CHECK (value_paise >= 0),      -- incl. tax
  hsn TEXT, vehicle_no TEXT, transport_doc_no TEXT,
  reason TEXT NOT NULL DEFAULT 'SUPPLY' CHECK (reason IN ('SUPPLY','JOB_WORK','SKD','LINE_SALES','OWN_USE','EXHIBITION','RETURN','OTHERS')),
  status TEXT NOT NULL DEFAULT 'ACT' CHECK (status IN ('ACT','CNL')), cancelled_at TEXT);

-- 23 gstr1_docs (matched to books by doc_no, not by month)
CREATE TABLE IF NOT EXISTS gstr1_docs (
  gstin TEXT NOT NULL, period TEXT NOT NULL CHECK (length(period) = 6),   -- YYYYMM
  section TEXT NOT NULL CHECK (section IN ('B2B','B2CL','B2CS','CDNR','EXP')),
  doc_no TEXT, doc_date TEXT, buyer_gstin TEXT, pos TEXT,
  taxable_paise INTEGER NOT NULL CHECK (taxable_paise >= 0),
  igst_paise INTEGER NOT NULL DEFAULT 0 CHECK (igst_paise >= 0),
  cgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (cgst_paise >= 0),
  sgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (sgst_paise >= 0),
  filed_at TEXT NOT NULL);

-- 24 gstr3b (T2)
CREATE TABLE IF NOT EXISTS gstr3b (
  gstin TEXT NOT NULL, period TEXT NOT NULL CHECK (length(period) = 6),
  outward_taxable_paise INTEGER NOT NULL CHECK (outward_taxable_paise >= 0),
  igst_paise INTEGER NOT NULL DEFAULT 0 CHECK (igst_paise >= 0),
  cgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (cgst_paise >= 0),
  sgst_paise INTEGER NOT NULL DEFAULT 0 CHECK (sgst_paise >= 0),
  filed_at TEXT NOT NULL,
  PRIMARY KEY (gstin, period));

-- 25 bank_txns: amount_paise is SIGNED (+ in, - out), the one exception to the >= 0 rule
CREATE TABLE IF NOT EXISTS bank_txns (
  id TEXT PRIMARY KEY, account_no TEXT NOT NULL, value_date TEXT NOT NULL,
  amount_paise INTEGER NOT NULL CHECK (amount_paise <> 0),
  cp_name TEXT, cp_account TEXT, cp_ifsc TEXT, utr TEXT, narration TEXT);

-- 26 mca_appointments (T2; independent director registry; seeded only)
CREATE TABLE IF NOT EXISTS mca_appointments (
  cin TEXT NOT NULL, company_name TEXT NOT NULL, din TEXT NOT NULL, person_name TEXT NOT NULL, person_pan TEXT,
  designation TEXT, appointed_on TEXT NOT NULL, ceased_on TEXT);

CREATE INDEX IF NOT EXISTS ix_einv_doc ON einvoices(supplier_gstin, doc_type, doc_no);
CREATE INDEX IF NOT EXISTS ix_ewb_doc ON ewaybills(supplier_gstin, doc_no);
CREATE INDEX IF NOT EXISTS ix_ewb_vehicle ON ewaybills(vehicle_no);
CREATE INDEX IF NOT EXISTS ix_gstr1_doc ON gstr1_docs(gstin, doc_no);
CREATE INDEX IF NOT EXISTS ix_gstr1_period ON gstr1_docs(gstin, period);
CREATE INDEX IF NOT EXISTS ix_bank_cp ON bank_txns(cp_account);
CREATE INDEX IF NOT EXISTS ix_mca_din ON mca_appointments(din);
