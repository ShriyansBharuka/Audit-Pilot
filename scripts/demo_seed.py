"""DEMO-SEED: three demo organisations for the judging round, seeded through the REST API and MCP (the same calls the
web app and an agent make), never straight into the databases.

Each organisation gets an engagement partner, an audit staff member and six client users (Supabase e-mail accounts;
the role comes only from the organisation's tenant.json). It then gets a year of business: parties, items, about 35
invoices with a March-end spike and early-April sales, dispatches, e-way bills, receipts, credit notes, journals and
GSTR-1. On top come the client's sales register and related-party list with planted irregularities, risk-based
samples with evidence for about half the requests, and PROPOSED findings. docs/DEMO_ACCOUNTS.md lists the logins.

    python scripts/demo_seed.py --inprocess              # Docker build (DATA_DIR=/app/seed-data): no server needed
    python scripts/demo_seed.py --api http://localhost:8001 --mcp http://localhost:8000/mcp
    python scripts/demo_seed.py --api https://<service>.onrender.com      # one-port server: MCP at <api>/mcp

In-process, the year is replayed on its business dates (config.set_clock, as app.seed does), so entries are keyed on
time. Against a running server everything is entered today, so every document also shows control-gap hits (IRN more
than 30 days late, journals posted after closing). Idempotent: an organisation that already has invoices is left
alone, and Supabase users are signed in when they already exist. Needs SUPABASE_URL + SUPABASE_ANON_KEY (env / .env).
"""
import argparse
import json
import logging
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = os.environ.get("DEMO_PASSWORD", "AuditPilot#Demo2026")
FY_END = "2026-03-31"
FIELDWORK = "2026-05-12"          # register + RP list arrive; the auditor tests from the next day

# ---------------------------------------------------------------- the three organisations (fictional)

ROLES = (("partner", "engagement_partner"), ("staff", "audit_staff"), ("cfo", "client_admin"),
         ("accounts1", "accounts"), ("accounts2", "accounts"), ("sales1", "sales"), ("sales2", "sales"),
         ("warehouse", "warehouse"))


def _people(stem, names):
    return [{"key": k, "role": r, "name": n, "email": f"{k}.{stem}@example.com"} for (k, r), n in zip(ROLES, names)]


ORGS = [
    {"stem": "arnav", "seed": 101, "industry": "Marine equipment",
     "name": "Arnav Marine Systems Pvt Ltd", "pan": "AAJCA7316Q", "membership_no": "112233",
     "people": _people("arnav", ["Nikhil Deshpande", "Pooja Shetty", "Ramesh Iyer", "Farah Khan", "Sandeep Patil",
                                 "Kavya Menon", "Arjun Salvi", "Ganesh Pawar"]),
     "items": [("Butterfly valve DN150", "8481", 1800, "38500.00", "24000.00", (2, 8)),
               ("Bilge pump BP-200", "8413", 1800, "142000.00", "98000.00", (1, 3)),
               ("Marine control panel MCP-6", "8537", 1800, "285000.00", "190000.00", (1, 2)),
               ("Gasket and seal kit", "4016", 1800, "6200.00", "3100.00", (5, 20))],
     "customers": [("Coastline Dredging Pvt Ltd", "27", "400001", "Plot 14, Ballard Estate, Mumbai"),
                   ("Mandovi Dockworks Pvt Ltd", "30", "403001", "22 Dayanand Bandodkar Marg, Panaji"),
                   ("Kanara Ship Repairs Pvt Ltd", "29", "575001", "7 Old Port Road, Mangaluru"),
                   ("Saurashtra Marine Works Pvt Ltd", "24", "364001", "41 Ghogha Road, Bhavnagar"),
                   ("Coromandel Offshore Pvt Ltd", "33", "600001", "18 Rajaji Salai, Chennai"),
                   ("Ratnadeep Trawlers Pvt Ltd", "27", "415612", "5 Mirkarwada Jetty, Ratnagiri")],
     "declared": ("Arnav Ocean Logistics Pvt Ltd", "27", "400705", "9 Sector 19, Vashi, Navi Mumbai"),
     "secret": ("Seabird Marine Traders Pvt Ltd", "27", "400601", "3 Gokhale Road, Thane"),
     "director": ("Vikram Joshi", "AQWPJ4821K"), "relative": ("Anjali Joshi", "BGTPJ5530M"),
     "transporter": "Western Ghats Roadlines", "fake_taxable": "240000", "top_side": "350000.00"},
    {"stem": "medisync", "seed": 202, "industry": "Pharma distribution",
     "name": "Medisync Pharma Distributors Pvt Ltd", "pan": "AAKCM5207H", "membership_no": "145566",
     "people": _people("medisync", ["Anita Bhosale", "Rahul Verma", "Suresh Nair", "Priyanka Jain", "Imran Shaikh",
                                    "Deepa Kulkarni", "Vivek Rane", "Manoj Gaikwad"]),
     "items": [("Paracetamol 500 mg (case of 50 boxes)", "3004", 1200, "9800.00", "7100.00", (10, 40)),
               ("Amoxicillin 250 mg (case)", "3004", 1200, "21500.00", "16200.00", (5, 20)),
               ("Insulin glargine pens (pack of 10)", "3004", 500, "14200.00", "11800.00", (5, 25)),
               ("Digital BP monitor", "9018", 1200, "2450.00", "1600.00", (10, 60))],
     "customers": [("Lifeline Hospitals Pvt Ltd", "27", "411001", "12 Moledina Road, Pune"),
                   ("Shreeji Medical Agencies Pvt Ltd", "24", "380009", "8 Ashram Road, Ahmedabad"),
                   ("Nirmal Healthcare Pvt Ltd", "27", "440001", "27 Central Avenue, Nagpur"),
                   ("Deccan Chemists Pvt Ltd", "36", "500001", "4 Abids Road, Hyderabad"),
                   ("Malabar Medicals Pvt Ltd", "32", "682011", "16 MG Road, Kochi"),
                   ("Narmada Pharma Retail Pvt Ltd", "23", "452001", "33 Rajwada Road, Indore")],
     "declared": ("Medisync Wellness Clinics Pvt Ltd", "27", "411004", "6 Law College Road, Pune"),
     "secret": ("Apex Carewell Distributors Pvt Ltd", "27", "400602", "11 Naupada Road, Thane"),
     "director": ("Sunita Rao", "AHMPR6612D"), "relative": ("Karthik Rao", "BKLPR2209C"),
     "transporter": "Coldchain Express Logistics", "fake_taxable": "186000", "top_side": "240000.00"},
    {"stem": "torqline", "seed": 303, "industry": "Auto components",
     "name": "Torqline Auto Components Ltd", "pan": "AABCT9034L", "membership_no": "167788",
     "people": _people("torqline", ["Prakash Mehta", "Sneha Gokhale", "Ajay Kulkarni", "Ritu Agarwal", "Sameer Joshi",
                                    "Neha Kadam", "Rohan Bhat", "Santosh More"]),
     "items": [("Brake caliper assembly", "8708", 2800, "4850.00", "3300.00", (60, 300)),
               ("Clutch plate kit", "8708", 2800, "3200.00", "2150.00", (80, 400)),
               ("Aluminium alloy wheel 15in", "8708", 2800, "6900.00", "4700.00", (40, 200)),
               ("Wiring harness WH-12", "8544", 1800, "2150.00", "1400.00", (100, 500))],
     "customers": [("Chakan Motors Pvt Ltd", "27", "410501", "Gat 112, Chakan Industrial Area, Pune"),
                   ("Hosur Two Wheelers Pvt Ltd", "33", "635109", "Plot 9, SIPCOT Phase 2, Hosur"),
                   ("Sanand Auto Assemblies Pvt Ltd", "24", "382110", "Plot 21, GIDC Sanand"),
                   ("Manesar Vehicle Systems Pvt Ltd", "06", "122051", "Plot 47, Sector 8, IMT Manesar"),
                   ("Nashik Tractor Works Pvt Ltd", "27", "422010", "D-14, MIDC Satpur, Nashik"),
                   ("Pithampur Commercial Vehicles Pvt Ltd", "23", "454775", "Sector 3, Pithampur")],
     "declared": ("Torqline Mobility Services Pvt Ltd", "27", "411018", "15 Pimpri Road, Pune"),
     "secret": ("Velocity Auto Traders Pvt Ltd", "27", "411014", "2 Nagar Road, Viman Nagar, Pune"),
     "director": ("Rajesh Kulkarni", "ANZPK3307F"), "relative": ("Meera Kulkarni", "BQRPK8814H"),
     "transporter": "Deccan Freight Carriers", "fake_taxable": "412000", "top_side": "475000.00"},
]


def _gstin(state, pan):
    from app.seed import make_gstin
    return make_gstin(state, pan)


def _pan(rng, initial, kind="C"):
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return ("AA" + rng.choice(letters) + kind + initial.upper() + f"{rng.randrange(1000, 9999)}" + rng.choice(letters))


def masters(org):
    """Customers (with ids filled in later), the director, the relative and a transporter for one organisation."""
    rng = random.Random(org["seed"])
    custs = []
    for i, (name, state, pin, addr) in enumerate(org["customers"] + [org["declared"], org["secret"]]):
        pan = _pan(rng, name[0])
        custs.append({"key": f"C{i + 1}", "name": name, "state": state, "pincode": pin, "address": addr, "pan": pan,
                      "gstin": _gstin(state, pan), "phone": f"98{rng.randrange(10_000_000, 99_999_999)}",
                      "email": f"accounts@{name.split()[0].lower()}{i}.example.com",
                      "bank": f"{rng.randrange(10**11, 10**12)}", "ifsc": f"HDFC000{rng.randrange(1000, 9999)}",
                      "series": "G11" if state == "30" else "G2"})
    declared, secret = custs[-2], custs[-1]
    dname, dpan = org["director"]
    director = {"name": dname, "pan": dpan, "phone": f"99{rng.randrange(10_000_000, 99_999_999)}",
                "email": f"{dname.split()[0].lower()}.{dname.split()[1].lower()}@example.com",
                "bank": f"{rng.randrange(10**11, 10**12)}", "ifsc": f"ICIC000{rng.randrange(1000, 9999)}"}
    # the planted link: the "independent" trader banks in the director's own account (strong identifier, D1);
    # the disclosed related company uses the director's phone and e-mail (two medium identifiers)
    secret.update(bank=director["bank"], ifsc=director["ifsc"], secret=True)
    declared.update(phone=director["phone"], email=director["email"], declared=True)
    return custs, director


def _d(s):
    return date.fromisoformat(s)


def plan_invoices(org, custs):
    """About 35 sales: two a month, two in early March, an eight-invoice spike in the last ten days of March and three
    in early April. Tags: 'stuffed' (to the director's trader, never dispatched, reversed in April) and 'late_dispatch'
    (billed 31 March, goods leave on 2 April)."""
    rng = random.Random(org["seed"] + 1)
    regular = [c for c in custs if not c.get("secret")]
    secret = next(c for c in custs if c.get("secret"))
    days = []
    for y, m in [(2025, m) for m in range(4, 13)] + [(2026, 1), (2026, 2)]:
        days += [date(y, m, d).isoformat() for d in sorted(rng.sample(range(3, 27), 2))]
    days += [date(2026, 3, d).isoformat() for d in sorted(rng.sample(range(2, 20), 2))]
    days += [date(2026, 3, d).isoformat() for d in (23, 25, 26, 27, 28, 30, 30, 31)]
    days += ["2026-04-02", "2026-04-06", "2026-04-09"]
    out = []
    for i, d in enumerate(days):
        lines = []
        for it in rng.sample(range(len(org["items"])), rng.choice((1, 1, 2))):
            lo, hi = org["items"][it][5]
            lines.append({"item": it, "qty": rng.randint(lo, hi)})
        out.append({"date": d, "customer": regular[i % len(regular)], "lines": lines, "tag": None})
    next(s for s in out if s["date"].startswith("2025-11"))["customer"] = secret
    stuffed = next(s for s in out if s["date"] == "2026-03-30")
    top = max(range(len(org["items"])), key=lambda i: int(org["items"][i][3].split(".")[0]))
    stuffed.update(customer=secret, tag="stuffed", lines=[{"item": top, "qty": org["items"][top][5][1] * 3}])
    next(s for s in out if s["date"] == "2026-03-31")["tag"] = "late_dispatch"
    return out

# ---------------------------------------------------------------- transport: REST + MCP, in-process or over HTTP


class Api:
    def __init__(self, client, mcp_url, clock=None):
        self.c, self.mcp_url, self.clock, self._n = client, mcp_url, clock, 0

    def at(self, ts):
        """Replay the business date (in-process only: the server's clock is ours)."""
        if self.clock:
            self.clock(ts)

    def call(self, method, path, token, tenant=None, **kw):
        h = {"Authorization": f"Bearer {token}", **({"X-Tenant": tenant} if tenant else {})}
        r = self.c.request(method, path, headers=h, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def get(self, path, token, tenant=None, **kw):
        return self.call("GET", path, token, tenant, **kw)

    def post(self, path, token, tenant=None, **kw):
        return self.call("POST", path, token, tenant, **kw)

    def mcp(self, token, tool, args=None):
        """One MCP tools/call (streamable HTTP, JSON or SSE answer) with an agent token -> the tool's dict."""
        self._n += 1
        h = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream",
             "Content-Type": "application/json"}
        init = {"jsonrpc": "2.0", "id": self._n, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "demo_seed", "version": "1"}}}
        r = self.c.post(self.mcp_url, json=init, headers=h)
        first = _rpc(r)
        h["mcp-protocol-version"] = first["result"]["protocolVersion"]
        if r.headers.get("mcp-session-id"):
            h["mcp-session-id"] = r.headers["mcp-session-id"]
            self.c.post(self.mcp_url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=h)
        body = {"jsonrpc": "2.0", "id": self._n, "method": "tools/call", "params": {"name": tool, "arguments": args or {}}}
        msg = _rpc(self.c.post(self.mcp_url, json=body, headers=h))
        if "error" in msg:
            raise RuntimeError(f"MCP {tool}: {msg['error']}")
        res = msg["result"]
        text = " ".join(c.get("text", "") for c in res.get("content", []))
        if res.get("isError"):
            raise RuntimeError(f"MCP {tool}: {text[:300]}")
        try:
            return json.loads(text)
        except ValueError:
            return res.get("structuredContent") or {}


def _rpc(r):
    if r.status_code >= 400:
        raise RuntimeError(f"MCP HTTP {r.status_code}: {r.text[:300]}")
    if "text/event-stream" in r.headers.get("content-type", ""):
        data = [ln[5:].strip() for ln in r.text.splitlines() if ln.startswith("data:")]
        return json.loads(data[-1])
    return r.json()

# ---------------------------------------------------------------- Supabase accounts (sign in, else sign up)


def _supabase(path, body):
    from app import config
    url = config.env("SUPABASE_URL", "https://ysimtmaxmdkubvkbpyes.supabase.co").rstrip("/") + path
    key = config.env("SUPABASE_ANON_KEY", "")
    if not key:
        raise SystemExit("demo_seed: SUPABASE_ANON_KEY is not set (env or .env)")
    data = json.dumps(body).encode()
    for attempt in range(8):
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"apikey": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                out = json.loads(e.read() or b"{}")
            except ValueError:
                out = {}
            if e.code == 429:                                   # auth rate limit: back off and retry
                wait = min(90, 10 * 2 ** attempt)
                print(f"  Supabase rate limit; waiting {wait}s")
                time.sleep(wait)
                continue
            return e.code, out
    raise SystemExit("demo_seed: Supabase kept answering 429 (rate limit); run again in a few minutes")


def supabase_session(email, password):
    """-> access token. Signs in; creates the account when it does not exist yet ("Confirm email" is off)."""
    code, d = _supabase("/auth/v1/token?grant_type=password", {"email": email, "password": password})
    if code == 200:
        return d["access_token"]
    code, d = _supabase("/auth/v1/signup", {"email": email, "password": password})
    tok = d.get("access_token") or (d.get("session") or {}).get("access_token")
    if code == 200 and tok:
        return tok
    raise SystemExit(f"demo_seed: Supabase refused {email} (HTTP {code}, {d.get('error_code') or d.get('msg')}). "
                     f"If the account exists with another password, set DEMO_PASSWORD.")

# ---------------------------------------------------------------- one organisation


def rupees(p):
    return f"{'-' if p < 0 else ''}{abs(p) // 100}.{abs(p) % 100:02d}"


def seed_org(api, org, sign_in):
    say = lambda s: print(f"  [{org['stem']}] {s}")  # noqa: E731
    tok = {p["key"]: sign_in(p["email"], PASSWORD) for p in org["people"]}
    ptn = tok["partner"]

    # 1. the organisation (creator = engagement partner) and its members
    api.at("2025-04-01T09:00:00+05:30")
    mine = [m for m in api.get("/api/auth/memberships", ptn)["items"]
            if m["name"] == org["name"] and m["role"] == "engagement_partner"]
    if mine:
        slug = mine[0]["slug"]
    else:
        slug = api.post("/api/onboarding/organization", ptn, json={
            "name": org["name"], "pan": org["pan"], "gstin": _gstin("27", org["pan"]), "fy": "2025-26",
            "membership_no": org["membership_no"]})["slug"]
        say(f"organisation {slug} created")
    have = {m["email"] for m in api.get(f"/api/tenants/{slug}/members", ptn)["members"]}
    api.at("2025-04-01T09:05:00+05:30")
    for p in org["people"][1:]:
        if p["email"] not in have:
            api.post(f"/api/tenants/{slug}/invites", ptn, json={"email": p["email"], "role": p["role"]})
    for p in org["people"][1:]:
        got = {m["slug"]: m["role"] for m in api.get("/api/auth/memberships", tok[p["key"]])["items"]}
        if got.get(slug) != p["role"]:
            raise RuntimeError(f"{p['email']} has role {got.get(slug)} in {slug}, expected {p['role']}")
    T = slug
    if api.get("/api/client/lookups", tok["cfo"], T)["invoices"]:
        say("already has invoices: left as it is (delete its tenant directory to rebuild)")
        return summary(api, org, slug, tok)

    # agent tokens for the MCP-only steps: warehouse (e-way bills, dispatch, POD), accounts (receipts, GSTR-1), and
    # the audit staff's agent (analytics, samples). Never printed.
    api.at("2025-04-01T09:25:00+05:30")
    agt = {k: api.post("/api/agent-tokens", tok[k], T, json={"label": "demo-seed"})["token"]
           for k in ("warehouse", "accounts1", "staff")}

    # 2. masters: the CFO creates items, the director, the relative-free transporter; sales create customers
    custs, director = masters(org)
    api.at("2025-04-01T09:30:00+05:30")
    items = []
    for name, hsn, rate_bp, rate, cost, _q in org["items"]:
        items.append(api.post("/api/client/records/item", tok["cfo"], T, json={
            "name": name, "hsn": hsn, "uom": "NOS", "gst_rate_bp": rate_bp, "list_rate": rate, "cost": cost})["result"]["id"])
    api.post("/api/client/records/party", tok["cfo"], T, json={
        "name": director["name"], "tags": "DIRECTOR", "kind": "PERSON", "pan": director["pan"], "state_code": "27",
        "phone": director["phone"], "email": director["email"], "bank_account": director["bank"],
        "ifsc": director["ifsc"]})
    transporter = api.post("/api/client/records/party", tok["cfo"], T, json={
        "name": org["transporter"], "tags": "TRANSPORTER", "state_code": "27"})["result"]["id"]
    for i, c in enumerate(custs):
        api.at(f"2025-04-01T10:{i * 3:02d}:00+05:30")
        c["id"] = api.post("/api/client/records/party", tok["sales1" if i % 2 == 0 else "sales2"], T, json={
            "name": c["name"], "tags": "CUSTOMER", "kind": "ENTITY", "pan": c["pan"], "gstin": c["gstin"],
            "state_code": c["state"], "address": c["address"], "pincode": c["pincode"], "phone": c["phone"],
            "email": c["email"], "bank_account": c["bank"], "ifsc": c["ifsc"]})["result"]["id"]
    say(f"{len(items)} items, {len(custs)} customers, director, transporter")

    # 3. the year, replayed in time order
    sales = plan_invoices(org, custs)
    rng = random.Random(org["seed"] + 2)
    events = []                                              # (timestamp, order, fn)

    def ev(ts, fn):
        events.append((ts, len(events), fn))

    for n, s in enumerate(sales):
        acc = tok["accounts1" if n % 3 else "accounts2"]
        ev(f"{s['date']}T11:{n % 50:02d}:00+05:30", lambda s=s, acc=acc: s.update(inv=api.post(
            "/api/client/records/invoice", acc, T, json={
                "party_id": s["customer"]["id"], "series": s["customer"]["series"], "invoice_date": s["date"],
                "lines": [{"item_id": items[ln["item"]], "qty": ln["qty"], "rate": org["items"][ln["item"]][3]}
                          for ln in s["lines"]]})["result"]))
        if s["tag"] == "stuffed":
            continue                                         # billed, never moved
        moved = (_d(s["date"]) + timedelta(days=2 if s["tag"] == "late_dispatch" else 0)).isoformat()
        delivered = (_d(moved) + timedelta(days=rng.randint(1, 4))).isoformat()
        vehicle, km = f"MH{rng.randint(4, 48):02d}{rng.choice('ABCDEFGH')}{rng.choice('JKLMNPRT')}{rng.randint(1000, 9999)}", \
            rng.randint(60, 1400)

        def dispatch(s=s, moved=moved, delivered=delivered, vehicle=vehicle, km=km):
            no, ewb = s["inv"]["invoice_no"], None
            if s["inv"]["total_paise"] > 50_000_00:          # goods over Rs 50,000 move on an e-way bill
                ewb = api.mcp(agt["warehouse"], "generate_eway_bill",
                              {"invoice": no, "vehicle_no": vehicle, "distance_km": km})["summary"]["ewb_no"]
            mv = api.mcp(agt["warehouse"], "record_dispatch", {
                "invoice_nos": [no], "moved_on": moved, "vehicle_no": vehicle, "transporter_id": transporter,
                "lr_no": f"LR/{moved[2:4]}/{rng.randint(10000, 99999)}", **({"ewb_no": str(ewb)} if ewb else {})})
            s["movement"] = mv["summary"]["id"]
        ev(f"{moved}T16:{n % 50:02d}:00+05:30", dispatch)
        ev(f"{delivered}T12:{n % 50:02d}:00+05:30", lambda s=s, d=delivered: api.mcp(
            agt["warehouse"], "record_delivery", {"movement_id": s["movement"], "delivered_on": d, "received_by": "Stores"}))

    # credit notes: a quality claim in October, a rate difference in January (both in the year) and the April
    # reversal of the stuffed March sale (SA 560 / Ind AS 115: a post-period credit note against a pre-period sale)
    cn_months = set()

    def credit(s, pct, reason, cn_date, acc):
        def go():
            taxable = s["inv"]["taxable_paise"] * pct // 100
            s["cn"] = api.post("/api/client/records/credit-note", tok[acc], T, json={
                "cn_date": cn_date, "reason": reason,
                "lines": [{"invoice_no": s["inv"]["invoice_no"], "taxable": rupees(taxable)}]})["result"]
            s["cn_date"] = cn_date
        cn_months.add(cn_date[:7])
        ev(f"{cn_date}T12:30:00+05:30", go)

    october = next(s for s in sales if s["date"].startswith("2025-10") and not s["customer"].get("secret"))
    january = next(s for s in sales if s["date"].startswith("2026-01"))
    stuffed = next(s for s in sales if s["tag"] == "stuffed")
    credit(october, 4, "QUALITY", (_d(october["date"]) + timedelta(days=15)).isoformat(), "accounts1")
    credit(january, 2, "RATE_DIFF", (_d(january["date"]) + timedelta(days=12)).isoformat(), "accounts2")
    credit(stuffed, 100, "SALES_RETURN", "2026-04-12", "accounts1")

    # receipts 25-45 days after the sale, net of any credit note (the stuffed sale is never paid)
    for s in sales:
        paid_on = (_d(s["date"]) + timedelta(days=rng.randint(25, 45))).isoformat()
        if s["tag"] == "stuffed" or paid_on > "2026-05-10":
            continue

        def receipt(s=s, paid_on=paid_on):
            amt = s["inv"]["total_paise"] - (s["cn"]["total_paise"] if s.get("cn") else 0)
            api.mcp(agt["accounts1"], "record_receipt", {"amount": rupees(amt), "invoice_nos": [s["inv"]["invoice_no"]],
                                                         "settled_on": paid_on, "utr": f"UTR{rng.randint(10**9, 10**10)}"})
        ev(f"{paid_on}T15:00:00+05:30", receipt)

    # journals: a routine inventory entry, and a top-side revenue entry dated 31 March, keyed on 8 April
    top_amt = org["top_side"]
    ev("2025-09-30T18:00:00+05:30", lambda: api.post("/api/client/records/journal", tok["accounts2"], T, json={
        "voucher_date": "2025-09-30", "narration": "Half-year stock reconciliation: consumption transferred to COGS",
        "lines": [{"account_code": "COGS", "debit": "185000.00"}, {"account_code": "INVENTORY", "credit": "185000.00"}]}))
    ev("2026-04-08T19:40:00+05:30", lambda: api.post("/api/client/records/journal", tok["cfo"], T, json={
        "voucher_date": FY_END, "narration": "Sales booked as per MD instruction, documents to follow",
        "lines": [{"account_code": "SUSPENSE", "debit": top_amt}, {"account_code": "SALES", "credit": top_amt}]}))

    # GSTR-1 for every month with documents, filed on the 10th of the next month
    months = sorted({s["date"][:7] for s in sales} | cn_months)
    for m in months:
        y, mo = int(m[:4]), int(m[5:])
        ev(f"{date(y + (mo == 12), mo % 12 + 1, 10).isoformat()}T10:00:00+05:30",
           lambda m=m: api.mcp(agt["accounts1"], "file_gstr1", {"period": m.replace("-", "")}))

    for ts, _n, fn in sorted(events):
        api.at(ts)
        fn()
    say(f"{len(sales)} invoices, 3 credit notes, 2 journals, {len(months)} GSTR-1 returns")

    # 4. the client's files, built from what was entered, with the planted differences
    reg, plants = register_csv(api, agt["accounts1"], org, sales)
    api.at(f"{FIELDWORK}T10:00:00+05:30")
    up = api.post("/api/client/sales-register", tok["accounts1"], T,
                  files={"file": ("sales_register_FY2025-26.csv", reg.encode(), "text/csv")})
    api.at(f"{FIELDWORK}T11:00:00+05:30")
    api.post("/api/client/related-parties", tok["cfo"], T,
             files={"file": ("related_parties.csv", rp_csv(org, custs, director).encode(), "text/csv")})
    say(f"register uploaded ({up['rows_received']} rows; plants: {', '.join(plants)}); RP list omits {custs[-1]['name']}")

    # 5. the auditor's agent over MCP: analytics over 100%, then the risk-based and cut-off samples
    api.at("2026-05-13T10:00:00+05:30")
    api.mcp(agt["staff"], "run_analytics")
    api.at("2026-05-13T10:20:00+05:30")
    tod = api.mcp(agt["staff"], "select_samples", {"kind": "sales_tod", "size": 25})["summary"]
    api.at("2026-05-13T10:40:00+05:30")
    cut = api.mcp(agt["staff"], "select_samples", {"kind": "cutoff"})["summary"]
    say(f"samples: sales TOD {tod['size']} of {tod['population']}, cut-off {cut['size']}")

    # 6. the client answers about half the evidence requests with the system's own documents
    reqs = sorted(api.get("/api/audit/evidence/requests", tok["cfo"], T), key=lambda r: r["id"])
    sent = 0
    for r in reqs[0::2] + reqs[1::2]:                        # every other request, topped up if some can't be answered
        if sent >= (len(reqs) + 1) // 2:
            break
        if r["doc_kind"] not in ("INVOICE", "EWAY_BILL", "LR", "POD", "CREDIT_NOTE"):
            continue
        try:
            text = api.mcp(agt["warehouse"], "render_document",
                           {"doc_type": r["doc_kind"], "id": r["about_doc_no"]})["client_data"]["text"]
        except RuntimeError:
            continue                                         # no such document (e.g. no LR for goods never moved)
        api.at(f"2026-05-{14 + sent // 12:02d}T{10 + sent % 12:02d}:15:00+05:30")
        who = tok["warehouse"] if r["doc_kind"] in ("LR", "POD", "EWAY_BILL") else tok["accounts2"]
        api.post("/api/audit/evidence/submit", who, T, data={"request_id": r["id"]},
                 files={"file": (f"{r['doc_kind']}_{r['about_doc_no'].replace('/', '-')}.txt", text.encode(), "text/plain")})
        sent += 1
    say(f"evidence: {sent} of {len(reqs)} requests answered")

    # 7. PROPOSED findings + the draft memorandum (the partner confirms and signs off in the web app only)
    api.at("2026-05-18T10:00:00+05:30")
    api.post("/api/audit/deliverables/statutory-memo", tok["staff"], T, json={})
    return summary(api, org, slug, tok)


def _line_taxes(api, agent, entity, key):
    """{doc id: [taxable, cgst, sgst, igst]} summed from the books' own lines (paged query_records)."""
    out, cursor = {}, None
    while True:
        page = api.mcp(agent, "query_records", {"entity": entity, "limit": 100, **({"cursor": cursor} if cursor else {})})
        for ln in page["items"]:
            t = out.setdefault(ln[key], [0, 0, 0, 0])
            for k, f in enumerate(("taxable_paise", "cgst_paise", "sgst_paise", "igst_paise")):
                t[k] += ln[f]
        cursor = page.get("next_cursor")
        if not cursor:
            return out


def register_csv(api, acc_agent, org, sales):
    """The client's FY register from the books (exact line taxes), with four planted differences: a sale left out,
    an inflated taxable value, an invoice that is not in the books and a changed date."""
    inv_tax = _line_taxes(api, acc_agent, "invoice_lines", "invoice_id")
    cn_tax = _line_taxes(api, acc_agent, "cn_lines", "cn_id")
    fy = [s for s in sales if s["date"] <= FY_END]
    rows, plain = [], []
    for s in fy:
        row = [s["inv"]["invoice_no"], s["date"], s["customer"]["name"], s["customer"]["gstin"],
               *inv_tax[s["inv"]["id"]], s["inv"]["total_paise"]]
        rows.append(row)
        if not s["tag"] and not s["customer"].get("secret"):
            plain.append(row)
    for s in fy:                                             # credit notes dated inside the year, as negative rows
        if s.get("cn") and s["cn_date"] <= FY_END:
            rows.append([s["cn"]["cn_no"], s["cn_date"], s["customer"]["name"], s["customer"]["gstin"],
                         *[-v for v in cn_tax[s["cn"]["id"]]], -s["cn"]["total_paise"]])
    missing = next(r for r in plain if r[1].startswith("2025-09"))
    inflated = next(r for r in plain if r[1].startswith("2025-12"))
    rows.remove(missing)
    inflated[4:9] = [v * 110 // 100 for v in inflated[4:9]]  # taxable +10%, tax and total follow
    april = next(s for s in sales if s["date"] == "2026-04-02")   # next year's sale pulled into this one
    moved = [april["inv"]["invoice_no"], FY_END, april["customer"]["name"], april["customer"]["gstin"],
             *inv_tax[april["inv"]["id"]], april["inv"]["total_paise"]]
    rows.append(moved)
    fake_no = f"G2/{max(int(s['inv']['invoice_no'].split('/')[1]) for s in fy if s['customer']['series'] == 'G2') + 1:04d}/25"
    cust = next(c["customer"] for c in fy if not c["customer"].get("secret") and c["customer"]["state"] == "27")
    ftx = int(org["fake_taxable"]) * 100
    tax = ftx * org["items"][0][2] // 10000
    rows.append([fake_no, "2026-03-29", cust["name"], cust["gstin"], ftx, tax // 2, tax - tax // 2, 0, ftx + tax])
    rows.sort(key=lambda r: (r[1], r[0]))
    out = ["Invoice No,Invoice Date,Customer Name,GSTIN,Taxable Value,CGST,SGST,IGST,Invoice Total"]
    for r in rows:
        out.append(",".join([r[0], r[1], f'"{r[2]}"', r[3]] + [rupees(v) for v in r[4:9]]))
    plants = [f"{missing[0]} left out", f"{inflated[0]} taxable +10%", f"{moved[0]} of 2026-04-02 dated {FY_END}",
              f"{fake_no} not in the books"]
    return "\n".join(out) + "\n", plants


def rp_csv(org, custs, director):
    """The related-party list as the client sends it: the director, a relative and the disclosed related company.
    The director's trading company (same bank account as the director) is left off: an undisclosed related party."""
    declared = next(c for c in custs if c.get("declared"))
    rel_name, rel_pan = org["relative"]
    rows = [("Name", "PAN", "GSTIN", "Relation", "Effective From", "Effective To"),
            (director["name"], director["pan"], "", "Director", "2019-06-01", ""),
            (rel_name, rel_pan, "", "Relative of director (spouse)", "2019-06-01", ""),
            (declared["name"], declared["pan"], declared["gstin"], "Entity in which a director is interested (s.184)",
             "2019-06-01", "")]
    return "\n".join(",".join(f'"{v}"' if "," in v else v for v in r) for r in rows) + "\n"


def summary(api, org, slug, tok):
    fs = api.get("/api/audit/findings", tok["staff"], slug)
    codes = Counter(f["code"] for f in fs)
    reqs = api.get("/api/audit/evidence/requests", tok["cfo"], slug)
    return {"org": org["name"], "slug": slug, "users": len(org["people"]), "findings": len(fs),
            "codes": dict(codes.most_common()), "evidence_requests": len(reqs),
            "evidence_received": sum(1 for r in reqs if r["status"] == "RECEIVED")}

# ---------------------------------------------------------------- main

EXPECTED = ("NOT_IN_SOR", "MISSING_FROM_REGISTER", "TAXABLE_DIFF", "FY_DIFF", "UNDISCLOSED_RP",
            "POST_PERIOD_REVERSAL", "REVENUE_WITHOUT_SALE", "NO_MOVEMENT")


def run(api, sign_in=supabase_session, only=None):
    out = []
    for org in ORGS:
        if only and org["stem"] not in only:
            continue
        print(f"{org['name']} ({org['industry']})")
        out.append(seed_org(api, org, sign_in))
    print("\nDemo organisations (password: see docs/DEMO_ACCOUNTS.md)")
    for s in out:
        miss = [c for c in EXPECTED if c not in s["codes"]]
        print(f"  {s['slug']:<40} {s['users']} users  {s['findings']:>3} findings  evidence {s['evidence_received']}/"
              f"{s['evidence_requests']}" + (f"  MISSING planted codes: {', '.join(miss)}" if miss else "  all plants found"))
        print(f"    findings by code: {', '.join(f'{k} {v}' for k, v in s['codes'].items())}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python scripts/demo_seed.py", description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inprocess", action="store_true", help="call app.serve in this process (Docker build)")
    g.add_argument("--api", help="REST base URL, e.g. http://localhost:8001")
    ap.add_argument("--mcp", help="MCP URL (default: <api>/mcp, the one-port server)")
    ap.add_argument("--only", nargs="*", help="organisation stems to seed (arnav medisync torqline)")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    logging.getLogger("httpx").setLevel(logging.WARNING)      # one INFO line per request otherwise
    if a.inprocess:
        from starlette.testclient import TestClient
        from app import config
        import app.serve as serve
        with TestClient(serve.app, base_url="http://localhost:8000") as client:
            try:
                run(Api(client, "/mcp", clock=config.set_clock), only=a.only)
            finally:
                config.set_clock(None)
    else:
        import httpx
        with httpx.Client(base_url=a.api.rstrip("/"), timeout=300) as client:
            client.get("/api/health").raise_for_status()      # wakes a sleeping free-plan host
            run(Api(client, a.mcp or a.api.rstrip("/") + "/mcp"), only=a.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
