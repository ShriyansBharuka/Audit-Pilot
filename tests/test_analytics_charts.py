"""EX-2: Benford maths, the spike z-score, and the charts endpoint on a seeded year."""
import math

import pytest
from starlette.testclient import TestClient

from app import analytics, charts, config, plants, seed
from app.api_server import app


def test_benford_expected_sums_to_one_and_chi2_behaves():
    b = analytics.benford([1])
    assert abs(sum(b["expected"].values()) - 1) < 1e-12
    perfect = [d * 10 ** 5 for d in range(1, 10) for _ in range(round(100_000 * math.log10(1 + 1 / d)))]
    bp = analytics.benford(perfect)
    assert bp["chi2"] < 0.05 and not bp["flagged"]
    uniform = [d * 10 ** 5 for d in range(1, 10) for _ in range(1000)]
    bu = analytics.benford(uniform)
    assert bu["chi2"] > 1000 and bu["flagged"]


def test_spike_day_gets_z_at_least_3():
    rows = [(f"2026-01-{d:02d}", 100_000_00 + (d % 3) * 1_000_00) for d in range(1, 31)]
    rows += [("2026-03-30", 9_00_000_00)]
    v = charts.daily_volume(rows, "2026-03-31")
    spike = next(d for d in v["days"] if d["date"] == "2026-03-30")
    assert spike["z"] >= 3 and spike["flagged"] and spike["period_end_window"]
    assert not any(d["flagged"] for d in v["days"] if d["date"] != "2026-03-30")
    assert isinstance(v["mean_paise"], int) and all(isinstance(d["total_paise"], int) for d in v["days"])


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("charts"))
    plan = seed.build_plan(150, 7)
    plants.add_plants(plan, 7)
    seed.load(plan, reset=True)
    config.set_clock("2026-10-05T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)
    yield
    config.set_clock(None)
    config.set_data_dir(default)


def test_charts_endpoint(world):
    api = TestClient(app)
    r = api.get("/api/audit/analytics/charts", headers={"Authorization": "Bearer aud_test"})
    assert r.status_code == 200
    c = r.json()
    assert len(c["benford"]["digits"]) == 9 and c["benford"]["n"] > 0
    assert c["volume"]["days"] and any(d["period_end_window"] for d in c["volume"]["days"])
    assert sum(h["count"] for h in c["risk"]["histogram"]) == c["risk"]["scatter_total"]
    assert c["risk"]["scatter_shown"] <= charts.SCATTER_CAP
    assert any(p["risk_score"] >= 70 for p in c["risk"]["scatter"])
    assert api.get("/api/audit/analytics/charts", headers={"Authorization": "Bearer adm_test"}).status_code == 403
