"""Organisations as tenants (EX-4, vault/03 §0a, 07 §3a): one data directory per audited company.

The ERP schema is single-company on purpose (no org_id columns). A tenant is a directory with its own four databases
and its own engagement: the default tenant is DATA_DIR (Konkan Marine Controls Ltd); others live in
DATA_DIR/tenants/<slug>/ with a tenant.json. scope(slug) activates one for a block (config ContextVar), so concurrent
requests stay isolated. Access: the default tenant is visible to every identity; another tenant only to the principals
listed in its tenant.json. Picking a tenant never grants a role: the role always comes from the token.

    python -m app.tenants --seed-demo          # tenant 2: Sahyadri Shipyards Enterprises, 300 invoices
    python -m app.tenants --list
"""
import argparse
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from app import config

DEFAULT = "konkan"
_PAN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_FY = re.compile(r"(\d{4})-(\d{2})")
DEMO = {"name": "Sahyadri Shipyards Enterprises", "pan": "AAFCS6120R", "fy": "2025-26", "invoices": 300, "seed": 11}


def _root():
    return Path(config._BASE["DATA_DIR"]) / "tenants"


def _default():
    return {"slug": DEFAULT, "name": config._BASE["ENTITY_NAME"], "pan": config.SELF_PAN,
            "gstin": config.UNITS["G2"]["gstin"], "fy_label": config._BASE["FY_LABEL"],
            "period_start": config._BASE["PERIOD_START"], "period_end": config._BASE["PERIOD_END"],
            "engagement_id": config._BASE["ENGAGEMENT_ID"], "default": True, "principals": "*"}


def registry():
    """Every tenant: the default first, then DATA_DIR/tenants/*/tenant.json by slug."""
    out = [_default()]
    root = _root()
    if root.exists():
        for f in sorted(root.glob("*/tenant.json")):
            t = json.loads(f.read_text(encoding="utf-8"))
            t["default"] = False
            out.append(t)
    return out


def get(slug):
    t = next((t for t in registry() if t["slug"] == slug), None)
    if t is None:
        raise LookupError(f"NOT_FOUND: no organisation '{slug}'. GET /api/tenants lists the ones you can see")
    return t


def current():
    """The tenant this context runs against (identified by its data directory, which is unique; two organisations may
    share an engagement-id stem), the default when none is active."""
    active = config.active_tenant()
    if active:
        d = Path(active["DATA_DIR"]).resolve()
        for t in registry():
            if not t["default"] and (_root() / t["slug"]).resolve() == d:
                return t
    return get(DEFAULT)


def allowed(principal, slug):
    try:
        t = get(slug)
    except LookupError:
        return False
    return t["principals"] == "*" or principal in t["principals"]


def visible(principal):
    return [t for t in registry() if t["principals"] == "*" or principal in t["principals"]]


def settings(t):
    return {"data_dir": _root() / t["slug"], "engagement_id": t["engagement_id"], "entity_name": t["name"],
            "period_start": t["period_start"], "period_end": t["period_end"], "fy_label": t["fy_label"]}


@contextmanager
def scope(slug):
    """Run a block against one tenant's databases and engagement (the default when slug is falsy)."""
    t = get(slug or DEFAULT)
    tok = config.use_tenant(None if t["default"] else settings(t))
    try:
        yield t
    finally:
        config.reset_tenant(tok)


def validate(name, pan, gstin, fy):
    """-> (name, pan, gstin, fy_label, period_start, period_end) or ValueError('INVALID_ARGUMENT: …')."""
    from app import related_parties
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not 3 <= len(name) <= 120:
        raise ValueError("INVALID_ARGUMENT: name must be 3-120 characters. Example: 'Sahyadri Shipyards Enterprises'")
    pan = str(pan or "").strip().upper()
    if not _PAN.fullmatch(pan):
        raise ValueError("INVALID_ARGUMENT: PAN must look like AAFCS6120R (5 letters, 4 digits, 1 letter)")
    gstin = str(gstin or "").strip().upper()
    if not related_parties.gstin_ok(gstin):
        raise ValueError("INVALID_ARGUMENT: GSTIN is not valid (format or check digit). Example: 27AAFCS6120R1ZV")
    if gstin[2:12] != pan:
        raise ValueError("INVALID_ARGUMENT: the GSTIN must embed the PAN (characters 3-12)")
    m = _FY.fullmatch(str(fy or "").strip())
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        raise ValueError("INVALID_ARGUMENT: FY must look like 2025-26")
    y = int(m.group(1))
    return name, pan, gstin, f"{y}-{m.group(2)}", f"{y}-04-01", f"{y + 1}-03-31"


def _slug(name):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "org"
    taken = {t["slug"] for t in registry()}
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def create(name, pan, gstin, fy, principals, created_by):
    """A new, empty organisation: its directory, four databases (COA seeded) and its FY engagement. -> tenant."""
    from app import db, intake
    name, pan, gstin, fy_label, start, end = validate(name, pan, gstin, fy)
    slug = _slug(name)
    stem, taken, n = slug.split("-")[0][:8].upper(), {t["engagement_id"] for t in registry()}, 2
    eid = f"ENG-{stem}-{fy_label}"
    while eid in taken:                      # "Velas Marine" and "Velas Shipping" must not share an engagement id
        eid, n = f"ENG-{stem}{n}-{fy_label}", n + 1
    t = {"slug": slug, "name": name, "pan": pan, "gstin": gstin, "fy_label": fy_label, "period_start": start,
         "period_end": end, "engagement_id": eid,
         "principals": sorted(set(principals)), "created_by": created_by, "created_at": config.now()}
    d = _root() / slug
    d.mkdir(parents=True, exist_ok=False)
    tok = config.use_tenant(settings(t))
    try:
        db.init_all(reset=True)
        intake.ensure_engagement()
    finally:
        config.reset_tenant(tok)
    (d / "tenant.json").write_text(json.dumps(t, indent=2), encoding="utf-8")
    return {**t, "default": False}


def seed_demo(principals=None, invoices=None):
    """Tenant 2 for the demo: Sahyadri Shipyards Enterprises with a small clean year and one analytics run. Visible to
    the audit principals in identities.json (never the client principals of Konkan). Idempotent."""
    from app import analytics, seed
    existing = next((t for t in registry() if t["name"] == DEMO["name"]), None)
    if existing:
        return existing
    if principals is None:
        ids = json.loads(config.IDENTITIES.read_text(encoding="utf-8")) if config.IDENTITIES.exists() else {}
        principals = [i["principal"] for i in ids.values() if i["role"] in ("audit_staff", "engagement_partner")]
    from app.seed import make_gstin
    t = create(DEMO["name"], DEMO["pan"], make_gstin("27", DEMO["pan"]), DEMO["fy"], principals, "system:seed")
    with scope(t["slug"]):
        seed.load(seed.build_plan(invoices or DEMO["invoices"], DEMO["seed"]), reset=True)
        config.set_clock(None)
        analytics.run_all(config.ENGAGEMENT_ID)
    return t


def counts(t):
    """Invoices and engagement status for the org list (read-only; zeros for an empty tenant)."""
    from app import db
    with scope(t["slug"]):
        try:
            with db.borrow("erp", "audit_staff") as e:
                n = e.execute("SELECT count(*) FROM invoices WHERE status = 'ISSUED'").fetchone()[0]
        except FileNotFoundError:
            n = 0
    return {"invoices_count": n}


def public(t):
    """What the UI may show (never the principal list of other users)."""
    return {k: t[k] for k in ("slug", "name", "pan", "gstin", "fy_label", "period_start", "period_end", "engagement_id",
                              "default")}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.tenants", description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed-demo", action="store_true", help="create tenant 2 (Sahyadri Shipyards Enterprises)")
    ap.add_argument("--invoices", type=int, default=DEMO["invoices"])
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.seed_demo:
        t = seed_demo(invoices=a.invoices)
        print(f"tenant {t['slug']}: {t['name']} ({t['engagement_id']})")
    for t in registry():
        print(f"{t['slug']:<36} {t['name']:<36} {t['engagement_id']:<20} {counts(t)['invoices_count']:>6} invoices")
    return 0


if __name__ == "__main__":
    sys.exit(main())
