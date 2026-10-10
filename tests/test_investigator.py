"""Investigator guard rails (10 §4): pricing, caps, off-by-default. No network, no API key needed."""
import types

import pytest

from app import config, investigator


def test_cost_math_per_model():
    # 40k input of which 24k cached + 5k output on GPT-6 Astra: 16k*$10 + 24k*$1 + 5k*$50 per 1M = $0.434
    assert investigator.CostMeter.cost_micros("gpt-6-astra", 40_000, 24_000, 5_000) == 434_000
    assert investigator.CostMeter.cost_micros("gpt-6.1-sol", 40_000, 24_000, 5_000) == 84_400
    assert investigator.CostMeter.cost_micros("gpt-6-luna", 40_000, 24_000, 5_000) == 4_340
    assert investigator.CostMeter.cost_micros("some-new-model", 1_000_000, 0, 0) == 10_000_000  # priced safe-side


def test_day_cap_refuses(world, monkeypatch):
    m = investigator.CostMeter(run_cap_usd="3", day_cap_usd="5")
    usage = types.SimpleNamespace(input_tokens=200_000, output_tokens=40_000,
                                  input_tokens_details=types.SimpleNamespace(cached_tokens=0))
    m.check()                                            # nothing spent yet
    m.add(usage, "gpt-6-astra", "test")                  # $2 + $2 = $4 spent today
    with pytest.raises(RuntimeError, match="day cap"):
        m.check()                                        # 4 + 3 (next run's cap) > 5


def test_off_by_default(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    ok, why = investigator.ready()
    assert not ok and "LLM_ENABLED" in why


# ---------------------------------------------------------------- MT-5 multi-agent case investigation (no network)

@pytest.fixture(scope="module")
def case_world(tmp_path_factory):
    from app import analytics, plants, seed
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("inv"))
    plan = seed.build_plan(120, 7)
    plants.add_plants(plan, 7)
    ids = seed.load(plan, reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)
    from app import cases
    cid = next(c["case_id"] for c in cases.list_cases(limit=100)["items"] if c["root_id"] == ids["PP1/po"])
    yield ids, cid
    config.set_clock(None)
    config.set_data_dir(default)


def test_case_investigation_keeps_amounts_deterministic(case_world):
    import asyncio
    from app import cases, gateway, mcp_server  # noqa: F401  (registers the tools)
    ids, cid = case_world
    seen = {}
    usage = types.SimpleNamespace(input_tokens=3_000, output_tokens=400,
                                  input_tokens_details=types.SimpleNamespace(cached_tokens=0))

    async def fake(name, instructions, text, model, tools, token, output_type=None):
        seen[name] = tools
        if output_type is None:
            return f"{name}: PO {ids['PP1/po']} paid 9,99,999 (model arithmetic, ignored)", usage, 2
        return investigator.CaseInvestigation(
            facts=[investigator.Fact(text="advance paid, 60 of 100 received", record_ids=[ids["PP1/po"]]),
                   investigator.Fact(text="an invented record", record_ids=["INV-999999"])],
            discrepancies=["billed 100, received 60"], missing_evidence=["GRN for 40 units"],
            open_questions=["where are the other 40 units?"], conclusion="UNRESOLVED",
            suggested_action="request proof of delivery"), usage, 0

    r = asyncio.run(investigator.investigate_case(cid, model="gpt-6.1-sol", run=fake))
    inv = r["investigation"]
    assert set(seen) == {"risk", "evidence", "money_flow", "reporting"} and seen["reporting"] == []
    read_only = {"get_case", "list_audit_items", "get_risk_graph", "trace_sale", "query_records", "run_readonly_sql",
                 "trace_money"}
    for name in ("risk", "evidence", "money_flow"):
        assert set(seen[name]) <= read_only and all("audit_staff" in gateway.TOOL_ROLES[t] for t in seen[name])
    assert inv["amounts"]["verified_paise"] == 5_00_000_00 and inv["amounts"]["affected_paise"] == 2_00_000_00
    assert inv["amounts"]["claimed_paise"] == 5_00_000_00 and inv["status"] == "PROPOSED"
    assert inv["unverified_ids"] == ["INV-999999"] and inv["conclusion"] == "UNRESOLVED"
    assert r["usd"] < 0.10 and r["tool_calls"] == 6
    d = cases.get_case(cid)
    assert d["investigation"]["conclusion"] == "UNRESOLVED" and d["history"][-1]["action"] == "AI_INVESTIGATION"
    assert d["case"]["status"] == "OPEN"                         # an AI run never decides anything


def test_investigate_endpoint_guards(case_world, monkeypatch):
    from starlette.testclient import TestClient
    from app.api_server import app
    _, cid = case_world
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    api = TestClient(app)
    r = api.post(f"/api/cases/{cid}/investigate", headers={"Authorization": "Bearer aud_test"})
    assert r.status_code == 409 and "LLM_OFF" in r.json()["detail"]
    assert api.post(f"/api/cases/{cid}/investigate", headers={"Authorization": "Bearer adm_test"}).status_code == 403
    assert api.post("/api/cases/AUD-9999/investigate", headers={"Authorization": "Bearer aud_test"}).status_code == 404
