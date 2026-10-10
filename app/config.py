"""Paths, environment, clock, unit master and engagement defaults (07 §3). Imported by every module; imports none.

Time is Asia/Kolkata (03 §1). IST has no DST, so a fixed +05:30 offset is exact and needs no tzdata on Windows.
The clock is settable so the seeder (and replay) can record FY 2025-26 history on its business dates: every
recorded_at, erp_log.recorded_at, IRN ack_at and EWB generated_at must come from now(), never datetime.now().
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path=ROOT / ".env"):
    """KEY=VALUE lines from .env (never committed); real environment variables win."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.split(" #", 1)[0].strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()
env = os.environ.get

# ---------------------------------------------------------------- time

TZ = "Asia/Kolkata"
IST = timezone(timedelta(hours=5, minutes=30), "IST")
_clock = None                                   # ISO timestamp string when set, else the wall clock


def set_clock(iso_ts=None):
    """Freeze now() at an ISO timestamp ('2025-04-03T11:20:00+05:30'), or None for the wall clock."""
    global _clock
    if iso_ts is not None:
        datetime.fromisoformat(iso_ts)          # fail fast on a malformed timestamp
    _clock = iso_ts


def now():
    """Server time as ISO-8601 with +05:30, second precision."""
    if _clock is not None:
        return datetime.fromisoformat(_clock).astimezone(IST).isoformat(timespec="seconds")
    return datetime.now(IST).isoformat(timespec="seconds")


def today():
    return now()[:10]

# ---------------------------------------------------------------- paths

DATA_DIR = Path(env("DATA_DIR", str(ROOT / "data")))
DBS = ("erp", "ext", "pbc", "audit")
DB_PATHS = {}
EVIDENCE_DIR = AUDIT_FILES_DIR = EXPORTS_DIR = None
SCHEMA_DIR = ROOT / "schema"
IDENTITIES = Path(env("IDENTITIES", str(ROOT / "identities.json")))


def set_data_dir(path):
    """Point every database and file store at `path` (selftest and tests use a temp dir). db.py reads DB_PATHS
    at call time, so this takes effect immediately."""
    global DATA_DIR, EVIDENCE_DIR, AUDIT_FILES_DIR, EXPORTS_DIR
    DATA_DIR = Path(path)
    DB_PATHS.clear()
    DB_PATHS.update({d: DATA_DIR / f"{d}.db" for d in DBS})
    EVIDENCE_DIR = DATA_DIR / "evidence"            # content-addressed client submissions (pbc.submissions)
    AUDIT_FILES_DIR = DATA_DIR / "audit_files"      # workpaper, memo, trail export
    EXPORTS_DIR = DATA_DIR / "exports"              # client register exports (pbc.exports)


set_data_dir(DATA_DIR)

# ---------------------------------------------------------------- server / integrations (07 §2, 10)

PORT = int(env("PORT", "8000"))
PUBLIC_HOST = env("PUBLIC_HOST", "localhost")
PUBLIC_URL = env("PUBLIC_URL", f"http://localhost:{PORT}/mcp")
PIPELINE_MODE = env("PIPELINE_MODE", "inline")
PORTAL_SECRET = env("PORTAL_SECRET", "change-me")
N8N_WEBHOOK_URL = env("N8N_WEBHOOK_URL", "")
N8N_SECRET = env("N8N_SECRET", "change-me")
LLM_ENABLED = env("LLM_ENABLED", "0") == "1"
LLM_RUN_CAP_USD = env("LLM_RUN_CAP_USD", "3")      # strings; CostMeter converts to micros
LLM_DAY_CAP_USD = env("LLM_DAY_CAP_USD", "40")

# ---------------------------------------------------------------- the audited company (fictional)

ENTITY_NAME = "Konkan Marine Controls Ltd"
SELF_PAN = "AAKCK4821M"
# Unit master: one invoice/CN series per unit per FY (CGST Rule 46(b)); issue_invoice takes supplier_gstin from here.
# Same values as seed.UNITS (DA-1a); the seed should import these instead of keeping its own copy.
UNITS = {
    "G2": {"name": "Ratnagiri works", "state_code": "27", "gstin": "27AAKCK4821M1Z4",
           "address": "Plot B-21, MIDC Mirjole, Ratnagiri", "pincode": "415639", "vehicle_rto": "MH08"},
    "G11": {"name": "Verna works", "state_code": "30", "gstin": "30AAKCK4821M1ZH",
            "address": "Plot L-54, Verna Industrial Estate, Salcete", "pincode": "403722", "vehicle_rto": "GA08"},
}

# ---------------------------------------------------------------- engagement defaults (audit.engagements)

FRAMEWORK = "IND_AS"
PERIOD_START = "2025-04-01"
PERIOD_END = "2026-03-31"                       # drives every date default (04 §3.5); configure_engagement overrides
FY_LABEL = "2025-26"
# Materiality (SA 320) as basis points; findings.py applies them (AA-3). The auditor can override.
OVERALL_MATERIALITY_BP_OF_REVENUE = 50          # OM = 0.5% of revenue
PERFORMANCE_MATERIALITY_BP_OF_OM = 7500         # PM = 75% of OM
TRIVIAL_BP_OF_OM = 500                          # clearly trivial = 5% of OM
SALES_TOD_SIZE = {"LOW": 25, "MODERATE": 30, "HIGH": 35}   # 05 §19.7: company band sizes the Sales TOD
EWB_THRESHOLD_PAISE = 50_000_00                 # CGST Rule 138: consignment value incl. tax
AATO_EINVOICE = True                            # AATO > Rs 5 cr: e-invoicing applies (D6 IRN_MISSING)
AATO_30_DAY_IRN = True                          # AATO >= Rs 10 cr: IRN within 30 days (D13 IRN_LATE)

# ---------------------------------------------------------------- AuditGraph (05 §19.2)

# Engine A weight per risk_hits code; anything not listed weighs 1.0. FORMAT_ONLY is a formatting difference;
# the D5 concentration codes are heuristics that only become findings when D3/D4/D9 corroborate them (05 D5).
RISK_WEIGHTS = {
    "FORMAT_ONLY": 0.2,
    "END_WINDOW_SHARE": 0.5, "DISCOUNT_SPIKE": 0.5, "SCHEME_WINDOW": 0.5, "NEW_CUSTOMER_AT_YEAR_END": 0.5,
    "BENFORD_FIRST_DIGIT": 0.5, "ACTIVITY_BURST": 0.5,
}


def risk_weight(code):
    return RISK_WEIGHTS.get(code, 1.0)


RISK_BANDS = ((60, "HIGH"), (30, "REVIEW"), (0, "LOW"))     # R on 0-100 (05 §19.5)
