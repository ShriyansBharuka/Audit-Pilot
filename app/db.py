"""Role-bound SQLite connections (03 §0, §6): independence is enforced by SQLite itself, not by if-statements.

An audit-role handle on erp.db / ext.db is opened mode=ro + query_only, so a buggy auditor tool physically cannot
write business data ("attempt to write a readonly database"). Client roles get no audit.db handle at all.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app import config

CLIENT = {"sales", "warehouse", "accounts", "client_admin"}
AUDIT = {"audit_staff", "engagement_partner", "system"}
ROLES = CLIENT | AUDIT | {"orchestrator", "portal"}
RW = {"erp": CLIENT, "pbc": AUDIT | CLIENT, "audit": AUDIT}   # pbc: clients only INSERT submissions (service enforces)
DB_PATHS = config.DB_PATHS                                    # same dict object: config.set_data_dir() updates it


def connect(db, role):
    """sqlite3.Connection for `db` ('erp'|'ext'|'pbc'|'audit') with exactly `role`'s rights. Autocommit mode:
    writes go through tx(). Raises PermissionError('PERMISSION_DENIED: ...') for a handle the role may not hold."""
    if db not in config.DBS:
        raise ValueError(f"INVALID_ARGUMENT: unknown database {db!r}; expected one of {', '.join(config.DBS)}")
    if role not in ROLES:
        raise PermissionError(f"PERMISSION_DENIED: unknown role {role!r}")
    if db == "audit" and role not in AUDIT | {"orchestrator"}:
        raise PermissionError("PERMISSION_DENIED: client identities cannot open audit workpapers")
    if db == "erp" and role == "orchestrator":       # 03 §0: n8n reads audit + pbc only, never the client's books
        raise PermissionError("PERMISSION_DENIED: the orchestrator has no handle on the client's system of record")
    rw = role in RW.get(db, set())                   # ext.db: nobody but portal.py (role 'portal')
    if db == "ext" and role == "portal":
        rw = True
    path = Path(DB_PATHS[db])
    if not path.exists():
        raise FileNotFoundError(f"PRECONDITION_FAILED: {db}.db does not exist. Run: python -m app.seed --reset")
    uri = path.resolve().as_uri() + ("?mode=rw" if rw else "?mode=ro")   # as_uri() escapes spaces in the path
    c = sqlite3.connect(uri, uri=True, timeout=10, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA recursive_triggers=ON")
    if rw:
        c.execute("PRAGMA synchronous=NORMAL")       # WAL + NORMAL: durable at checkpoints, fast enough for the seed
    else:
        c.execute("PRAGMA query_only=ON")
    return c


@contextmanager
def tx(conn):
    """One BEGIN IMMEDIATE transaction (03 §1). Nested use joins the outer transaction, which commits."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _raw(path):
    c = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_all(reset=False):
    """Create the 4 databases from schema/*.sql (idempotent), switch them to WAL, and bootstrap the COA through
    ledger.seed_coa (so the accounts get erp_log rows like every other [V] record). reset=True deletes them first."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for d in (config.EVIDENCE_DIR, config.AUDIT_FILES_DIR, config.EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    for name in config.DBS:
        path = Path(DB_PATHS[name])
        if reset:
            for p in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
                try:
                    p.unlink(missing_ok=True)
                except PermissionError as e:
                    raise PermissionError(f"PRECONDITION_FAILED: {p.name} is open in another process "
                                          f"(MCP server or UI?). Stop it and re-run the reset.") from e
        c = _raw(path)
        try:
            c.executescript((config.SCHEMA_DIR / f"{name}.sql").read_text(encoding="utf-8"))
            c.execute("PRAGMA journal_mode=WAL")
        finally:
            c.close()
    from app import ledger                           # IB-2 owns the COA; a no-op until it lands
    c = connect("erp", "client_admin")
    try:
        ledger.seed_coa(c)
    finally:
        c.close()
