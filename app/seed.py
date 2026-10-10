"""Demo company seeder: Konkan Marine Controls Ltd (fictional), FY 2025-26.

    python -m app.seed --reset [--invoices 7000] [--seed 7] [--plan-only]

DA-1a (today): SELF + units G2 (Maharashtra, 27) and G11 (Goa, 30); ~150 customers incl. declared group
companies, unregistered buyers and exporters; ~40 items + service lines + CHG items; directors / KMP /
relatives with MBP-1 / DIR-12 links; transporters, vendors; clean sale lifecycles (enquiry -> SO ->
invoice -> e-way bill -> dispatch -> POD) for the FY plus Apr-May 2026; identities.json + judge card.
DA-1 adds receipts + bank, schemes, CNs, GST filings, plants and data/answer_key.json.

The plan is pure data from one recorded seed, so it is testable without a database. load() pushes it
through the erp services (07 §4) in entry-time order, so erp_log seq follows the order a real client
would have keyed things in. Only rng.random() is used (same rule as sampling, 05 §15): one seed gives
the same company on every Python version. Clean data must not trip a detector; see clean-data guards.
"""
import argparse
import json
import os
import random
import secrets
import sys
import time
from datetime import date, timedelta
from pathlib import Path

FY_START, FY_END = date(2025, 4, 1), date(2026, 3, 31)
POST_END = date(2026, 5, 31)                  # post-period docs for cut-off (first 15 after) and D9
MASTERS_AT = "2025-02-01T10:00:00+05:30"      # masters exist before the earliest enquiry (FY start - 45 days)
HOLIDAYS = {date(2025, 8, 15), date(2025, 10, 2), date(2026, 1, 26)}
EWB_THRESHOLD_PAISE = 50_000_00               # CGST Rule 138: consignment value incl. tax

# ---------------------------------------------------------------- rng helpers (rng.random() only)

def _int(rng, lo, hi):
    return lo + int(rng.random() * (hi - lo + 1))

def _pick(rng, seq):
    return seq[int(rng.random() * len(seq))]

def _wpick(rng, pairs):
    x = rng.random() * sum(w for _, w in pairs)
    for v, w in pairs:
        x -= w
        if x < 0:
            return v
    return pairs[-1][0]

def _shuffled(rng, seq):
    out = list(seq)
    for i in range(len(out) - 1, 0, -1):
        j = int(rng.random() * (i + 1))
        out[i], out[j] = out[j], out[i]
    return out

def _letters(rng, n):
    return "".join(_pick(rng, "ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(n))

def _digits(rng, n):
    return "".join(_pick(rng, "0123456789") for _ in range(n))

# ---------------------------------------------------------------- identifiers

_C36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def gstin_check_char(first14):
    """Mod-36 check character (the 05 D1 algorithm, verified on published GSTINs)."""
    t = 0
    for i, ch in enumerate(first14):
        p = _C36.index(ch) * (2 if i % 2 else 1)
        t += p // 36 + p % 36
    return _C36[(36 - t % 36) % 36]

def make_gstin(state_code, pan, entity_no="1"):
    s = f"{state_code}{pan}{entity_no}Z"
    return s + gstin_check_char(s)

def _tax_paise(taxable_paise, rate_bp):       # money.tax_paise (03 §6): half-up per line, integers only
    return (taxable_paise * rate_bp + 5000) // 10000

class _Unique:
    """Draws until unused, so no two parties share a PAN / phone / account by accident."""
    def __init__(self):
        self.seen = set()
    def __call__(self, make):
        while True:
            v = make()
            if v not in self.seen:
                self.seen.add(v)
                return v

def _ts(d, minutes):
    return f"{d.isoformat()}T{minutes // 60:02d}:{minutes % 60:02d}:00+05:30"

# ---------------------------------------------------------------- the company

SELF_PAN = "AAKCK4821M"                       # 4th char C = company, 5th K = Konkan
UNITS = {
    "G2": {"name": "Ratnagiri works", "state_code": "27", "gstin": make_gstin("27", SELF_PAN),
           "address": "Plot B-21, MIDC Mirjole, Ratnagiri", "pincode": "415639", "vehicle_rto": "MH08"},
    "G11": {"name": "Verna works", "state_code": "30", "gstin": make_gstin("30", SELF_PAN),
            "address": "Plot L-54, Verna Industrial Estate, Salcete", "pincode": "403722", "vehicle_rto": "GA08"},
}
SELF_DOMAIN = "konkanmarine.in"

# (city, pincodes, streets) per state; addresses are fictional
CITIES = {
    "27": [("Mumbai", ["400001", "400009", "400072"], ["P D'Mello Road", "Andheri Kurla Road", "Reay Road"]),
           ("Navi Mumbai", ["400703", "400705", "400710"], ["TTC MIDC", "Sector 19 Vashi", "Thane Belapur Road"]),
           ("Ratnagiri", ["415612", "415639"], ["Mirjole MIDC", "Mirkarwada Jetty Road"]),
           ("Pune", ["411018", "411026"], ["Bhosari MIDC", "Pimpri Industrial Area"]),
           ("Alibag", ["402201"], ["Revdanda Road"])],
    "30": [("Vasco da Gama", ["403802", "403803"], ["Harbour Road", "Mangor Hill"]),
           ("Margao", ["403601", "403602"], ["Station Road", "Aquem"]),
           ("Panaji", ["403001"], ["Rua de Ourem"])],
    "29": [("Mangaluru", ["575001", "575010"], ["Bunder Road", "Baikampady Industrial Area"]),
           ("Karwar", ["581301"], ["Baithkol Port Road"])],
    "24": [("Bhavnagar", ["364001", "364004"], ["Alang Road", "Chitra GIDC"]),
           ("Gandhidham", ["370201"], ["Kandla Port Road"]),
           ("Surat", ["395010"], ["Hazira Road"])],
    "33": [("Chennai", ["600001", "600013"], ["Rajaji Salai", "Ennore Express Road"]),
           ("Thoothukudi", ["628001"], ["Harbour Estate"])],
    "32": [("Kochi", ["682001", "682029"], ["Willingdon Island", "Thevara Ferry Road"])],
    "37": [("Visakhapatnam", ["530001", "530035"], ["Port Area", "Scindia Road"])],
    "19": [("Kolkata", ["700043"], ["Garden Reach Road"])],
}
STATE_WEIGHTS = [("27", 45), ("30", 18), ("29", 9), ("24", 10), ("33", 6), ("32", 6), ("37", 4), ("19", 2)]
# km from (unit state, customer state): base range; per-customer distance is fixed once
DIST = {("27", "27"): (40, 360), ("27", "30"): (230, 300), ("30", "30"): (15, 70), ("30", "27"): (230, 560)}
DIST_FAR = {"29": (350, 520), "24": (700, 1050), "33": (1050, 1300), "32": (900, 1150), "37": (1100, 1350),
            "19": (1750, 1950)}

PREFIXES = ["Arabian", "Malabar", "Coastal", "Deccan", "Sahyadri", "Mandovi", "Zuari", "Western", "Bharat",
            "Apex", "Trident", "Anchor", "Harbour", "Seaway", "Bluewater", "Nautica", "Gomantak", "Sindhu",
            "Vaitarna", "Tapti", "Kaveri", "Lakshadweep", "Bay Line", "Mariner"]
TRADES = ["Shipyards", "Marine Services", "Engineering Works", "Dredging", "Fisheries", "Offshore",
          "Port Logistics", "Boat Builders", "Hydraulics", "Ship Repairs", "Marine Automation", "Shipping"]
SUFFIXES = [("Pvt Ltd", "C", 60), ("Ltd", "C", 15), ("LLP", "F", 10), ("& Co", "F", 7), ("Enterprises", "P", 8)]
FIRST = ["Amit", "Sameer", "Prakash", "Nilesh", "Rahul", "Swati", "Kavita", "Deepak", "Manoj", "Farhan",
         "Joseph", "Lalita", "Sandeep", "Arvind", "Shilpa", "Imran", "Gaurav", "Snehal", "Ashok", "Tejas"]
LAST = ["Kulkarni", "Shetty", "Pai", "Fernandes", "Gaonkar", "Jadhav", "Menon", "Iyer", "Patel", "Sheikh",
        "Kadam", "Rao", "Naik", "D'Souza", "Mhatre", "Chavan", "Pillai", "Bhatt", "Raut", "Khan"]
BANKS = ["HDFC", "ICIC", "SBIN", "UTIB", "KKBK", "BARB", "CNRB", "IBKL"]

DIRECTORS = [  # id, name, PAN surname letter, role, since, link relation
    ("P-DIR1", "Vikram Desai", "D", "Managing Director", "2012-06-01", "DIRECTOR_OF"),
    ("P-DIR2", "Anjali Kamat", "K", "Whole-time Director", "2015-04-01", "DIRECTOR_OF"),
    ("P-DIR3", "Rohan Parulekar", "P", "Director", "2018-09-15", "DIRECTOR_OF"),
    ("P-DIR4", "Meera Sawant", "S", "Independent Director", "2021-08-01", "DIRECTOR_OF"),
    ("P-KMP1", "Kiran Bhosle", "B", "Chief Financial Officer", "2019-01-07", "KMP_OF"),
    ("P-KMP2", "Pooja Naik", "N", "Company Secretary", "2022-05-02", "KMP_OF"),
]
RELATIVES = [  # id, name, surname letter, relative of
    ("P-REL1", "Sunita Desai", "D", "P-DIR1"),
    ("P-REL2", "Aditya Desai", "D", "P-DIR1"),
    ("P-REL3", "Ramesh Kamat", "K", "P-DIR2"),
    ("P-REL4", "Nisha Parulekar", "P", "P-DIR3"),
]
GROUP = [  # declared related parties that also buy from SELF (disclosed, dated before the FY)
    ("P-GRP1", "Desai Hydraulics Pvt Ltd", "C", "D", "27", "P-DIR1", "DIRECTOR_OF", None, "2018-04-01"),
    ("P-GRP1", None, None, None, None, "P-DIR1", "SHAREHOLDER_OF", 6000, "2018-04-01"),
    ("P-GRP2", "Kamat Ship Chandlers", "F", "K", "30", "P-REL3", "PARTNER_OF", 5000, "2016-11-01"),
    ("P-GRP3", "Parulekar Offshore Services LLP", "F", "P", "27", "P-DIR3", "PARTNER_OF", 4000, "2020-02-01"),
]
TRANSPORTERS = [  # id, name, unit served, LR prefix
    ("P-TRN1", "Sahyadri Roadlines", "G2", "SRL"), ("P-TRN2", "Ratnagiri Roadways", "G2", "RRW"),
    ("P-TRN3", "Western Ghats Logistics", "G2", "WGL"), ("P-TRN4", "Goa Carriers", "G11", "GCR"),
    ("P-TRN5", "Mandovi Freight Movers", "G11", "MFM"),
]
VENDORS = [("P-VEN1", "Bharat Castings Pvt Ltd", "27"), ("P-VEN2", "Precision Valve Components Pvt Ltd", "27"),
           ("P-VEN3", "Apex Electricals", "30"), ("P-VEN4", "Marine Cables India Ltd", "24"),
           ("P-VEN5", "Shakti Steel Traders", "27")]
OVERSEAS = [("Gulf Marine Supplies FZC", "Saif Zone, Sharjah, UAE"),
            ("Straits Shipcare Pte Ltd", "Tuas South Avenue, Singapore"),
            ("Red Sea Offshore LLC", "Sohar Port, Oman")]

# name, hsn, uom, list rupees, qty range, popularity. GST 18% throughout (no slab changes for these HSNs;
# ponytail: one rate per item — add effective-dated rates if a 5%/40% item is ever needed)
ITEMS = [
    ("Butterfly valve DN50 PN16", "8481", "NOS", 6800, (2, 24), 8),
    ("Butterfly valve DN100 PN16", "8481", "NOS", 11500, (2, 20), 7),
    ("Butterfly valve DN150 PN16", "8481", "NOS", 18900, (1, 12), 5),
    ("Butterfly valve DN250 PN10", "8481", "NOS", 42000, (1, 6), 3),
    ("Globe valve DN40 bronze", "8481", "NOS", 9200, (2, 20), 5),
    ("Gate valve DN80 cast steel", "8481", "NOS", 16400, (1, 12), 4),
    ("Ball valve DN25 SS316", "8481", "NOS", 4350, (4, 40), 8),
    ("Ball valve DN50 SS316", "8481", "NOS", 8900, (2, 24), 6),
    ("Screw-down non-return valve DN65", "8481", "NOS", 14200, (1, 10), 4),
    ("Storm valve DN100", "8481", "NOS", 21500, (1, 8), 3),
    ("Pressure relief valve DN25", "8481", "NOS", 12800, (1, 10), 4),
    ("Solenoid valve 24V DC 1/2 inch", "8481", "NOS", 3950, (4, 40), 7),
    ("Quick-closing valve DN50", "8481", "NOS", 27500, (1, 6), 3),
    ("Valve repair kit (seals and seats)", "8481", "SET", 2450, (5, 60), 6),
    ("Pneumatic actuator DA-60", "8412", "NOS", 15600, (1, 12), 5),
    ("Pneumatic actuator SR-120", "8412", "NOS", 28400, (1, 8), 4),
    ("Electric actuator 50 Nm", "8501", "NOS", 38500, (1, 6), 3),
    ("Hydraulic actuator HA-200", "8412", "NOS", 64000, (1, 4), 2),
    ("Hydraulic power pack 7.5 kW", "8412", "NOS", 385000, (1, 2), 1),
    ("Remote valve control console", "8537", "NOS", 680000, (1, 1), 1),
    ("Engine room alarm monitoring panel", "8537", "NOS", 425000, (1, 2), 1),
    ("Ballast control panel", "8537", "NOS", 310000, (1, 2), 1),
    ("Pump starter panel 15 kW", "8537", "NOS", 145000, (1, 3), 2),
    ("Bilge alarm panel", "8531", "NOS", 48500, (1, 4), 2),
    ("Fire detection control panel 8-zone", "8531", "NOS", 112000, (1, 2), 1),
    ("Junction box SS316 IP66", "8538", "NOS", 6750, (2, 20), 5),
    ("Radar level transmitter", "9026", "NOS", 86000, (1, 6), 2),
    ("Pressure transmitter 0-16 bar", "9026", "NOS", 18500, (1, 12), 5),
    ("Temperature sensor PT100", "9025", "NOS", 4800, (2, 30), 6),
    ("Tank gauging system 8-tank", "9026", "SET", 940000, (1, 1), 1),
    ("Electromagnetic flow meter DN80", "9026", "NOS", 124000, (1, 4), 2),
    ("Draft gauge system", "9026", "SET", 235000, (1, 2), 1),
    ("Valve position indicator", "9026", "NOS", 7600, (2, 20), 4),
    ("Marine cable 2C x 1.5 sqmm", "8544", "MTR", 185, (100, 1500), 5),
    ("Marine cable 4C x 2.5 sqmm", "8544", "MTR", 420, (100, 1000), 4),
    ("Instrumentation cable 2P x 0.75 shielded", "8544", "MTR", 265, (100, 1000), 4),
    ("Fibre-optic marine cable 12F", "8544", "MTR", 310, (100, 800), 2),
    ("LED masthead navigation light", "9405", "NOS", 14800, (1, 8), 3),
    ("Marine pump impeller set", "8413", "SET", 22500, (1, 6), 3),
    ("AMC: remote valve control system", "998719", "JOB", 240000, (1, 1), 2),
    ("Installation and commissioning", "998732", "JOB", 185000, (1, 1), 2),
    ("Calibration of instruments", "998346", "JOB", 38000, (1, 3), 3),
    ("Breakdown repair service", "998719", "JOB", 65000, (1, 1), 2),
]
CHARGES = [("CHG-PACKING", "Packing charges", "998540"), ("CHG-FREIGHT", "Freight charges", "996511"),
           ("CHG-INSURANCE", "Transit insurance", "997136")]

# ---------------------------------------------------------------- masters

def _party(id_, kind, tags, name, pan=None, gstin=None, state_code=None, address="", pincode="",
           phone=None, email=None, bank_account=None, ifsc=None):
    return {"id": id_, "kind": kind, "tags": tags, "name": name, "pan": pan, "gstin": gstin,
            "state_code": state_code, "address": address, "pincode": pincode, "phone": phone,
            "email": email, "bank_account": bank_account, "ifsc": ifsc}

def _slug(name):
    return "".join(ch for ch in name.lower().split(" pvt")[0].split(" ltd")[0].split(" llp")[0] if ch.isalnum())

def _masters(rng):
    pans, phones, accounts, houses = _Unique(), _Unique(), _Unique(), _Unique()
    pan = lambda kind, initial: pans(lambda: _letters(rng, 3) + kind + initial + _digits(rng, 4) + _letters(rng, 1))
    phone = lambda: phones(lambda: _pick(rng, "6789") + _digits(rng, 9))
    bank = lambda: (accounts(lambda: _pick(rng, "123456789") + _digits(rng, _int(rng, 10, 13))),
                    _pick(rng, BANKS) + "0" + _digits(rng, 6))
    pans.seen.add(SELF_PAN)

    def address(state):
        city, pins, streets = _pick(rng, CITIES[state])
        pin = _pick(rng, pins)
        house = houses(lambda: (pin, _pick(rng, ["Plot No. ", "Gala ", "Unit ", "Shed "]) + str(_int(rng, 1, 240))))[1]
        return f"{house}, {_pick(rng, streets)}, {city}", pin

    g2 = UNITS["G2"]
    acct, ifsc = bank()
    parties = [_party("SELF", "ENTITY", "SELF", "Konkan Marine Controls Ltd", SELF_PAN, g2["gstin"], "27",
                      g2["address"], g2["pincode"], phone(), f"accounts@{SELF_DOMAIN}", acct, ifsc)]
    links, meta = [], {}

    def link(frm, to, relation, since, source, pct_bp=None):
        links.append({"id": f"L-{len(links) + 1:03d}", "from_party": frm, "to_party": to, "relation": relation,
                      "pct_bp": pct_bp, "effective_from": since, "effective_to": None, "source": source})

    for id_, name, initial, _role, since, rel in DIRECTORS:
        acct, ifsc = bank()
        addr, pin = address("27")
        parties.append(_party(id_, "PERSON", "DIRECTOR" if rel == "DIRECTOR_OF" else "KMP", name, pan("P", initial),
                              None, "27", addr, pin, phone(), f"{name.split()[0].lower()}.{name.split()[1].lower()}@mailbox.in",
                              acct, ifsc))
        link(id_, "SELF", rel, since, "DIR-12" if rel == "DIRECTOR_OF" else "OTHER")
    for id_, name, initial, of in RELATIVES:
        acct, ifsc = bank()
        addr, pin = address("27")
        parties.append(_party(id_, "PERSON", "RELATIVE", name, pan("P", initial), None, "27", addr, pin, phone(),
                              None, acct, ifsc))
        link(id_, of, "RELATIVE_OF", "2000-01-01", "MBP-1")

    for id_, name, kind, initial, state, person, rel, pct, since in GROUP:
        if name:
            acct, ifsc = bank()
            addr, pin = address(state)
            p = pan(kind, initial)
            parties.append(_party(id_, "ENTITY", "CUSTOMER", name, p, make_gstin(state, p), state, addr, pin, phone(),
                                  f"accounts@{_slug(name)}.in", acct, ifsc))
            meta[id_] = {"state": state, "group": True}
        link(person, id_, rel, since, "MBP-1", pct)

    for id_, name, unit, _lr in TRANSPORTERS:
        state = UNITS[unit]["state_code"]
        acct, ifsc = bank()
        addr, pin = address(state)
        p = pan("F", name[0])
        parties.append(_party(id_, "ENTITY", "TRANSPORTER", name, p, make_gstin(state, p), state, addr, pin, phone(),
                              f"booking@{_slug(name)}.in", acct, ifsc))
    for id_, name, state in VENDORS:
        acct, ifsc = bank()
        addr, pin = address(state)
        p = pan("C" if "Ltd" in name else "F", name[0])
        parties.append(_party(id_, "ENTITY", "VENDOR", name, p, make_gstin(state, p), state, addr, pin, phone(),
                              f"sales@{_slug(name)}.in", acct, ifsc))

    # customers: 147 generated + 3 group companies = 150
    names = _shuffled(rng, [f"{a} {b}" for a in PREFIXES for b in TRADES])
    n = 0
    for i, base in enumerate(names[:140]):
        suffix, kind, _w = _wpick(rng, [((s, k, w), w) for s, k, w in SUFFIXES])
        name = f"{base} {suffix}"
        state = _wpick(rng, STATE_WEIGHTS)
        initial = name[0] if kind != "P" else _pick(rng, LAST)[0]   # proprietorship: proprietor's PAN
        p = pan(kind, initial)
        addr, pin = address(state)
        acct, ifsc = bank()
        email = f"accounts@{_slug(name)}.in" if kind != "P" else f"{_slug(name)}@gmail.com"
        n += 1
        id_ = f"P-{n:04d}"
        parties.append(_party(id_, "ENTITY", "CUSTOMER", name, p, make_gstin(state, p), state, addr, pin, phone(),
                              email, acct, ifsc))
        meta[id_] = {"state": state}
    for i in range(4):                                   # unregistered buyers (B2C / no GSTIN)
        name = f"{_pick(rng, FIRST)} {_pick(rng, LAST)} Boat Repairs"
        addr, pin = address("27")
        n += 1
        id_ = f"P-{n:04d}"
        parties.append(_party(id_, "ENTITY", "CUSTOMER", name, None, None, "27", addr, pin, phone(), None, None, None))
        meta[id_] = {"state": "27", "unregistered": True}
    for name, addr in OVERSEAS:                          # exports: place of supply 96 (other country)
        acct = accounts(lambda: _digits(rng, 12))
        n += 1
        id_ = f"P-{n:04d}"
        parties.append(_party(id_, "ENTITY", "CUSTOMER", name, None, None, "96", addr, "999999", "+971" + _digits(rng, 8),
                              f"purchase@{_slug(name)}.com", acct, None))
        meta[id_] = {"state": "96", "export": True}

    # clean-data guard (DA-3 regression): six small customers share their CA's phone -> fan-out, no D1 edge
    ca_phone = phone()
    shared = [p for p in parties if p["id"].startswith("P-0") and meta[p["id"]].get("state") == "27"
              and p["gstin"]][-6:]
    for p in shared:
        p["phone"] = ca_phone
    regressions = [{"kind": "SHARED_SERVICE_PHONE", "phone": ca_phone, "party_ids": [p["id"] for p in shared],
                    "expect": "SERVICE_PROVIDER_IDENTIFIER; no D1 edge"}]
    return parties, links, meta, regressions


def _items(rng):
    items = []
    for i, (name, hsn, uom, rupees, _q, _w) in enumerate(ITEMS, 1):
        cost = rupees * _int(rng, 62, 74) // 100
        items.append({"id": f"IT-{i:03d}", "name": name, "hsn": hsn, "uom": uom, "gst_rate_bp": 1800,
                      "list_rate_paise": rupees * 100, "cost_paise": cost * 100})
    for id_, name, hsn in CHARGES:
        items.append({"id": id_, "name": name, "hsn": hsn, "uom": "JOB", "gst_rate_bp": 1800,
                      "list_rate_paise": 0, "cost_paise": 0})
    return items

# ---------------------------------------------------------------- sales

def _business_days(lo, hi):
    d, out = lo, []
    while d <= hi:
        if d.weekday() != 6 and d not in HOLIDAYS:
            out.append(d)
        d += timedelta(days=1)
    return out

# Apr..Mar; March sits inside the other months' range (no clean-data D5 END_WINDOW_SHARE hit)
MONTH_WEIGHTS = [7, 7, 8, 8, 8, 9, 8, 8, 9, 9, 9, 9]

def _sale_dates(rng, n_fy, n_post):
    by_month = {}
    for d in _business_days(FY_START, FY_END):
        by_month.setdefault((d.year, d.month), []).append(d)
    months = list(by_month)
    out = []
    for _ in range(n_fy):
        m = _wpick(rng, list(zip(months, MONTH_WEIGHTS)))
        out.append(_pick(rng, by_month[m]))
    post = _business_days(FY_END + timedelta(days=1), POST_END)
    out += [_pick(rng, post) for _ in range(n_post)]
    return sorted(out)


def _customer_profiles(rng, parties, meta):
    custs = [p for p in parties if p["tags"] == "CUSTOMER"]
    ranked = _shuffled(rng, [p["id"] for p in custs if not meta[p["id"]].get("group")])
    for gid, at in (("P-GRP1", 4), ("P-GRP2", 11), ("P-GRP3", 19)):   # group companies buy regularly
        ranked.insert(at, gid)
    prof = {}
    for rank, pid in enumerate(ranked, 1):
        m = meta[pid]
        st = m["state"]
        prof[pid] = {
            "weight": 1.0 / rank ** 0.8 * (0.25 if m.get("export") or m.get("unregistered") else 1.0),
            "unit_pref": "G11" if st == "30" else "G2",
            "discount_bp": _wpick(rng, [(0, 60), (200, 15), (300, 15), (500, 10)]),
            "credit_days": _pick(rng, [30, 45, 60, 90]),
            "channel": _wpick(rng, [("EMAIL", 45), ("PHONE", 25), ("VISIT", 15), ("PORTAL", 15)]),
            "contact": f"{_pick(rng, FIRST)} {_pick(rng, LAST)}",
            "dist": {u: _cust_distance(rng, UNITS[u]["state_code"], st) for u in UNITS},
            "po_prefix": "".join(w[0] for w in next(p["name"] for p in custs if p["id"] == pid).split()[:3]).upper(),
        }
    return prof


def _cust_distance(rng, unit_state, cust_state):
    if cust_state == "96":
        return _int(rng, 300, 420)                       # to the port of loading
    lo, hi = DIST.get((unit_state, cust_state)) or DIST_FAR.get(cust_state, (300, 800))
    return _int(rng, lo, hi)


def _lines(rng, items, is_service):
    pool = [(it, w) for it, (*_x, w) in zip(items, ITEMS) if (it["hsn"].startswith("99")) == is_service]
    k = 1 if is_service else _wpick(rng, [(1, 45), (2, 30), (3, 17), (4, 8)])
    chosen = []
    while len(chosen) < k:
        it = _wpick(rng, pool)
        if it not in chosen:
            chosen.append(it)
    out = []
    for it in chosen:
        lo, hi = next(q for (name, *_r, q, _w) in ITEMS if name == it["name"])
        out.append({"item_id": it["id"], "qty": _int(rng, lo, hi), "rate_paise": it["list_rate_paise"]})
    return out


def _sales(rng, n_fy, parties, meta, items):
    prof = _customer_profiles(rng, parties, meta)
    by_id = {p["id"]: p for p in parties}
    cust_pick = [(pid, pr["weight"]) for pid, pr in prof.items()]
    n_post = max(20, n_fy * 8 // 100)
    lr_counters = {t[0]: 0 for t in TRANSPORTERS}
    vehicles = {t[0]: [f"{UNITS[t[2]]['vehicle_rto']}{_letters(rng, 2)}{_digits(rng, 4)}" for _ in range(5)]
                for t in TRANSPORTERS}
    sales = []
    for i, inv_date in enumerate(_sale_dates(rng, n_fy, n_post), 1):
        pid = _wpick(rng, cust_pick)
        pr, cust = prof[pid], by_id[pid]
        unit = pr["unit_pref"] if rng.random() < 0.85 else _pick(rng, [u for u in UNITS if u != pr["unit_pref"]])
        is_service = bool(cust["gstin"]) and rng.random() < 0.08
        lines = _lines(rng, items, is_service)
        if not is_service:                               # charges ride on goods invoices
            for chg, p, lo, hi in (("CHG-FREIGHT", 0.30, 10, 200), ("CHG-PACKING", 0.20, 5, 60),
                                   ("CHG-INSURANCE", 0.10, 5, 40)):
                if rng.random() < p:
                    lines.append({"item_id": chg, "qty": 1, "rate_paise": _int(rng, lo, hi) * 100_00})
        taxable = tax = 0
        for ln in lines:
            gross = ln["qty"] * ln["rate_paise"]
            ln["discount_paise"] = 0 if ln["item_id"].startswith("CHG") else (gross * pr["discount_bp"] + 5000) // 10000
            t = gross - ln["discount_paise"]
            taxable += t
            tax += _tax_paise(t, 1800)
        terms = "FOR_DISPATCH" if is_service else _wpick(rng, [("FOR_DISPATCH", 50), ("EX_WORKS", 20), ("FOR_DESTINATION", 30)])
        if meta[pid].get("export"):
            terms = "FOR_DISPATCH"
        enquired = inv_date - timedelta(days=_int(rng, 10, 45))
        quoted = enquired + timedelta(days=_int(rng, 1, 5))
        confirmed = min(quoted + timedelta(days=_int(rng, 1, 10)), inv_date - timedelta(days=1))
        s = {"key": f"S-{i:05d}", "unit": unit, "party_id": pid, "invoice_date": inv_date.isoformat(),
             "place_of_supply": cust["state_code"], "is_service": is_service, "lines": lines,
             "taxable_paise": taxable, "tax_paise": tax, "total_paise": taxable + tax,
             "so": {"party_id": pid, "channel": pr["channel"], "enquired_on": enquired.isoformat(),
                    "quoted_on": quoted.isoformat(), "confirmed_on": confirmed.isoformat(),
                    "contact_name": pr["contact"], "contact_phone": cust["phone"], "contact_email": cust["email"],
                    "customer_po_no": f"PO/{pr['po_prefix']}/{inv_date.year % 100:02d}/{_int(rng, 100, 9999)}",
                    "delivery_terms": terms, "credit_days": pr["credit_days"],
                    "lines": [{k: ln[k] for k in ("item_id", "qty", "rate_paise", "discount_paise")} for ln in lines]},
             "dispatch": None, "delivery": None, "ewb": False}
        if not is_service:
            # goods leave on the invoice date or the next day (CGST s.31(1)(a)); FY goods never leave in April
            late = rng.random() >= 0.9 and inv_date != FY_END
            moved = inv_date + timedelta(days=1 if late else 0)
            km = pr["dist"][unit]
            transit = 0 if km < 120 else (km + 349) // 350
            delivered = moved + timedelta(days=transit)
            if terms == "FOR_DESTINATION" and inv_date <= FY_END < delivered:
                terms = s["so"]["delivery_terms"] = "FOR_DISPATCH"     # clean-data guard: no accidental D3 PREMATURE
            trn = _pick(rng, [t for t in TRANSPORTERS if t[2] == unit])
            lr_counters[trn[0]] += 1
            lr_no = f"{trn[3]}/{moved.year % 100:02d}/{lr_counters[trn[0]]:05d}"
            s["dispatch"] = {"moved_on": moved.isoformat(), "transporter_id": trn[0],
                             "vehicle_no": _pick(rng, vehicles[trn[0]]), "lr_no": lr_no, "lr_date": moved.isoformat(),
                             "from_pincode": UNITS[unit]["pincode"], "to_pincode": cust["pincode"], "distance_km": km,
                             "lines": [{"item_id": ln["item_id"], "qty": ln["qty"]} for ln in lines
                                       if not ln["item_id"].startswith("CHG")]}
            s["delivery"] = {"delivered_on": delivered.isoformat(), "received_by": pr["contact"],
                             "recorded_lag_days": _wpick(rng, [(0, 60), (1, 30), (2, 10)])}
            s["ewb"] = s["total_paise"] > EWB_THRESHOLD_PAISE
        sales.append(s)
    return sales


def _lost_leads(rng, n, parties):
    custs = [p for p in parties if p["tags"] == "CUSTOMER" and p["gstin"]]
    days = _business_days(FY_START, FY_END)
    leads = []
    for i in range(n):
        p = _pick(rng, custs)
        leads.append({"key": f"L-{i + 1:05d}", "party_id": p["id"], "enquired_on": _pick(rng, days).isoformat(),
                      "channel": _wpick(rng, [("EMAIL", 45), ("PHONE", 35), ("VISIT", 10), ("PORTAL", 10)]),
                      "contact_name": f"{_pick(rng, FIRST)} {_pick(rng, LAST)}", "contact_phone": p["phone"],
                      "contact_email": p["email"]})
    return leads

# ---------------------------------------------------------------- events (what load() replays, in entry order)

# principal per role (identities.json uses the same principals, so erp_log actors are real users)
PEOPLE = {"sales": "sales.priya", "warehouse": "whs.ganesh", "accounts": "acc.neha", "client_admin": "adm.kiran"}

def _ev(at, role, service, args, refs=None, out=None):
    return {"at": at, "actor": PEOPLE[role], "role": role, "service": service, "args": args,
            "refs": refs or {}, "out": out}

def _events(rng, sales, leads):
    """Each sale's events have strictly increasing times, so a stable sort keeps every dependency in order."""
    evs = []
    for ld in leads:
        d = date.fromisoformat(ld["enquired_on"])
        evs.append(_ev(_ts(d, _int(rng, 600, 1080)), "sales", "create_lead",
                       {k: v for k, v in ld.items() if k != "key"}))
    for s in sales:
        k = s["key"]
        conf = date.fromisoformat(s["so"]["confirmed_on"])
        inv = date.fromisoformat(s["invoice_date"])
        seq = [_ev(_ts(conf, _int(rng, 570, 660)), "sales", "create_sales_order", dict(s["so"]),
                   out=(f"{k}/so", "id"))]
        t_inv = _int(rng, 660, 900)
        seq.append(_ev(_ts(inv, t_inv), "accounts", "issue_invoice",
                       {"series": s["unit"], "invoice_date": s["invoice_date"], "party_id": s["party_id"],
                        "place_of_supply": s["place_of_supply"],
                        "lines": [{k2: ln[k2] for k2 in ("item_id", "qty", "rate_paise", "discount_paise")}
                                  for ln in s["lines"]]},
                       refs={"so_id": f"{k}/so"}, out=(f"{k}/inv", "id")))
        if s["dispatch"]:
            dp = s["dispatch"]
            moved = date.fromisoformat(dp["moved_on"])
            t = t_inv + _int(rng, 20, 90) if moved == inv else _int(rng, 570, 720)
            if s["ewb"]:
                seq.append(_ev(_ts(moved, t), "warehouse", "generate_eway_bill",
                               {"vehicle_no": dp["vehicle_no"], "distance_km": dp["distance_km"], "reason": "SUPPLY",
                                "transport_doc_no": dp["lr_no"]},
                               refs={"invoice_id": f"{k}/inv"}, out=(f"{k}/ewb", "ewb_no")))
                t += _int(rng, 10, 40)
            args = {kk: dp[kk] for kk in ("moved_on", "transporter_id", "vehicle_no", "lr_no", "lr_date",
                                          "from_pincode", "to_pincode", "lines")}
            args["direction"] = "OUT"
            refs = {"invoice_nos": f"{k}/inv"}
            if s["ewb"]:
                refs["ewb_no"] = f"{k}/ewb"
            seq.append(_ev(_ts(moved, t), "warehouse", "record_dispatch", args, refs=refs, out=(f"{k}/mov", "id")))
            dv = s["delivery"]
            rec = date.fromisoformat(dv["delivered_on"]) + timedelta(days=dv["recorded_lag_days"])
            seq.append(_ev(_ts(rec, _int(rng, 1050, 1170)), "warehouse", "record_delivery",
                           {"delivered_on": dv["delivered_on"], "received_by": dv["received_by"]},
                           refs={"movement_id": f"{k}/mov"}))
        evs += seq
    evs.sort(key=lambda e: e["at"])
    return evs

# ---------------------------------------------------------------- plan

def build_plan(n_invoices=7000, seed=7):
    rng = random.Random(seed)
    parties, links, meta, regressions = _masters(rng)
    items = _items(rng)
    sales = _sales(rng, n_invoices, parties, meta, items)
    leads = _lost_leads(rng, max(10, n_invoices // 8), parties)
    return {"seed": seed, "n_invoices": n_invoices, "fy": ["2025-04-01", "2026-03-31"], "post_end": POST_END.isoformat(),
            "units": UNITS, "parties": parties, "links": links, "items": items, "sales": sales,
            "events": _events(rng, sales, leads), "regressions": regressions}

# ---------------------------------------------------------------- identities (04 §1) + judge card

ROLES = [("sales", "sal_", "sales.priya", "Priya Shetty, sales executive"),
         ("warehouse", "whs_", "whs.ganesh", "Ganesh Patil, dispatch"),
         ("accounts", "acc_", "acc.neha", "Neha Joshi, accounts"),
         ("client_admin", "adm_", "adm.kiran", "Kiran Bhosle, CFO"),
         ("audit_staff", "aud_", "aud.judge", "Auditor agent (judges)"),
         ("audit_staff", "aud_", "aud.investigator", "AuditPilot investigator"),
         ("orchestrator", "orc_", "orc.n8n", "n8n workflows"),
         ("engagement_partner", "ptn_", "ptn.mehta", "CA Rakesh Mehta, engagement partner")]

def make_identities():
    ids = {}
    for role, prefix, principal, name in ROLES:
        rec = {"principal": principal, "role": role, "name": name}
        if role == "engagement_partner":
            rec["membership_no"] = "118204"          # ICAI no., read by the partner UI at sign-off (06 §9)
        ids[prefix + secrets.token_urlsafe(24)] = rec
    return ids

def judge_card(ids, url=None):
    url = url or os.environ.get("PUBLIC_URL", "http://localhost:8000/mcp")
    lines = ["", "=== AuditPilot judge card ===", f"MCP endpoint: {url}", ""]
    for token, i in ids.items():
        where = "web UI only (never give to an agent)" if i["role"] == "engagement_partner" else "MCP"
        lines.append(f"  {i['role']:<19} {i['principal']:<17} {token}   [{where}]")
    client = next(t for t, i in ids.items() if i["role"] == "client_admin")
    audit = next(t for t, i in ids.items() if i["principal"] == "aud.judge")
    lines += ["", "Claude Code:",
              f'  claude mcp add --transport http auditpilot-client {url} --header "Authorization: Bearer {client}"',
              f'  claude mcp add --transport http auditpilot-auditor {url} --header "Authorization: Bearer {audit}"',
              f"Header-less hosts: {url.rsplit('/mcp', 1)[0]}/c/<token>/mcp", ""]
    return "\n".join(lines)

# ---------------------------------------------------------------- load into the DBs (needs SH-1/SH-2/SH-4)

def load(plan, reset):
    """Replays the plan through the erp services. Each service is (actor, role, **args) -> {result, next_steps}
    (07 §4); kwargs are 03 column names, money in paise. The clock is set per event so recorded_at, IRN ack_at
    and EWB generated_at fall on the business date instead of today (needs config.set_clock, see PROGRESS)."""
    from app import config, db, erp
    db.init_all(reset=reset)
    config.set_clock(MASTERS_AT)
    for service, rows, role in (("create_party", plan["parties"], "client_admin"),
                                ("link_parties", plan["links"], "client_admin"),
                                ("create_item", plan["items"], "client_admin")):
        for row in rows:
            _call(erp, service, PEOPLE[role], role, row, row["id"])
    ids = {}
    for ev in plan["events"]:
        config.set_clock(ev["at"])
        args = dict(ev["args"])
        for arg, ref in ev["refs"].items():
            args[arg] = [ids[ref]] if arg.endswith("_nos") else ids[ref]
        res = _call(erp, ev["service"], ev["actor"], ev["role"], args, ev["at"])
        if ev["out"]:
            ids[ev["out"][0]] = res["result"][ev["out"][1]]
    config.set_clock(None)
    return ids

def _call(erp, service, actor, role, args, where):
    try:
        return getattr(erp, service)(actor, role, **args)
    except Exception as e:
        raise SystemExit(f"seed: erp.{service} failed at {where}: {type(e).__name__}: {e}") from e

# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__.split("\n\n")[0])
    ap.add_argument("--reset", action="store_true", help="drop and rebuild the 4 databases")
    ap.add_argument("--invoices", type=int, default=7000, help="FY 2025-26 invoices (post-period adds ~8%%)")
    ap.add_argument("--seed", type=int, default=7, help="data seed (the demo company; not a sampling seed)")
    ap.add_argument("--plan-only", action="store_true", help="write data/seed_plan.json + identities, skip the DBs")
    a = ap.parse_args(argv)

    t0 = time.perf_counter()
    plan = build_plan(a.invoices, a.seed)
    if a.plan_only:
        data = Path(os.environ.get("DATA_DIR", "data"))
        data.mkdir(exist_ok=True)
        (data / "seed_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    else:
        load(plan, a.reset)
    # tokens survive a plain re-run so configured agents keep working; --reset issues new ones
    id_path = Path(os.environ.get("IDENTITIES", "identities.json"))
    if a.reset or not id_path.exists():
        id_path.write_text(json.dumps(make_identities(), indent=2), encoding="utf-8")
    ids = json.loads(id_path.read_text(encoding="utf-8"))

    n_cust = sum(p["tags"] == "CUSTOMER" for p in plan["parties"])
    fy = [s for s in plan["sales"] if s["invoice_date"] <= plan["fy"][1]]
    print(f"seed {a.seed}: {n_cust} customers, {len(plan['items'])} items, {len(fy)} FY invoices "
          f"(Rs {sum(s['taxable_paise'] for s in fy) // 100:,} taxable) + {len(plan['sales']) - len(fy)} post-period, "
          f"{len(plan['events'])} events{' (plan only)' if a.plan_only else ' loaded'} in {time.perf_counter() - t0:.1f}s")
    print(judge_card(ids))

if __name__ == "__main__":
    sys.exit(main())
