"""MT-7 (vault/13): reports A and B render as json / md / html, stay DRAFT before sign-off, never give an opinion, and
every amount row carries the case or finding id it comes from."""
import pytest
from starlette.testclient import TestClient

from app import analytics, cases, config, plants, reports, seed
from app.api_server import app

AUD = {"Authorization": "Bearer aud_test"}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("reports"))
    plan = seed.build_plan(120, 7)
    plants.add_plants(plan, 7)
    ids = seed.load(plan, reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)
    cid = next(c["case_id"] for c in cases.list_cases(limit=100)["items"] if c["root_id"] == ids["PP5/po"])
    cases.act(cid, "PROPOSE_ADJUSTMENT", "accrue", "aud.judge", "audit_staff",
              aje_lines=[{"account_code": "PURCHASES", "dr_paise": 90_000_00},
                         {"account_code": "CREDITORS", "party_id": "P-VEN5", "cr_paise": 90_000_00}])
    yield ids
    config.set_clock(None)
    config.set_data_dir(default)


def _amount_rows(obj):
    """Every dict in the report that carries a non-zero *_paise amount."""
    if isinstance(obj, dict):
        if any(k.endswith("_paise") and isinstance(v, int) and v for k, v in obj.items()):
            yield obj
        for v in obj.values():
            yield from _amount_rows(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _amount_rows(v)


def test_every_amount_traces_to_a_case_or_finding(world):
    for r in (reports.continuous(), reports.year_end()):
        assert r["status"] == "DRAFT" and "does not express an audit opinion" in r["no_opinion"]
        skip = ("sa450",)
        body = {k: v for k, v in r.items() if k not in skip}
        rows = list(_amount_rows(body))
        assert rows
        for row in rows:
            assert row.get("case_id") or row.get("finding_id") or row.get("case_ids"), row
    b = reports.year_end()
    assert any(x["case_id"] and x["finding_id"] for x in b["proposed_ajes"])
    assert {x["attribution"] for x in b["funds_flow"]} == {"NOT_ESTABLISHED"}
    assert len(b["march_april"]) >= 5 and "not a loss" in b["executive_summary"]


def test_formats_and_guards(world):
    api = TestClient(app)
    for path in ("/api/reports/continuous", "/api/reports/year-end"):
        j = api.get(path, headers=AUD)
        assert j.status_code == 200 and j.json()["status"] == "DRAFT"
        md = api.get(path + "?format=md", headers=AUD)
        assert md.status_code == 200 and md.text.startswith("# Report") and "DRAFT" in md.text
        html = api.get(path + "?format=html", headers=AUD)
        assert html.status_code == 200 and "<table>" in html.text and "draft" in html.text
        assert api.get(path + "?format=pdf", headers=AUD).status_code == 400
        assert api.get(path, headers={"Authorization": "Bearer adm_test"}).status_code == 403
