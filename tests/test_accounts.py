"""Web accounts (Supabase): the role never comes from Supabase, only from the organisation's tenant.json. A new account
has no role anywhere until it creates an organisation (becoming its partner) or is invited; an invited client can
upload and enter records but never reach audit endpoints; an outsider cannot open the organisation."""
import hashlib

import pytest
from starlette.testclient import TestClient

from app import accounts, config, seed
from app.api_server import app

USERS = {"eyP.partner.sig": {"id": "u-partner", "email": "partner@firm.in"},
         "eyC.client.sig": {"id": "u-client", "email": "cfo@client.in"},
         "eyO.outsider.sig": {"id": "u-out", "email": "someone@else.in"}}
H = lambda tok, slug=None: {"Authorization": f"Bearer {tok}", **({"X-Tenant": slug} if slug else {})}  # noqa: E731


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    default = config.DATA_DIR
    config.set_data_dir(tmp_path_factory.mktemp("accounts"))
    seed.load(seed.build_plan(60, 7), reset=True)
    mp = pytest.MonkeyPatch()
    mp.setattr(accounts, "verify", lambda token: USERS[token] if token in USERS else (_ for _ in ()).throw(LookupError("x")))
    yield TestClient(app)
    mp.undo()
    config.set_data_dir(default)


def test_new_account_has_no_role(api):
    assert api.get("/api/auth/memberships", headers=H("eyP.partner.sig")).json()["items"] == []
    r = api.get("/api/audit/overview", headers=H("eyP.partner.sig"))
    assert r.status_code == 403 and r.json()["detail"].startswith("NO_ROLE")


def test_onboarding_invite_upload_and_isolation(api):
    r = api.post("/api/onboarding/organization", headers=H("eyP.partner.sig"),
                 json={"name": "Velas Marine Pvt Ltd", "pan": "AAFCS6120R", "gstin": "27AAFCS6120R1ZV", "fy": "2025-26"})
    assert r.status_code == 200, r.text
    slug = r.json()["slug"]
    assert api.get("/api/auth/memberships", headers=H("eyP.partner.sig")).json()["items"] == [
        {"slug": slug, "name": "Velas Marine Pvt Ltd", "role": "engagement_partner"}]
    assert api.get("/api/audit/overview", headers=H("eyP.partner.sig", slug)).status_code == 200
    # a bad PAN/GSTIN is refused
    bad = api.post("/api/onboarding/organization", headers=H("eyP.partner.sig"),
                   json={"name": "Bad Co", "pan": "XYZ", "gstin": "27AAFCS6120R1ZV", "fy": "2025-26"})
    assert bad.status_code == 400

    # the partner invites the client's CFO; the role applies at the CFO's first request
    assert api.post(f"/api/tenants/{slug}/invites", headers=H("eyP.partner.sig"),
                    json={"email": "CFO@client.in", "role": "client_admin"}).status_code == 200
    assert api.get("/api/auth/memberships", headers=H("eyC.client.sig")).json()["items"][0]["role"] == "client_admin"
    # the client cannot invite, and cannot reach audit endpoints
    assert api.post(f"/api/tenants/{slug}/invites", headers=H("eyC.client.sig"),
                    json={"email": "x@y.in", "role": "engagement_partner"}).status_code == 403
    assert api.get("/api/audit/overview", headers=H("eyC.client.sig", slug)).status_code == 403

    # the client uploads the related-party list: stored as sent, server-computed SHA-256
    csv = b"Name,PAN,GSTIN,Relation,Effective From,Effective To\nDesai Hydraulics Pvt Ltd,AAACD1234E,,director,2018-04-01,\n"
    up = api.post("/api/client/related-parties", headers=H("eyC.client.sig", slug),
                  files={"file": ("rp.csv", csv, "text/csv")})
    assert up.status_code == 200, up.text
    assert up.json()["sha256"] == hashlib.sha256(csv).hexdigest()

    # manual entry through the ERP service (role rules of the client tools)
    party = api.post("/api/client/records/party", headers=H("eyC.client.sig", slug),
                     json={"name": "Coastal Dredgers Pvt Ltd", "tags": "CUSTOMER", "gstin": "27AAPFU0939F1ZV"})
    assert party.status_code == 200, party.text
    assert party.json()["result"]["id"]
    item = api.post("/api/client/records/item", headers=H("eyC.client.sig", slug),
                    json={"name": "Ball valve DN25", "hsn": "8481", "gst_rate_bp": 1800, "list_rate": "4500.00"})
    assert item.status_code == 200, item.text
    inv = api.post("/api/client/records/invoice", headers=H("eyC.client.sig", slug),
                   json={"party_id": party.json()["result"]["id"], "series": "G2", "invoice_date": "2026-03-20",
                         "lines": [{"item_id": item.json()["result"]["id"], "qty": 2, "rate": "4500.00"}]})
    assert inv.status_code == 200, inv.text
    assert api.post("/api/client/records/nonsense", headers=H("eyC.client.sig", slug), json={}).status_code == 404
    # internal service arguments are refused (the web gets the MCP tool's parameters only)
    assert api.post("/api/client/records/party", headers=H("eyC.client.sig", slug),
                    json={"name": "X Traders", "id": "P-9999"}).status_code == 400

    # an outsider can neither open the organisation nor see it
    assert api.get("/api/audit/overview", headers=H("eyO.outsider.sig", slug)).status_code == 403
    assert api.get("/api/auth/memberships", headers=H("eyO.outsider.sig")).json()["items"] == []


def test_same_first_word_orgs_keep_their_own_roles(api):
    # "Velas Logistics" shares the "velas" stem with "Velas Marine": distinct engagement ids, and each partner is
    # partner in their own organisation only (the bug: the role was looked up in the first org with that stem)
    r = api.post("/api/onboarding/organization", headers=H("eyO.outsider.sig"),
                 json={"name": "Velas Logistics Pvt Ltd", "pan": "AAFCS6120R", "gstin": "27AAFCS6120R1ZV", "fy": "2025-26"})
    assert r.status_code == 200, r.text
    mine = r.json()
    others = [m for m in api.get("/api/tenants", headers=H("eyO.outsider.sig", mine["slug"])).json()["items"]]
    assert [o["slug"] for o in others] == [mine["slug"]] and others[0]["active"]
    login = api.post("/api/auth/token-login", headers=H("eyO.outsider.sig", mine["slug"]), json={"token": "eyO.outsider.sig"})
    assert login.json()["role"] == "engagement_partner"
    assert api.get("/api/audit/overview", headers=H("eyO.outsider.sig", mine["slug"])).status_code == 200
    velas_marine = api.get("/api/auth/memberships", headers=H("eyP.partner.sig")).json()["items"][0]
    assert velas_marine["slug"] != mine["slug"]
    from app import tenants
    assert tenants.get(velas_marine["slug"])["engagement_id"] != tenants.get(mine["slug"])["engagement_id"]
    # organisations created before the fix can still share an id on disk: the role must still resolve per organisation
    t = tenants.get(mine["slug"])
    t["engagement_id"] = tenants.get(velas_marine["slug"])["engagement_id"]
    accounts._save(t)
    login = api.post("/api/auth/token-login", headers=H("eyO.outsider.sig", mine["slug"]), json={"token": "eyO.outsider.sig"})
    assert login.json()["role"] == "engagement_partner"


def test_agent_tokens_unchanged(api):
    # judge/agent tokens keep their identities.json role on the default tenant
    assert api.get("/api/audit/overview", headers=H("aud_test")).status_code == 200
