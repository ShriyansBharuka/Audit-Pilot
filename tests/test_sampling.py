"""07 §8.3: same seed + population -> identical picks; size 25-35; >= 3 RP; <= 3 per customer; every pick has a
reason; reproduce_selection identical; the first selection starts testing and sends requests (no reasons)."""
import random
from collections import Counter

import pytest

from app import analytics, config, db, erp, intake, sampling, seed


def pop_fixture(n=400, n_rp=12, seed_=3):
    rng = random.Random(seed_)
    pop = []
    for i in range(n):
        m = 4 + int(rng.random() * 12)
        y, mo = (2025, m) if m <= 12 else (2026, m - 12)
        pop.append({"id": f"INV-{i:06d}", "no": f"G2/{i:04d}/25", "date": f"{y}-{mo:02d}-15",
                    "party": f"P-{int(rng.random() * 40):04d}", "unit": "G2" if rng.random() < 0.7 else "G11",
                    "taxable": int(rng.random() * 50_00_000_00) + 1, "row": i + 1,
                    "rp": i < n_rp, "rp_status": "DECLARED_RP" if i < n_rp else "NRP",
                    "points": 0, "max_sev": 0, "impact": 0, "codes": []})
    for p in pop[100:105]:                                       # five analytics hits for the KEY stratum
        p.update(points=5, max_sev=5, impact=p["taxable"], codes=["NO_MOVEMENT"])
    return pop


def test_pps_uses_only_rng_random_and_is_deterministic():
    items = [(f"I{i}", w) for i, w in enumerate([5, 1, 1, 8, 2, 3, 9, 1])]
    assert sampling.pps(items, 3, random.Random(7)) == sampling.pps(items, 3, random.Random(7))
    assert len(sampling.pps(items, 3, random.Random(7))) <= 3


def test_sales_selection_rules():
    pop = pop_fixture()
    a = sampling.select_sales(pop, 30, "12345", 10**15)
    assert a == sampling.select_sales(pop, 30, "12345", 10**15)                 # same seed + population
    assert a != sampling.select_sales(pop, 30, "54321", 10**15)                 # the seed matters
    assert len(a) == 30 and len({p["id"] for p in a}) == 30
    strata = Counter(p["stratum"] for p in a)
    assert strata["KEY"] == 5 and strata["RP"] + sum(1 for p in a if p["id"] < "INV-000012") >= 3
    parties = Counter(next(q["party"] for q in pop if q["id"] == p["id"]) for p in a)
    assert max(parties.values()) <= 3
    assert all(p["reason"] and p["reason"].startswith(p["stratum"]) for p in a)
    by = {q["id"]: q for q in pop}
    assert {by[p["id"]]["unit"] for p in a} == {"G2", "G11"}
    assert len({sampling._quarter(by[p["id"]]["date"]) for p in a}) == 4


def test_cutoff_selection_takes_10_before_15_after():
    pop = [{"id": f"I{i:03d}", "no": f"G2/{i:04d}/25", "date": d, "codes": []}
           for i, d in enumerate(sorted([f"2026-03-{x:02d}" for x in range(5, 32)] + [f"2026-04-{x:02d}" for x in range(1, 25)]))]
    pop[3]["codes"] = ["PREMATURE"]
    picks = sampling.select_cutoff(pop, "2026-03-31")
    s = Counter(p["stratum"] for p in picks)
    assert s["CUTOFF_BEFORE"] == 10 and s["CUTOFF_AFTER"] == 15 and s["ANALYTICS"] == 1


@pytest.fixture()
def engaged(world):
    plan = seed.build_plan(150, 7)
    seed.load(plan, reset=True)
    config.set_clock("2026-04-10T11:00:00+05:30")
    erp.issue_credit_note("acc.neha", "accounts", cn_date="2026-04-10", reason="RATE_DIFF",
                          lines=[{"invoice_no": "G2/0001/25", "taxable_paise": 100000}])
    config.set_clock("2026-10-05T10:00:00+05:30")
    exp = erp.export_sales_register("acc.neha", "accounts")["result"]
    content, name = intake.build_register(exp["export_id"])
    intake.on_client_upload(intake.submit("SALES_REGISTER", content, name, "acc.neha"))
    analytics.run_all(config.ENGAGEMENT_ID)
    return plan


def test_select_starts_testing_reproduces_and_requests(engaged):
    r = sampling.select(config.ENGAGEMENT_ID, "sales_tod", size=30, actor="aud.judge")
    assert r["size"] == 30 and r["seed"].isdigit() and all(i["reason"] for i in r["items"])
    assert sum(1 for i in r["items"] if i["stratum"] == "RP") + r["strata"].get("KEY", 0) >= 3
    assert sampling.reproduce(r["run_id"])["identical"] is True
    with db.borrow("audit", "audit_staff") as a:
        eng = a.execute("SELECT * FROM engagements").fetchone()
        assert eng["status"] == "TESTING" and eng["testing_started_seq"] > 0
        assert [x[0] for x in a.execute("SELECT label FROM anchors ORDER BY id")][-1] == "TESTING_START"
        assert a.execute("SELECT count(*) FROM samples WHERE run_id = ?", (r["run_id"],)).fetchone()[0] == 30
    with db.borrow("pbc", "accounts") as p:
        reqs = [dict(x) for x in p.execute("SELECT * FROM evidence_requests")]
    assert len(reqs) == r["requests_sent"] >= 30 and {q["doc_kind"] for q in reqs} >= {"INVOICE", "LR", "POD"}
    assert all(q["sample_ref"].startswith("S-") for q in reqs)
    assert not any(k in reqs[0] for k in ("reason", "stratum"))                 # the client never sees why
    first = r["run_id"]
    c = sampling.select(config.ENGAGEMENT_ID, "cutoff")
    s = Counter(i["stratum"] for i in c["items"])
    assert s["CUTOFF_BEFORE"] == 10 and s["CUTOFF_AFTER"] == 15          # the first 15 after, even beyond 30 days
    assert sampling.reproduce(c["run_id"])["identical"]
    n = sampling.select(config.ENGAGEMENT_ID, "credit_note")
    assert [i["stratum"] for i in n["items"]] == ["CN_POST_PERIOD"]
    with pytest.raises(ValueError, match="25 to 35"):
        sampling.select(config.ENGAGEMENT_ID, "sales_tod", size=40)
    again = sampling.select(config.ENGAGEMENT_ID, "sales_tod", seed=r["seed"])     # a judge re-running with the seed
    assert [i["doc_id"] for i in again["items"]] == [i["doc_id"] for i in r["items"]] and again["run_id"] != first
