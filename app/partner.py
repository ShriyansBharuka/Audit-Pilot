"""Engagement-partner actions (06 §9): decide each finding, then sign off. Web UI only; never an MCP tool.

The partner token is rejected by the MCP verifier (04 §1), so the human decision can't be taken by an agent.
Identity comes from identities.json (name + ICAI membership_no), never from typed parameters. Every action is a
hash-chained audit_trail row (transport UI). Sign-off is refused while a finding is PROPOSED, a sample is stale or
integrity fails; on success it stores signoff_hash, writes a SIGNOFF anchor and emits SIGNED_OFF.
"""
import hashlib
import json

from app import chain, config, db, evidence, memo, notify, trail, workpaper

DECISIONS = {"CONFIRM": "CONFIRMED", "REJECT": "REJECTED", "MODIFY": "MODIFIED"}


def identity(token):
    """token -> {principal, role, name, ...}; LookupError when unknown."""
    ids = json.loads(config.IDENTITIES.read_text(encoding="utf-8")) if config.IDENTITIES.exists() else {}
    rec = ids.get((token or "").strip())
    if not rec:
        raise LookupError("UNAUTHENTICATED: unknown token")
    return rec


def _partner(token):
    rec = identity(token)
    if rec["role"] != "engagement_partner":
        raise PermissionError("PERMISSION_DENIED: only the engagement partner may decide findings or sign off")
    return rec


def review_queue(token, status=None):
    """Findings of the engagement (default: all), newest decisions last."""
    _partner(token)
    sql, args = "SELECT * FROM findings WHERE engagement_id = ?", [config.ENGAGEMENT_ID]
    if status:
        sql, args = sql + " AND status = ?", args + [status]
    with db.borrow("audit", "engagement_partner") as a:
        return [dict(r) for r in a.execute(sql + " ORDER BY gross_impact_paise DESC, id", args)]


def decide_finding(token, finding_id, decision, note, taxable_impact_paise=None, proposed_aje=None):
    """CONFIRM | REJECT | MODIFY with a mandatory comment. MODIFY may change the taxable impact and/or AJE lines."""
    rec = _partner(token)
    if decision not in DECISIONS:
        raise ValueError("INVALID_ARGUMENT: decision is CONFIRM, REJECT or MODIFY")
    if not (note or "").strip():
        raise ValueError("INVALID_ARGUMENT: a comment is mandatory for every decision (SA 230)")
    if proposed_aje is not None and sum(l.get("dr_paise", 0) for l in proposed_aje) != sum(
            l.get("cr_paise", 0) for l in proposed_aje):
        raise ValueError("INVALID_ARGUMENT: modified AJE lines must balance (Dr = Cr)")
    sets = {"status": DECISIONS[decision], "decided_by": rec["principal"], "decided_at": config.now(),
            "decision_note": note.strip()}
    if decision == "MODIFY":
        if taxable_impact_paise is not None:
            sets["taxable_impact_paise"] = int(taxable_impact_paise)
        if proposed_aje is not None:
            sets["proposed_aje_json"] = json.dumps(proposed_aje, sort_keys=True)
    with db.borrow("audit", "engagement_partner") as a, db.tx(a):
        eng = a.execute("SELECT status FROM engagements WHERE id = ?", (config.ENGAGEMENT_ID,)).fetchone()
        if eng and eng["status"] == "SIGNED_OFF":
            raise ValueError("PRECONDITION_FAILED: the engagement is signed off; later work is an addendum")
        n = a.execute(f"UPDATE findings SET {', '.join(k + ' = ?' for k in sets)} WHERE id = ? AND engagement_id = ?",
                      (*sets.values(), finding_id, config.ENGAGEMENT_ID)).rowcount
    if not n:
        raise LookupError(f"NOT_FOUND: finding {finding_id}")
    trail.trail(rec["principal"], rec["role"], "partner.decide_finding",
                {"finding_id": finding_id, "decision": decision}, "OK", sets, transport="UI")
    return sets


def blockers():
    """What still prevents sign-off (06 §9.3)."""
    out = []
    with db.borrow("audit", "engagement_partner") as a:
        eng = a.execute("SELECT * FROM engagements WHERE id = ?", (config.ENGAGEMENT_ID,)).fetchone()
        if eng is None:
            return ["no engagement yet (the client hasn't uploaded a register)"]
        n = a.execute("SELECT count(*) FROM findings WHERE engagement_id = ? AND status = 'PROPOSED'",
                      (config.ENGAGEMENT_ID,)).fetchone()[0]
    if n:
        out.append(f"{n} finding(s) still PROPOSED")
    if not getattr(evidence, "STUB", False):
        stale = evidence.check_for_changes(config.ENGAGEMENT_ID).get("stale_samples", [])
        if stale:
            out.append(f"{len(stale)} stale sample(s) need re-testing")
        if not evidence.verify_integrity(config.ENGAGEMENT_ID).get("ok"):
            out.append("verify_integrity failed")
    return out


def _sha(mod):
    if getattr(mod, "STUB", False):
        return None
    try:
        return mod.build(config.ENGAGEMENT_ID).get("sha256")
    except Exception:  # noqa: BLE001 - a deliverable bug must not hide the sign-off refusal reason
        return None


def sign_off(token, conclusion):
    """Lock the engagement with the partner's identity (name + membership_no from identities.json)."""
    rec = _partner(token)
    if not (conclusion or "").strip():
        raise ValueError("INVALID_ARGUMENT: write the partner's conclusion")
    block = blockers()
    if block:
        raise ValueError("PRECONDITION_FAILED: cannot sign off: " + "; ".join(block))
    erp_seq, erp_hash = trail.erp_head()
    with db.borrow("audit", "engagement_partner") as a:
        t_seq, t_hash = chain.head(a, "audit_trail")
    basis = {"workpaper_sha256": _sha(workpaper), "memo_sha256": _sha(memo), "erp_head": [erp_seq, erp_hash],
             "trail_head": [t_seq, t_hash], "conclusion": conclusion.strip()}
    sig = hashlib.sha256(chain.canon(basis).encode()).hexdigest()
    signer = f"{rec.get('name', rec['principal'])} (ICAI M.No. {rec.get('membership_no', 'n/a')})"
    with db.borrow("audit", "engagement_partner") as a, db.tx(a):
        a.execute("UPDATE engagements SET status = 'SIGNED_OFF', signed_by = ?, signed_at = ?, signoff_hash = ?"
                  " WHERE id = ?", (signer, config.now(), sig, config.ENGAGEMENT_ID))
    anchor = trail.anchor(config.ENGAGEMENT_ID, "SIGNOFF")
    trail.trail(rec["principal"], rec["role"], "partner.sign_off", {"conclusion": conclusion.strip()}, "OK",
                {"signoff_hash": sig}, transport="UI")
    notify.emit("SIGNED_OFF", {"signoff_hash": sig, "signed_by": rec["principal"]}, config.ENGAGEMENT_ID)
    for mod in (workpaper, memo):            # regenerate as FINAL (no DRAFT mark) when the builders exist
        _sha(mod)
    return {"signed_by": signer, "signoff_hash": sig, "anchor": anchor, "basis": basis}
