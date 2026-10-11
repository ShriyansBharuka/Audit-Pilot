"""DEMO-SEED: the demo seeder builds an organisation through REST + MCP in-process (Supabase faked): roles come from
tenant.json, every planted irregularity becomes a finding, about half the evidence requests are answered, and a
second run changes nothing."""
import importlib.util
from collections import Counter

from starlette.testclient import TestClient

from app import accounts, config, tenants

spec = importlib.util.spec_from_file_location("demo_seed", config.ROOT / "scripts" / "demo_seed.py")
demo_seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo_seed)


def test_demo_seed_one_organisation(world, monkeypatch):
    users = {}                                               # e-mail -> fake Supabase session token

    def sign_in(email, password):
        return users.setdefault(email, f"eyD{len(users)}.demo.sig")

    def verify(token):
        for email, t in users.items():
            if t == token:
                return {"id": f"u-{email}", "email": email}
        raise LookupError("UNAUTHENTICATED")

    monkeypatch.setattr(accounts, "verify", verify)
    import app.serve as serve
    with TestClient(serve.app, base_url="http://localhost:8000") as client:
        api = demo_seed.Api(client, "/mcp", clock=config.set_clock)
        try:
            first = demo_seed.run(api, sign_in=sign_in, only=["arnav"])[0]
            again = demo_seed.run(api, sign_in=sign_in, only=["arnav"])[0]
        finally:
            config.set_clock(None)
        # the judge walkthrough: the partner decides every finding and signs off in the web app (REST)
        ptn, slug = users["partner.arnav@example.com"], first["slug"]
        for f in api.get("/api/audit/findings", ptn, slug):
            api.post(f"/api/audit/findings/{f['id']}/decide", ptn, slug,
                     json={"decision": "CONFIRM", "note": "Agreed after review of the evidence."})
        assert api.get("/api/audit/signoff-blockers", ptn, slug) == []
        signed = api.post("/api/audit/sign-off", ptn, slug, json={"statement": "Reviewed.", "password": "x"})
        assert len(signed["signoff_hash"]) == 64

    missing = [c for c in demo_seed.EXPECTED if c not in first["codes"]]
    assert not missing, first["codes"]
    assert 0 < first["evidence_received"] <= (first["evidence_requests"] + 1) // 2
    assert again == first                                    # idempotent: the organisation is left as it was
    t = tenants.get(first["slug"])
    assert Counter(t["roles"].values()) == {"engagement_partner": 1, "audit_staff": 1, "client_admin": 1,
                                            "accounts": 2, "sales": 2, "warehouse": 1}
    assert not t.get("invites")                              # every invite was taken up
