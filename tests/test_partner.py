"""Partner review + sign-off (06 §9) and the explorer's audit-only reads. UI-only actions, human-only decisions."""
import json

import pytest

from app import chain, config, db, explorer, partner

PTN, AUD = "ptn_test", "aud_test"


@pytest.fixture()
def eng(world, tmp_path, monkeypatch):
    ids = tmp_path / "identities.json"
    ids.write_text(json.dumps({PTN: {"principal": "ptn.t", "role": "engagement_partner", "name": "CA Test",
                                     "membership_no": "123456"},
                               AUD: {"principal": "aud.t", "role": "audit_staff", "name": "Auditor"}}))
    monkeypatch.setattr(config, "IDENTITIES", ids)
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute("INSERT INTO engagements(id, entity_name, period_start, period_end) VALUES (?,?,?,?)",
                  (config.ENGAGEMENT_ID, "Test Co", "2025-04-01", "2026-03-31"))
        a.execute("INSERT INTO findings(id, engagement_id, category, title, explanation, confidence, prepared_by,"
                  " prepared_at) VALUES ('F-001', ?, 'CUTOFF', 't', 'e', 'HIGH', 'aud.t', ?)",
                  (config.ENGAGEMENT_ID, config.now()))
    return world


def test_only_the_partner_decides(eng):
    with pytest.raises(PermissionError):
        partner.decide_finding(AUD, "F-001", "CONFIRM", "ok")
    with pytest.raises(LookupError):
        partner.review_queue("nobody")
    with pytest.raises(ValueError, match="comment is mandatory"):
        partner.decide_finding(PTN, "F-001", "CONFIRM", "  ")
    with pytest.raises(ValueError, match="must balance"):
        partner.decide_finding(PTN, "F-001", "MODIFY", "x", proposed_aje=[{"dr_paise": 5}, {"cr_paise": 4}])


def test_sign_off_blocked_until_decided_then_locks(eng):
    with pytest.raises(ValueError, match="still PROPOSED"):
        partner.sign_off(PTN, "conclusion")
    assert partner.decide_finding(PTN, "F-001", "CONFIRM", "agreed")["status"] == "CONFIRMED"
    r = partner.sign_off(PTN, "Revenue fairly stated.")
    assert "123456" in r["signed_by"] and len(r["signoff_hash"]) == 64 and r["anchor"]["label"] == "SIGNOFF"
    with pytest.raises(Exception):
        partner.decide_finding(PTN, "F-001", "REJECT", "too late")
    with db.borrow("audit", "system") as a:
        assert a.execute("SELECT status FROM engagements").fetchone()[0] == "SIGNED_OFF"
        assert chain.verify(a, "audit_trail")["valid"]
        tools = [r[0] for r in a.execute("SELECT tool FROM audit_trail WHERE transport = 'UI'")]
    assert tools == ["partner.decide_finding", "partner.sign_off"]


def test_explorer_is_audit_only(eng):
    with pytest.raises(PermissionError):
        explorer.risk_history("client_admin", "INVOICE", "X")
    assert explorer.risk_history("audit_staff", "INVOICE", "X") == []
    assert explorer.evidence_for("audit_staff", "G2/0001/25") == []
