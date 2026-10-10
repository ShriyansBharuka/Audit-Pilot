"""Engagement-partner actions (06 §9) for the web UI: the token-based entry points. Never an MCP tool.

One sign-off path: this module resolves the partner from their token (identities.json: name + ICAI membership_no,
never typed parameters) and delegates to findings.decide / findings.sign_off, which own the rules (mandatory
comment, balanced AJE, STALE/integrity blockers, FINAL deliverables, signoff_hash, SIGNOFF anchor, SIGNED_OFF event).
The partner token is rejected by the MCP verifier (04 §1), so no agent can reach these decisions.
"""
import json

from app import config, db, evidence, findings, trail

DECISIONS = {"CONFIRM": "CONFIRMED", "REJECT": "REJECTED", "MODIFY": "MODIFIED"}


def identity(token):
    """token -> {principal, role, name, ...}; LookupError when unknown."""
    ids = json.loads(config.IDENTITIES.read_text(encoding="utf-8")) if config.IDENTITIES.exists() else {}
    rec = ids.get((token or "").strip())
    if rec:
        return rec
    from app import accounts                      # web sign-in: a Supabase session token (vault/07 §3b)
    if accounts.looks_like_jwt(token):
        return accounts.identity(token.strip())
    raise LookupError("UNAUTHENTICATED: unknown token")


def _partner(token):
    rec = identity(token)
    if rec["role"] != "engagement_partner":
        raise PermissionError("PERMISSION_DENIED: only the engagement partner may decide findings or sign off")
    return rec


def review_queue(token, status=None):
    """Findings of the engagement (default: all), largest impact first."""
    _partner(token)
    sql, args = "SELECT * FROM findings WHERE engagement_id = ?", [config.ENGAGEMENT_ID]
    if status:
        sql, args = sql + " AND status = ?", args + [status]
    with db.borrow("audit", "engagement_partner") as a:
        return [dict(r) for r in a.execute(sql + " ORDER BY gross_impact_paise DESC, id", args)]


def decide_finding(token, finding_id, decision, note, taxable_impact_paise=None, proposed_aje=None):
    """CONFIRM | REJECT | MODIFY with a mandatory comment (rules in findings.decide)."""
    rec = _partner(token)
    if decision not in DECISIONS:
        raise ValueError("INVALID_ARGUMENT: decision is CONFIRM, REJECT or MODIFY")
    out = findings.decide(finding_id, DECISIONS[decision], (note or "").strip(), rec,
                          impact=taxable_impact_paise, aje_lines=proposed_aje)
    trail.trail(rec["principal"], rec["role"], "partner.decide_finding",
                {"finding_id": finding_id, "decision": decision}, "OK", out, transport="UI")
    return out


def blockers():
    """What still prevents sign-off (the same checks findings.sign_off enforces)."""
    eid = config.ENGAGEMENT_ID
    with db.borrow("audit", "engagement_partner") as a:
        if a.execute("SELECT 1 FROM engagements WHERE id = ?", (eid,)).fetchone() is None:
            return ["no engagement yet (the client hasn't uploaded a register)"]
        proposed = a.execute("SELECT count(*) FROM findings WHERE engagement_id = ? AND status = 'PROPOSED'",
                             (eid,)).fetchone()[0]
        stale_concl = a.execute("SELECT count(*) FROM samples s JOIN sample_runs r ON r.id = s.run_id WHERE"
                                " r.engagement_id = ? AND s.conclusion_proposed = 'STALE'", (eid,)).fetchone()[0]
    out = [f"{proposed} finding(s) still PROPOSED"] if proposed else []
    stale = len(evidence.check_for_changes(eid).get("stale_samples", [])) + stale_concl
    if stale:
        out.append(f"{stale} STALE sample(s) to re-test")
    if not evidence.verify_integrity(eid).get("ok"):
        out.append("verify_integrity fails")
    return out


def sign_off(token, conclusion):
    """Lock the engagement as the partner on record; the conclusion is kept in the hash-chained trail."""
    rec = _partner(token)
    if not (conclusion or "").strip():
        raise ValueError("INVALID_ARGUMENT: write the partner's conclusion")
    r = findings.sign_off(config.ENGAGEMENT_ID, rec)
    trail.trail(rec["principal"], rec["role"], "partner.conclusion", {"conclusion": conclusion.strip()}, "OK",
                {"signoff_hash": r["signoff_hash"]}, transport="UI")
    return {**r, "signed_by": f"{rec.get('name', rec['principal'])} (ICAI M.No. {rec.get('membership_no', '-')})"}
