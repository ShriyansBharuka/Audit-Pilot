import json
import re
from collections import Counter
from datetime import date

import pytest

from app import seed

C = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def gstin_ok(g):  # 05 D1, verbatim
    if not re.fullmatch(r'\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]', g or ''): return False
    t = 0
    for i, ch in enumerate(g[:14]):
        p = C.index(ch) * (2 if i % 2 else 1); t += p // 36 + p % 36
    return C[(36 - t % 36) % 36] == g[14]


@pytest.fixture(scope="module")
def plan():
    return seed.build_plan(300, 7)


def test_check_char_matches_published_gstins():
    for g in ("27AAPFU0939F1ZV", "29AAGCB7383J1Z4"):
        assert seed.gstin_check_char(g[:14]) == g[14]


def test_same_seed_same_company(plan):
    assert json.dumps(seed.build_plan(300, 7)) == json.dumps(plan)
    assert json.dumps(seed.build_plan(300, 8)) != json.dumps(plan)


def test_masters(plan):
    parties = plan["parties"]
    tags = Counter(p["tags"] for p in parties)
    assert tags["SELF"] == 1 and tags["CUSTOMER"] == 150
    assert tags["DIRECTOR"] == 4 and tags["KMP"] == 2 and tags["RELATIVE"] == 4
    assert tags["TRANSPORTER"] >= 3 and tags["VENDOR"] >= 3
    ids = {it["id"] for it in plan["items"]}
    assert {"CHG-PACKING", "CHG-FREIGHT", "CHG-INSURANCE"} <= ids
    assert sum(1 for i in ids if i.startswith("IT-")) >= 40
    assert any(it["hsn"].startswith("99") for it in plan["items"] if it["id"].startswith("IT-"))
    by_id = {p["id"]: p for p in parties}
    for ln in plan["links"]:
        assert ln["from_party"] in by_id and ln["to_party"] in by_id


def test_identifiers_valid_and_consistent(plan):
    for u in plan["units"].values():
        assert gstin_ok(u["gstin"]) and u["gstin"][:2] == u["state_code"]
    for p in plan["parties"]:
        if p["gstin"]:
            assert gstin_ok(p["gstin"]), p["id"]
            assert p["gstin"][2:12] == p["pan"], p["id"]          # clean data: no PAN_GSTIN_MISMATCH
            assert p["gstin"][:2] == p["state_code"], p["id"]     # clean data: no GSTIN_STATE_MISMATCH
    pans = [p["pan"] for p in plan["parties"] if p["pan"] and p["id"] != "SELF"]
    banks = [p["bank_account"] for p in plan["parties"] if p["bank_account"]]
    assert len(pans) == len(set(pans)) and len(banks) == len(set(banks))   # no accidental STRONG edges


def test_only_designed_phone_sharing(plan):
    reg = plan["regressions"][0]
    assert reg["kind"] == "SHARED_SERVICE_PHONE" and len(reg["party_ids"]) == 6
    phones = Counter(p["phone"] for p in plan["parties"] if p["phone"])
    assert [ph for ph, n in phones.items() if n > 1] == [reg["phone"]]


def test_no_floats_anywhere(plan):
    def walk(x):
        assert not isinstance(x, float), x
        if isinstance(x, dict): [walk(v) for v in x.values()]
        if isinstance(x, list): [walk(v) for v in x]
    walk(plan)


def test_sales_clean_and_in_range(plan):
    fy_end = date(2026, 3, 31)
    fy = [s for s in plan["sales"] if date.fromisoformat(s["invoice_date"]) <= fy_end]
    post = [s for s in plan["sales"] if date.fromisoformat(s["invoice_date"]) > fy_end]
    assert len(fy) == 300 and len(post) >= 15                      # cut-off needs the first 15 after
    units = Counter(s["unit"] for s in plan["sales"])
    assert units["G2"] and units["G11"]
    for s in plan["sales"]:
        d = date.fromisoformat(s["invoice_date"])
        assert date(2025, 4, 1) <= d <= date(2026, 5, 31) and d.weekday() != 6
        assert s["so"]["enquired_on"] < s["so"]["quoted_on"] <= s["so"]["confirmed_on"] < s["invoice_date"]
        assert s["total_paise"] == s["taxable_paise"] + s["tax_paise"] > 0
        if s["is_service"]:
            assert s["dispatch"] is None and all(not ln["item_id"].startswith("CHG") for ln in s["lines"])
            continue
        moved = date.fromisoformat(s["dispatch"]["moved_on"])
        delivered = date.fromisoformat(s["delivery"]["delivered_on"])
        assert 0 <= (moved - d).days <= 1 and delivered >= moved
        assert s["ewb"] == (s["total_paise"] > seed.EWB_THRESHOLD_PAISE)
        if d <= fy_end:                                            # no accidental D3 PREMATURE in clean data
            assert moved <= fy_end
            if s["so"]["delivery_terms"] == "FOR_DESTINATION":
                assert delivered <= fy_end


def test_events_replay_in_dependency_order(plan):
    evs = plan["events"]
    assert [e["at"] for e in evs] == sorted(e["at"] for e in evs)
    produced = set()
    for e in evs:
        for ref in e["refs"].values():
            assert ref in produced, (e["service"], ref)
        if e["out"]:
            produced.add(e["out"][0])
    assert Counter(e["service"] for e in evs)["issue_invoice"] == len(plan["sales"])
    assert min(e["at"] for e in evs) > seed.MASTERS_AT


def test_identities_cover_every_role():
    ids = seed.make_identities()
    roles = Counter(i["role"] for i in ids.values())
    assert set(roles) == {"sales", "warehouse", "accounts", "client_admin", "audit_staff", "orchestrator",
                          "engagement_partner"}
    prefix = {r: p for r, p, _, _ in seed.ROLES}
    for tok, i in ids.items():
        assert tok.startswith(prefix[i["role"]]) and len(tok) > 30
    partner = next(i for i in ids.values() if i["role"] == "engagement_partner")
    assert partner["membership_no"]
    assert "web UI only" in seed.judge_card(ids)
