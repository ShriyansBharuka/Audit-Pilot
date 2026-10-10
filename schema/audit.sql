-- audit.db: the auditor's file (vault/03 §5). Client roles have NO handle at all (db.connect refuses);
-- orchestrator (n8n) reads it only. AJEs live here as proposals and are never posted by the auditor.

-- 30 engagements: period_end drives every date default (04 §3.5)
CREATE TABLE IF NOT EXISTS engagements (
  id TEXT PRIMARY KEY, entity_name TEXT NOT NULL,
  framework TEXT NOT NULL DEFAULT 'IND_AS' CHECK (framework IN ('IND_AS','AS')),
  period_start TEXT NOT NULL, period_end TEXT NOT NULL, run_date TEXT,
  materiality_paise INTEGER CHECK (materiality_paise IS NULL OR materiality_paise >= 0),
  performance_materiality_paise INTEGER CHECK (performance_materiality_paise IS NULL OR performance_materiality_paise >= 0),
  trivial_paise INTEGER CHECK (trivial_paise IS NULL OR trivial_paise >= 0),
  register_submission_id TEXT, rp_submission_id TEXT, register_map_json TEXT,
  status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','TESTING','READY_FOR_REVIEW','SIGNED_OFF')),
  testing_started_at TEXT, testing_started_seq INTEGER,
  signed_by TEXT, signed_at TEXT, signoff_hash TEXT);

-- 31 [A] register_rows: cells_json is verbatim (every cell's raw value + number_format, original column order);
-- mapped_json holds normalised fields used only for pairing (register.map_row)
CREATE TABLE IF NOT EXISTS register_rows (
  engagement_id TEXT NOT NULL, submission_id TEXT NOT NULL, row_no INTEGER NOT NULL,
  cells_json TEXT NOT NULL, mapped_json TEXT,
  PRIMARY KEY (submission_id, row_no));

-- 32 [A] rp_list_rows (mapped_json: name, pan?, gstin?, relation?, effective_from?, effective_to?)
CREATE TABLE IF NOT EXISTS rp_list_rows (
  engagement_id TEXT NOT NULL, submission_id TEXT NOT NULL, row_no INTEGER NOT NULL,
  cells_json TEXT NOT NULL, mapped_json TEXT,
  PRIMARY KEY (submission_id, row_no));

-- 33 risk_hits: reason is plain language, server-written, cites ids only
CREATE TABLE IF NOT EXISTS risk_hits (
  id INTEGER PRIMARY KEY, engagement_id TEXT NOT NULL, analytics_run TEXT NOT NULL,
  detector TEXT NOT NULL CHECK (detector GLOB 'D[0-9]*'), code TEXT NOT NULL,
  object_type TEXT NOT NULL, object_id TEXT NOT NULL,
  severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
  impact_paise INTEGER NOT NULL DEFAULT 0 CHECK (impact_paise >= 0),
  reason TEXT NOT NULL, evidence_json TEXT, created_at TEXT NOT NULL);

-- 34 findings: proposed_aje_json = balanced COA lines, NULL for disclosure-only; only the partner (UI) decides
CREATE TABLE IF NOT EXISTS findings (
  id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL, detector TEXT, code TEXT, category TEXT NOT NULL,
  title TEXT NOT NULL, explanation TEXT NOT NULL, standards TEXT, doc_refs_json TEXT, evidence_json TEXT,
  taxable_impact_paise INTEGER NOT NULL DEFAULT 0 CHECK (taxable_impact_paise >= 0),
  tax_impact_paise INTEGER NOT NULL DEFAULT 0 CHECK (tax_impact_paise >= 0),
  gross_impact_paise INTEGER NOT NULL DEFAULT 0 CHECK (gross_impact_paise >= 0),
  affected_fy TEXT,
  confidence TEXT NOT NULL CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
  proposed_aje_json TEXT,
  status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED','CONFIRMED','REJECTED','MODIFIED')),
  prepared_by TEXT NOT NULL, prepared_at TEXT NOT NULL,
  decided_by TEXT, decided_at TEXT, decision_note TEXT);

-- 35 [A] sample_runs: seed is TEXT because secrets.randbits(64) can exceed SQLite's signed 64-bit INTEGER
CREATE TABLE IF NOT EXISTS sample_runs (
  id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('SALES_TOD','CUTOFF_TOD','CN_TOD')),
  seed TEXT NOT NULL, size INTEGER NOT NULL, params_json TEXT, as_of_seq INTEGER NOT NULL,
  population_json TEXT NOT NULL, population_sha256 TEXT NOT NULL, algo_version TEXT NOT NULL,
  run_by TEXT NOT NULL, run_at TEXT NOT NULL);

-- 36 samples: no is_stale column; staleness is computed (05 D11)
CREATE TABLE IF NOT EXISTS samples (
  run_id TEXT NOT NULL REFERENCES sample_runs(id), sample_no INTEGER NOT NULL,
  doc_type TEXT NOT NULL, doc_id TEXT NOT NULL, register_row_no INTEGER,
  stratum TEXT NOT NULL CHECK (stratum IN ('KEY','HIGH_VALUE','RP','REPRESENTATIVE','CUTOFF_BEFORE','CUTOFF_AFTER',
                                           'CN_POST_PERIOD','CN_LARGE','ANALYTICS')),
  reason TEXT NOT NULL, risk_points INTEGER NOT NULL DEFAULT 0,
  snapshot_seq INTEGER NOT NULL, bundle_json TEXT, snapshot_hash TEXT,
  test_result_json TEXT, tested_at TEXT, tested_seq INTEGER, conclusion_proposed TEXT, notes TEXT,
  PRIMARY KEY (run_id, sample_no));

-- 37 anchors: the auditor's copies of the erp_log / audit_trail heads
CREATE TABLE IF NOT EXISTS anchors (
  id INTEGER PRIMARY KEY, engagement_id TEXT NOT NULL,
  label TEXT NOT NULL CHECK (label IN ('UPLOAD','TESTING_START','TEST','DELIVERABLES','REVIEW','SIGNOFF','PERIODIC')),
  erp_seq INTEGER, erp_hash TEXT, trail_seq INTEGER, trail_hash TEXT, at TEXT NOT NULL);

-- 38 events (-> n8n via notify.emit)
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, engagement_id TEXT,
  kind TEXT NOT NULL CHECK (kind IN ('REGISTER_UPLOADED','RP_LIST_UPLOADED','SAMPLES_SELECTED','EVIDENCE_RECEIVED',
                                     'STALE_DETECTED','INTEGRITY_ALERT','READY_FOR_REVIEW','SIGNED_OFF',
                                     'RISK_ESCALATED')),           -- RISK_ESCALATED: AuditGraph crossing into High (05 §19.6)
  payload_json TEXT, at TEXT NOT NULL, notified_at TEXT);

-- 39 downloads: one-time /files/<key> URLs, never server paths
CREATE TABLE IF NOT EXISTS downloads (
  key TEXT PRIMARY KEY, path TEXT NOT NULL, sha256 TEXT NOT NULL, roles_allowed TEXT NOT NULL, expires_at TEXT NOT NULL);

-- 40 [H][A] audit_trail: every agent/tool action incl. denials; tokens never logged.
-- (erp_seq, erp_hash) is the anchor: the erp_log head at that call. CONNECTOR = the Shopify route (10 §2).
CREATE TABLE IF NOT EXISTS audit_trail (
  seq INTEGER PRIMARY KEY, at TEXT NOT NULL, principal TEXT NOT NULL, role TEXT NOT NULL,
  transport TEXT NOT NULL CHECK (transport IN ('STDIO','HTTP','UI','SYSTEM','CONNECTOR')),
  tool TEXT NOT NULL, args_json TEXT,
  outcome TEXT NOT NULL CHECK (outcome IN ('OK','DENIED','ERROR')),
  result_sha256 TEXT, erp_seq INTEGER, erp_hash TEXT,
  prev_hash TEXT NOT NULL UNIQUE, hash TEXT NOT NULL);

-- 41 llm_usage (T2; CostMeter, 10 §4)
CREATE TABLE IF NOT EXISTS llm_usage (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, purpose TEXT, model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0, cached_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0, usd_micros INTEGER NOT NULL DEFAULT 0);

-- 42 [A] risk_snapshots: AuditGraph temporal risk history (05 §19.6), never overwritten. A/E/R/C x1000 integers.
-- band MODERATE is the company band (05 §19.7); entries use LOW/REVIEW/HIGH.
CREATE TABLE IF NOT EXISTS risk_snapshots (
  run_id TEXT NOT NULL, at TEXT NOT NULL,
  object_type TEXT NOT NULL CHECK (object_type IN ('INVOICE','CN','PARTY','COMPANY')), object_id TEXT NOT NULL,
  A INTEGER, E INTEGER, R INTEGER, C INTEGER,
  band TEXT NOT NULL CHECK (band IN ('LOW','REVIEW','MODERATE','HIGH')),
  reasons_json TEXT,
  PRIMARY KEY (run_id, object_type, object_id));

-- 45 [A] cases (vault/13 MT-4): one per root object (invoice / PO / settlement / party / ...) of severity >= 4 hits.
-- Rebuilt idempotently after every analytics run: numbers and hits refresh, id and status are kept; a case whose
-- serious hits are gone is kept with active = 0. Status changes only with a case_events row. confidence x1000.
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL,
  root_type TEXT NOT NULL, root_id TEXT NOT NULL, title TEXT NOT NULL, counterparty_id TEXT,
  codes_json TEXT NOT NULL, hit_ids_json TEXT NOT NULL, top_severity INTEGER NOT NULL,
  recorded_paise INTEGER NOT NULL DEFAULT 0 CHECK (recorded_paise >= 0),
  verified_paise INTEGER NOT NULL DEFAULT 0 CHECK (verified_paise >= 0),
  received_paise INTEGER,
  affected_paise INTEGER NOT NULL DEFAULT 0 CHECK (affected_paise >= 0),
  risk_score INTEGER NOT NULL DEFAULT 0, confidence INTEGER NOT NULL DEFAULT 0,
  band TEXT NOT NULL DEFAULT 'LOW' CHECK (band IN ('LOW','REVIEW','HIGH')),
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','EXPLAINED','EVIDENCE_REQUESTED','ESCALATED','ADJUSTMENT_PROPOSED')),
  active INTEGER NOT NULL DEFAULT 1, opened_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE (engagement_id, root_type, root_id));

-- 46 [A] case_events: the case history (append-only). action OPENED / EXPLAINED / REQUEST_EVIDENCE / ESCALATE /
-- PROPOSE_ADJUSTMENT / AI_INVESTIGATION (PROPOSED output of the investigator, never a decision)
CREATE TABLE IF NOT EXISTS case_events (
  id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), at TEXT NOT NULL, by TEXT NOT NULL, role TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('OPENED','EXPLAINED','REQUEST_EVIDENCE','ESCALATE','PROPOSE_ADJUSTMENT','AI_INVESTIGATION')),
  note TEXT, payload_json TEXT);

CREATE INDEX IF NOT EXISTS ix_hits_eng ON risk_hits(engagement_id, detector, code);
CREATE INDEX IF NOT EXISTS ix_hits_obj ON risk_hits(object_type, object_id);
CREATE INDEX IF NOT EXISTS ix_find_eng ON findings(engagement_id, status);
CREATE INDEX IF NOT EXISTS ix_runs_eng ON sample_runs(engagement_id);
CREATE INDEX IF NOT EXISTS ix_samples_doc ON samples(doc_type, doc_id);
CREATE INDEX IF NOT EXISTS ix_anchors_eng ON anchors(engagement_id, label);
CREATE INDEX IF NOT EXISTS ix_events_eng ON events(engagement_id, kind);
CREATE INDEX IF NOT EXISTS ix_snap_obj ON risk_snapshots(object_type, object_id, at);
CREATE INDEX IF NOT EXISTS ix_case_eng ON cases(engagement_id, status);
CREATE INDEX IF NOT EXISTS ix_case_ev ON case_events(case_id, id);

-- [A] guards: register_rows, rp_list_rows, sample_runs, audit_trail, risk_snapshots
CREATE TRIGGER IF NOT EXISTS register_rows_no_update BEFORE UPDATE ON register_rows BEGIN SELECT RAISE(ABORT, 'append-only: register_rows'); END;
CREATE TRIGGER IF NOT EXISTS register_rows_no_delete BEFORE DELETE ON register_rows BEGIN SELECT RAISE(ABORT, 'append-only: register_rows'); END;
CREATE TRIGGER IF NOT EXISTS rp_list_rows_no_update BEFORE UPDATE ON rp_list_rows BEGIN SELECT RAISE(ABORT, 'append-only: rp_list_rows'); END;
CREATE TRIGGER IF NOT EXISTS rp_list_rows_no_delete BEFORE DELETE ON rp_list_rows BEGIN SELECT RAISE(ABORT, 'append-only: rp_list_rows'); END;
CREATE TRIGGER IF NOT EXISTS sample_runs_no_update BEFORE UPDATE ON sample_runs BEGIN SELECT RAISE(ABORT, 'append-only: sample_runs'); END;
CREATE TRIGGER IF NOT EXISTS sample_runs_no_delete BEFORE DELETE ON sample_runs BEGIN SELECT RAISE(ABORT, 'append-only: sample_runs'); END;
CREATE TRIGGER IF NOT EXISTS audit_trail_no_update BEFORE UPDATE ON audit_trail BEGIN SELECT RAISE(ABORT, 'append-only: audit_trail'); END;
CREATE TRIGGER IF NOT EXISTS audit_trail_no_delete BEFORE DELETE ON audit_trail BEGIN SELECT RAISE(ABORT, 'append-only: audit_trail'); END;
CREATE TRIGGER IF NOT EXISTS risk_snapshots_no_update BEFORE UPDATE ON risk_snapshots BEGIN SELECT RAISE(ABORT, 'append-only: risk_snapshots'); END;
CREATE TRIGGER IF NOT EXISTS risk_snapshots_no_delete BEFORE DELETE ON risk_snapshots BEGIN SELECT RAISE(ABORT, 'append-only: risk_snapshots'); END;
CREATE TRIGGER IF NOT EXISTS case_events_no_update BEFORE UPDATE ON case_events BEGIN SELECT RAISE(ABORT, 'append-only: case_events'); END;
CREATE TRIGGER IF NOT EXISTS case_events_no_delete BEFORE DELETE ON case_events BEGIN SELECT RAISE(ABORT, 'append-only: case_events'); END;
CREATE TRIGGER IF NOT EXISTS cases_no_delete BEFORE DELETE ON cases BEGIN SELECT RAISE(ABORT, 'cases are never deleted (active = 0)'); END;

-- after sign-off the engagement's findings and samples are frozen; later work is an addendum (06 §9.4, SA 230)
CREATE TRIGGER IF NOT EXISTS findings_signed_off BEFORE UPDATE ON findings
WHEN (SELECT status FROM engagements WHERE id = OLD.engagement_id) = 'SIGNED_OFF'
BEGIN SELECT RAISE(ABORT, 'engagement signed off: record an addendum'); END;
CREATE TRIGGER IF NOT EXISTS samples_signed_off BEFORE UPDATE ON samples
WHEN (SELECT e.status FROM engagements e JOIN sample_runs r ON r.engagement_id = e.id WHERE r.id = OLD.run_id) = 'SIGNED_OFF'
BEGIN SELECT RAISE(ABORT, 'engagement signed off: record an addendum'); END;
