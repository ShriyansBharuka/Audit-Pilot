"""D1/D2 on the seed's company: clean data gives no RP exceptions; every A/B plant (08 §5) is caught."""
import copy

import pytest

from app import seed
from app.related_parties import address_key, analyse, gstin_hits_register, gstin_ok, keys, status_on

P0, P1 = "2025-04-01", "2026-03-31"


@pytest.fixture(scope="module")
def base():
    plan = seed.build_plan(300, 7)
    links = plan["links"]
    # the client's RP list as management would declare it: every person/entity linked to SELF, with link dates
    declared_ids = ["P-DIR1", "P-DIR2", "P-DIR3", "P-DIR4", "P-KMP1", "P-KMP2", "P-REL1", "P-REL2", "P-REL3",
                    "P-REL4", "P-GRP1", "P-GRP2", "P-GRP3"]
    by_id = {p["id"]: p for p in plan["parties"]}
    rp_rows = []
    for i, pid in enumerate(declared_ids, 1):
        p = by_id[pid]
        since = max(l["effective_from"] for l in links if pid in (l["from_party"], l["to_party"]))
        if pid.startswith("P-REL"):      # a relative's relationship starts when their director joined
            of = next(l["to_party"] for l in links if l["from_party"] == pid)
            since = next(l["effective_from"] for l in links if l["from_party"] == of and l["to_party"] == "SELF")
        rp_rows.append({"row_no": i, "name": p["name"], "pan": p["pan"], "gstin": p["gstin"],
                        "effective_from": since, "effective_to": None})
    invoices = [{"id": s["key"], "party_id": s["party_id"], "control_date": s["invoice_date"],
                 "taxable_paise": s["taxable_paise"]} for s in plan["sales"]]
    return plan, rp_rows, invoices


def run(plan, rp_rows, invoices, parties=None, links=None, since=None):
    return analyse(parties or plan["parties"], links or plan["links"], rp_rows, P0, P1, invoices, since)


def codes(res, code):
    return {h["object_id"] for h in res["hits"] if h["code"] == code}


def plain_customer(parties, n):
    return [p for p in parties if p["id"].startswith("P-0") and p["gstin"] and p["state_code"] == "27"][n]


def test_clean_company_has_no_rp_exceptions(base):
    plan, rp_rows, invoices = base
    res = run(plan, rp_rows, invoices)
    bad = [h for h in res["hits"] if h["code"] not in ("SERVICE_PROVIDER_IDENTIFIER",)]
    assert bad == []
    sp = [h for h in res["hits"] if h["code"] == "SERVICE_PROVIDER_IDENTIFIER"]
    assert len(sp) == 1 and sorted(sp[0]["evidence"]["party_ids"]) == sorted(plan["regressions"][0]["party_ids"])
    assert status_on(res["rp"]["P-GRP1"], "2025-06-01")[0] == "DECLARED_RP"
    assert status_on(res["rp"].get(plain_customer(plan["parties"], 0)["id"]), "2025-06-01")[0] == "NRP"


def test_a_family_shared_identifiers(base):
    plan, rp_rows, invoices = base
    parties = copy.deepcopy(plan["parties"])
    links = copy.deepcopy(plan["links"])
    by_id = {p["id"]: p for p in parties}
    c = [plain_customer(parties, i) for i in range(6)]
    c[0]["pan"] = by_id["P-DIR1"]["pan"]                                              # A1 PAN = director's
    c[1]["gstin"] = seed.make_gstin("27", by_id["P-REL1"]["pan"], "2")               # A2 GSTIN embeds spouse PAN
    c[2]["bank_account"], c[2]["ifsc"] = by_id["P-GRP1"]["bank_account"], by_id["P-GRP1"]["ifsc"]   # A3
    d2 = by_id["P-DIR2"]
    d2["phone"] = "9820012345"
    c[3]["phone"] = "+91 98200-12345"                                                # A4 phone + reworded address
    pin, house, street = address_key(d2["address"], d2["pincode"]).split("|")
    c[3]["address"], c[3]["pincode"] = f"Plot {house}, {street.title()} MIDC Road, Pune", pin
    links.append({"id": "L-900", "from_party": "P-DIR3", "to_party": c[4]["id"], "relation": "DIRECTOR_OF",
                  "pct_bp": None, "effective_from": "2020-01-01", "effective_to": None, "source": "OTHER"})   # A5
    c[5]["address"], c[5]["pincode"] = "Plot B-21, MIDC Mirjole, Ratnagiri", "415639"  # A6 SELF address + domain
    c[5]["email"] = "purchase@konkanmarine.in"
    res = run(plan, rp_rows, invoices, parties, links)
    und = codes(res, "UNDISCLOSED_RP")
    assert {p["id"] for p in c} <= und, und - {p["id"] for p in c}
    assert len(und) == 6
    assert c[1]["id"] in codes(res, "PAN_GSTIN_MISMATCH") and c[0]["id"] in codes(res, "PAN_GSTIN_MISMATCH")
    reasons = {h["object_id"]: h["reason"] for h in res["hits"] if h["code"] == "UNDISCLOSED_RP"}
    assert "GSTIN embeds PAN" in reasons[c[1]["id"]] and "P-REL1" in reasons[c[1]["id"]]
    assert "L-900" in reasons[c[4]["id"]]
    assert all(p["name"] not in r for p in c for r in reasons.values())             # no client text in reasons
    assert all(h["impact_paise"] >= 0 for h in res["hits"])


def test_b_family_mid_period(base):
    plan, rp_rows, invoices = base
    links = copy.deepcopy(plan["links"])
    parties = copy.deepcopy(plan["parties"])
    by_id = {p["id"]: p for p in parties}
    sold = {i["party_id"] for i in invoices}
    b1, b2, b4 = [p for p in parties if p["id"].startswith("P-0") and p["gstin"] and p["id"] in sold][:3]
    links.append({"id": "L-901", "from_party": "P-DIR1", "to_party": b1["id"], "relation": "DIRECTOR_OF",
                  "pct_bp": None, "effective_from": "2025-10-01", "effective_to": None, "source": "OTHER"})   # B1
    links.append({"id": "L-902", "from_party": "P-DIR2", "to_party": b2["id"], "relation": "DIRECTOR_OF",
                  "pct_bp": None, "effective_from": "2025-10-01", "effective_to": None, "source": "OTHER"})   # B2
    rows = rp_rows + [{"row_no": 99, "name": b2["name"], "pan": b2["pan"], "gstin": b2["gstin"],
                       "effective_from": "2026-01-01", "effective_to": None}]
    b4["bank_account"], b4["ifsc"] = by_id["P-DIR1"]["bank_account"], by_id["P-DIR1"]["ifsc"]          # B4
    res = run(plan, rows, invoices, parties, links, since={(b4["id"], "BANK"): "2025-10-15"})
    assert status_on(res["rp"][b1["id"]], "2025-06-01")[0] == "NRP_BEFORE_RELATIONSHIP"
    assert status_on(res["rp"][b1["id"]], "2025-11-01")[0] == "UNDISCLOSED_RP"
    assert b1["id"] in codes(res, "UNDISCLOSED_RP")
    assert b2["id"] in codes(res, "RP_PERIOD_MISSTATED") and b2["id"] not in codes(res, "UNDISCLOSED_RP")
    assert status_on(res["rp"][b2["id"]], "2025-11-01")[0] == "UNDISCLOSED_RP"     # in the gap
    assert status_on(res["rp"][b2["id"]], "2026-02-01")[0] == "DECLARED_RP"
    gap = next(h for h in res["hits"] if h["code"] == "RP_PERIOD_MISSTATED" and h["object_id"] == b2["id"])
    expect = [i for i in invoices if i["party_id"] == b2["id"] and "2025-10-01" <= i["control_date"] < "2026-01-01"]
    assert gap["impact_paise"] == sum(i["taxable_paise"] for i in expect)
    assert res["rp"][b4["id"]]["independent"][0] == "2025-10-15"
    assert status_on(res["rp"][b4["id"]], "2025-09-01")[0] == "NRP_BEFORE_RELATIONSHIP"


def test_unsupported_declaration_and_register_gstins():
    res = analyse([{"id": "SELF", "tags": "SELF", "name": "X", "email": "a@x.in"},
                   {"id": "P-1", "tags": "CUSTOMER", "name": "Alpha Pvt Ltd", "gstin": "27AAPFU0939F1ZV",
                    "state_code": "27"}],
                  [], [{"row_no": 1, "name": "Alpha Pvt Ltd"}], P0, P1)
    assert {h["code"] for h in res["hits"]} == {"DECLARED_UNSUPPORTED"}
    regs = [{"kind": "ROW", "row_no": 1, "gstin": "27AAPFU0939F1ZA", "state_code": "27"},     # K8 bad check digit
            {"kind": "ROW", "row_no": 2, "gstin": "27AAPFU0939F1ZV", "state_code": 0},        # Fig. 1 State Code 0
            {"kind": "ROW", "row_no": 3, "gstin": "27AAPFU0939F1ZV", "state_code": "27"},
            {"kind": "ROW", "row_no": 4, "gstin": None, "state_code": 0}]
    assert [(h["code"], h["object_id"]) for h in gstin_hits_register(regs)] == [
        ("INVALID_GSTIN", "1"), ("GSTIN_STATE_MISMATCH", "2")]


def test_keys_normalise():
    assert gstin_ok("29AAGCB7383J1Z4") and not gstin_ok("29AAGCB7383J1Z5")
    a = address_key("Plot No. 14, Mirjole MIDC, Ratnagiri", "415612")
    assert a == address_key("Plot 14, Near Mirjole Road, Ratnagiri", "415 612") == "415612|14|MIRJOLE"
    k = dict((kind, key) for kind, _s, key in keys({"id": "X", "phone": "+91 98200-12345", "email": "A@B.IN",
                                                    "bank_account": "000123456789", "ifsc": "HDFC0001234"}))
    assert k == {"PHONE": "9820012345", "EMAIL": "a@b.in", "BANK": "HDFC:123456789"}
