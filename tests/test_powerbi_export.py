"""EX-1: the Power BI package (4 CSVs + DAX), integer paise, referential integrity, formula-injection guard."""
import csv
import io
import zipfile

import pytest
from starlette.testclient import TestClient

from app import analytics, config, erp, plants, powerbi, seed
from app.api_server import app

AUD = {"Authorization": "Bearer aud_test"}
FILES = {"Fact_Invoices.csv", "Dim_Customers.csv", "Dim_Detectors.csv", "Fact_Findings_AJEs.csv", "measures.dax"}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("powerbi"))
    plan = seed.build_plan(120, 7)
    plants.add_plants(plan, 7)
    seed.load(plan, reset=True)
    config.set_clock("2026-04-02T10:00:00+05:30")
    erp.create_party("sales.priya", "sales", name="=HYPERLINK(\"http://x\",\"ok\")", gstin="27AAPFU0939F1ZV")
    config.set_clock("2026-10-05T10:00:00+05:30")
    analytics.run_all(config.ENGAGEMENT_ID)
    from app import findings
    findings.from_hits(config.ENGAGEMENT_ID)
    yield
    config.set_clock(None)
    config.set_data_dir(default)


def _read(z, name):
    return list(csv.DictReader(io.StringIO(z.read(name).decode("utf-8-sig"))))


def test_package_files_keys_and_paise(world):
    data, name = powerbi.package()
    z = zipfile.ZipFile(io.BytesIO(data))
    assert set(z.namelist()) == FILES and name.endswith(".zip")
    inv, cust = _read(z, "Fact_Invoices.csv"), _read(z, "Dim_Customers.csv")
    assert inv and cust
    assert {r["party_id"] for r in inv} <= {r["party_id"] for r in cust}       # every fact key has a dimension row
    for r in inv:
        for col in ("taxable_paise", "tax_paise", "total_paise", "risk_score"):
            assert r[col].lstrip("-").isdigit(), (col, r[col])                   # integers, never 1234.5
        assert int(r["total_paise"]) - int(r["taxable_paise"]) - int(r["tax_paise"]) in range(-100, 101)
    fa = _read(z, "Fact_Findings_AJEs.csv")
    assert fa and all(r[c].isdigit() for r in fa for c in ("impact_paise", "aje_debit_paise", "aje_credit_paise"))
    for fid in {r["finding_id"] for r in fa}:                                     # each finding's AJE lines balance
        lines = [r for r in fa if r["finding_id"] == fid]
        assert sum(int(r["aje_debit_paise"]) for r in lines) == sum(int(r["aje_credit_paise"]) for r in lines)
    det = _read(z, "Dim_Detectors.csv")
    assert {r["detector_id"] for r in det} >= {"D0", "D3", "D10", "D15"}
    measures = z.read("measures.dax").decode()
    for m in ("Total Revenue", "Materiality Threshold", "Flagged Fraud Volume", "Cut-off Error %", "RP Exposure %"):
        assert m + " =" in measures


def test_formula_injection_guard(world):
    assert powerbi.safe("=1+1") == "'=1+1" and powerbi.safe("+91 98") == "'+91 98" and powerbi.safe("-x") == "'-x"
    assert powerbi.safe("@SUM(A1)") == "'@SUM(A1)" and powerbi.safe("Konkan") == "Konkan" and powerbi.safe(-5) == -5
    z = zipfile.ZipFile(io.BytesIO(powerbi.package()[0]))
    names = [r["name"] for r in _read(z, "Dim_Customers.csv")]
    assert any(n.startswith("'=HYPERLINK") for n in names) and not any(n.startswith("=") for n in names)


def test_rest_feed_alias_and_guards(world):
    api = TestClient(app)
    a = api.get("/api/integrations/powerbi", headers=AUD).json()
    b = api.get("/api/v1/powerbi/feed", headers=AUD).json()
    assert a["money_unit"] == "paise" and {k: v for k, v in a.items() if k != "generated_at"} == \
        {k: v for k, v in b.items() if k != "generated_at"}
    assert all(isinstance(i["total_paise"], int) for i in a["invoices"])
    r = api.get("/api/integrations/powerbi/package", headers=AUD)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert set(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == FILES
    for path in ("/api/integrations/powerbi/package", "/api/v1/powerbi/feed"):
        assert api.get(path, headers={"Authorization": "Bearer adm_test"}).status_code == 403
