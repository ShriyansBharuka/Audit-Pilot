-- pbc.db: the client <-> auditor channel (vault/03 §4). Requests are written by audit tools; submissions only
-- by intake.submit() (clients INSERT, never UPDATE; the service enforces it, the [A] trigger guards it).

-- 27 evidence_requests: sample_ref is opaque (S-014): no reasons or strata ever reach the client
CREATE TABLE IF NOT EXISTS evidence_requests (
  id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL, sample_ref TEXT NOT NULL,
  doc_kind TEXT NOT NULL CHECK (doc_kind IN ('INVOICE','EWAY_BILL','LR','POD','CREDIT_NOTE','RETURN_PROOF','CONTRACT','OTHER')),
  about_doc_no TEXT, requested_at TEXT NOT NULL, due_on TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RECEIVED','OVERDUE','WAIVED')));

-- 28 [A] submissions: stored byte-for-byte, content-addressed (evidence/<sha256>), sha256 server-computed;
-- declared_json holds the client's own claims, stored as claims
CREATE TABLE IF NOT EXISTS submissions (
  id TEXT PRIMARY KEY, engagement_id TEXT,
  kind TEXT NOT NULL CHECK (kind IN ('SALES_REGISTER','RP_LIST','EVIDENCE')),
  request_id TEXT REFERENCES evidence_requests(id),
  filename TEXT NOT NULL, mime TEXT, size INTEGER NOT NULL CHECK (size >= 0),
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64), stored_path TEXT NOT NULL,
  declared_json TEXT, submitted_by TEXT NOT NULL, submitted_at TEXT NOT NULL);

-- 29 exports: client register exports (upload_sales_register(base_export_id=..., edits=...))
CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'SALES_REGISTER' CHECK (kind IN ('SALES_REGISTER')),
  fy_start TEXT NOT NULL, sha256 TEXT NOT NULL, stored_path TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS ix_req_eng ON evidence_requests(engagement_id, status);
CREATE INDEX IF NOT EXISTS ix_sub_req ON submissions(request_id);
CREATE INDEX IF NOT EXISTS ix_sub_sha ON submissions(sha256);

CREATE TRIGGER IF NOT EXISTS submissions_no_update BEFORE UPDATE ON submissions BEGIN SELECT RAISE(ABORT, 'append-only: submissions'); END;
CREATE TRIGGER IF NOT EXISTS submissions_no_delete BEFORE DELETE ON submissions BEGIN SELECT RAISE(ABORT, 'append-only: submissions'); END;
