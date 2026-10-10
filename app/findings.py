"""Hits -> PROPOSED findings, proposed AJEs (06 §6), materiality (SA 320), the SA 450 summary, and the partner's
decisions and sign-off (06 §9: web UI only; the partner token is rejected on MCP).

A finding groups an object's hits from one detector. Severity >= 4 hits become findings; D5 concentration is a risk
indicator only (05 D5) and never becomes a finding on its own. AJEs are proposals stored in audit.db and are never
posted by the auditor: management posts an accepted one with post_journal_entry(aje_ref=...), which D7 then
recognises as ACCEPTED_AJE.
"""
import hashlib
import json
from collections import defaultdict

from app import config, db, money

CATEGORY = {"D0": "Register vs system of record", "D1": "Related parties", "D2": "Related parties (period)",
            "D3": "Cut-off / transfer of control", "D4": "Turnover without movement / settlement",
            "D5": "Period-end concentration", "D6": "Statutory documents and returns", "D7": "Revenue journals",
            "D8": "Evidence", "D9": "Credit notes", "D10": "Circular trading", "D11": "Changes after testing",
            "D12": "Integrity of records", "D13": "Backdating and sequence", "D14": "Instruction text in client data"}
STANDARDS = {
    "D0": "SA 500 (inconsistent evidence from different sources); SA 230",
    "D1": "SA 550; Ind AS 24 / AS 18; Companies Act 2013 s.2(76), s.184, s.188",
    "D2": "SA 550; Ind AS 24 paras 9, 18; s.188",
    "D3": "Ind AS 115 paras 31-38, B79-B82 (AS 9); SA 500; SA 240 (revenue recognition fraud risk)",
    "D4": "SA 240 (occurrence); SA 500; CGST Rule 138; Ind AS 115 para 9",
    "D5": "SA 240 (Appendix); SA 520",
    "D6": "CGST Act s.31, s.37, s.39; Rules 46, 48, 138; IGST Act s.10; SA 500",
    "D7": "SA 240 para 32(a) (journal entries); SA 330",
    "D8": "SA 500 (reliability of evidence); SA 240 (documents that may not be authentic)",
    "D9": "SA 560; Ind AS 10 / AS 4; Ind AS 115 paras 50-59, B20-B27; CGST s.34",
    "D10": "SA 240; Ind AS 115 para 9(d); Companies Act 2013 s.143(12)",
    "D11": "SA 230 (changes after assembly)", "D12": "Companies (Accounts) Rules 2014 r.3(1); SA 230; SA 265",
    "D13": "SA 240 para 32(a); CGST Rule 46(b), Rule 48", "D14": "SA 240 (authenticity); OWASP LLM01"}
HIGH_CONF = {"D0", "D3", "D4", "D6", "D7", "D8", "D9", "D12", "D13"}
LOW_CONF = {"D5", "D14"}
FICTITIOUS = {"NO_MOVEMENT", "EWB_NOT_FOUND", "BELONGS_TO_OTHER_TXN", "EWB_NOT_ON_PORTAL", "ROUND_TRIP_GOODS"}


def fy_label(iso):
    from app.portal import fy_label as f
    return f(iso)

# ---------------------------------------------------------------- materiality (SA 320)

def ensure_materiality(engagement_id):
    """Fill OM / PM / trivial with the defaults (0.5% of revenue; 75%; 5%) unless the auditor set them."""
    with db.borrow("audit", "system") as a:
        eng = dict(a.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone())
    if eng["materiality_paise"] and eng["performance_materiality_paise"] and eng["trivial_paise"]:
        return eng
    with db.borrow("erp", "system") as e:
        revenue = e.execute("SELECT COALESCE(SUM(l.taxable_paise), 0) FROM invoices i JOIN invoice_lines l ON"
                            " l.invoice_id = i.id WHERE i.status = 'ISSUED' AND i.invoice_date BETWEEN ? AND ?",
                            (eng["period_start"], eng["period_end"])).fetchone()[0]
    om = eng["materiality_paise"] or revenue * config.OVERALL_MATERIALITY_BP_OF_REVENUE // 10000
    pm = eng["performance_materiality_paise"] or om * config.PERFORMANCE_MATERIALITY_BP_OF_OM // 10000
    tr = eng["trivial_paise"] or om * config.TRIVIAL_BP_OF_OM // 10000
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute("UPDATE engagements SET materiality_paise = ?, performance_materiality_paise = ?, trivial_paise = ?"
                  " WHERE id = ?", (om, pm, tr, engagement_id))
    return {**eng, "materiality_paise": om, "performance_materiality_paise": pm, "trivial_paise": tr}

# ---------------------------------------------------------------- AJE templates (06 §6)

def _invoice(e, iid):
    inv = e.execute("SELECT * FROM invoices WHERE id = ?", (iid,)).fetchone()
    if inv is None:
        return None
    lines = [dict(r) for r in e.execute("SELECT l.*, it.cost_paise FROM invoice_lines l JOIN items it ON it.id = l.item_id"
                                        " WHERE invoice_id = ?", (iid,))]
    return dict(inv), lines


def _revenue_split(lines, pos):
    from app.erp import _revenue_account
    out = defaultdict(int)
    for l in lines:
        out[_revenue_account(l["hsn"], pos)] += l["taxable_paise"]
    return out


def aje(finding):
    """Balanced COA lines [{account_code, party_id?, dr_paise, cr_paise}] for a finding, or None (disclosure only)."""
    det, code = finding.get("detector"), finding.get("code")
    refs = finding.get("doc_refs") or json.loads(finding.get("doc_refs_json") or "[]")
    with db.borrow("erp", "system") as e:
        if det == "D7" and code in ("REVENUE_WITHOUT_SALE", "UNUSUAL_CONTRA", "POST_CLOSING"):
            jno = next((r for r in refs if str(r).isdigit()), None)
            if jno is None:
                return None
            jl = [dict(r) for r in e.execute("SELECT * FROM journal_lines WHERE journal_no = ?", (int(jno),))]
            rev = {r[0] for r in e.execute("SELECT code FROM accounts WHERE is_revenue = 1")}
            out = [{"account_code": l["account_code"], "dr_paise": l["cr_paise"], "cr_paise": 0}
                   for l in jl if l["account_code"] in rev and l["cr_paise"]]
            out += [{"account_code": l["account_code"], "party_id": l["party_id"], "dr_paise": 0, "cr_paise": l["dr_paise"]}
                    for l in jl if l["account_code"] not in rev and l["dr_paise"]]
            return _clean(out)
        if det == "D9" and code == "POST_PERIOD_REVERSAL":
            c = e.execute("SELECT * FROM credit_notes WHERE id = ?", (refs[0],)).fetchone() if refs else None
            if c is None:
                return None
            cl = [dict(r) for r in e.execute("SELECT l.*, it.cost_paise FROM cn_lines l LEFT JOIN items it ON it.id = l.item_id"
                                             " WHERE cn_id = ?", (c["id"],))]
            t = sum(l["taxable_paise"] for l in cl)
            out = [{"account_code": "SALES_RETURNS", "dr_paise": t}, {"account_code": "REFUND_LIABILITY", "cr_paise": t}]
            cost = sum((l["cost_paise"] or 0) * (l["qty"] or 0) for l in cl)
            if c["reason"] == "SALES_RETURN" and cost:
                out += [{"account_code": "INVENTORY", "dr_paise": cost}, {"account_code": "COGS", "cr_paise": cost}]
            return _clean(out)
        iid = next((r for r in refs if str(r).startswith("INV-")), None)
        got = _invoice(e, iid) if iid else None
        if got is None:
            return None
        inv, lines = got
        t = sum(l["taxable_paise"] for l in lines)
        cost = sum((l["cost_paise"] or 0) * l["qty"] for l in lines
                   if not str(l["hsn"]).startswith("99") and not l["item_id"].startswith("CHG"))
        split = _revenue_split(lines, inv["place_of_supply"])
        if det == "D3" and code == "PREMATURE":
            out = [{"account_code": a, "dr_paise": v} for a, v in split.items()]
            out.append({"account_code": "CONTRACT_LIABILITY", "cr_paise": t})
            if cost:
                out += [{"account_code": "INVENTORY", "dr_paise": cost}, {"account_code": "COGS", "cr_paise": cost}]
            return _clean(out)
        if det == "D3" and code == "DELAYED":
            out = [{"account_code": "DEBTORS", "party_id": inv["party_id"], "dr_paise": t}]
            out += [{"account_code": a, "cr_paise": v} for a, v in split.items()]
            if cost:
                out += [{"account_code": "COGS", "dr_paise": cost}, {"account_code": "INVENTORY", "cr_paise": cost}]
            return _clean(out)
        if code in FICTITIOUS:
            out = [{"account_code": a, "dr_paise": v} for a, v in split.items()]
            for acct, k in (("OUTPUT_IGST", "igst_paise"), ("OUTPUT_CGST", "cgst_paise"), ("OUTPUT_SGST", "sgst_paise")):
                v = sum(l[k] for l in lines)
                if v:
                    out.append({"account_code": acct, "dr_paise": v})
            out.append({"account_code": "DEBTORS", "party_id": inv["party_id"],
                        "cr_paise": t + sum(l["igst_paise"] + l["cgst_paise"] + l["sgst_paise"] for l in lines)})
            return _clean(out)
    return None                                       # RP, register-only, statutory, integrity: disclosure / judgement


def _clean(lines):
    out = []
    for l in lines:
        d, c = int(l.get("dr_paise") or 0), int(l.get("cr_paise") or 0)
        if d or c:
            out.append({k: v for k, v in {"account_code": l["account_code"], "party_id": l.get("party_id"),
                                           "dr_paise": d, "cr_paise": c}.items() if v is not None})
    dr, cr = sum(x["dr_paise"] for x in out), sum(x["cr_paise"] for x in out)
    return out if out and dr == cr > 0 else None

# ---------------------------------------------------------------- hits -> findings

_AS_FINDING = lambda h: h["severity"] >= 4 and h["detector"] != "D5" and h["code"] not in ("ACCEPTED_AJE",)


def _evidence(h):
    ev = json.loads(h["evidence_json"] or "null")
    return ev if isinstance(ev, dict) else {}


def _impacts(h_list, e):
    """(taxable, tax) impact of a group: the largest hit impact, with tax from the invoice when the template moves it."""
    t = max(h["impact_paise"] or 0 for h in h_list)
    tax = 0
    codes = {h["code"] for h in h_list}
    obj = h_list[0]
    if obj["object_type"] == "invoice" and codes & FICTITIOUS:
        r = e.execute("SELECT COALESCE(SUM(igst_paise + cgst_paise + sgst_paise), 0) FROM invoice_lines WHERE"
                      " invoice_id = ?", (obj["object_id"],)).fetchone()
        tax = r[0]
    return t, tax


def from_hits(engagement_id):
    """Group severity >= 4 hits by (detector, object) into PROPOSED findings with plain explanations, standards,
    impacts, affected FY, confidence and the proposed AJE. Existing findings for the same group are kept. -> new ids."""
    eng = ensure_materiality(engagement_id)
    with db.borrow("audit", "system") as a:
        hits = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ? ORDER BY severity DESC, id",
                                           (engagement_id,))]
        have = {json.loads(r[0] or "{}").get("group") for r in a.execute("SELECT evidence_json FROM findings WHERE"
                                                                          " engagement_id = ?", (engagement_id,))}
        last = a.execute("SELECT id FROM findings WHERE id >= 'F-0' AND id < 'F-:' ORDER BY id DESC LIMIT 1").fetchone()
    groups = defaultdict(list)
    for h in hits:
        if _AS_FINDING(h):
            groups[(h["detector"], h["object_type"], h["object_id"])].append(h)
    n = int(last[0][2:]) if last else 0
    rows, new = [], []
    with db.borrow("erp", "system") as e:
        for (det, otype, oid), hs in sorted(groups.items(), key=lambda kv: (-max(h["severity"] for h in kv[1]), kv[0])):
            gkey = f"{det}|{otype}|{oid}"
            if gkey in have:
                continue
            hs.sort(key=lambda h: (-h["severity"], -(h["impact_paise"] or 0)))
            top = hs[0]
            codes = sorted({h["code"] for h in hs})
            t, tax = _impacts(hs, e)
            doc_date = None
            if otype == "invoice":
                r = e.execute("SELECT invoice_date FROM invoices WHERE id = ?", (oid,)).fetchone()
                doc_date = r[0] if r else None
            elif otype == "credit_note":
                r = e.execute("SELECT cn_date FROM credit_notes WHERE id = ?", (oid,)).fetchone()
                doc_date = r[0] if r else None
            fy = fy_label(doc_date) if doc_date else fy_label(eng["period_end"])
            if top["code"] == "PREMATURE" or top["code"] == "POST_PERIOD_REVERSAL":
                fy = fy_label(eng["period_end"])
            refs = [oid] + sorted({str(j) for h in hs for j in _evidence(h).get("journals", [])})
            f = {"detector": det, "code": top["code"], "doc_refs": refs}
            lines = aje(f)
            n += 1
            fid = f"F-{n:03d}"
            explanation = " ".join(dict.fromkeys(h["reason"] for h in hs[:3]))
            title = f"{CATEGORY.get(det, det)}: {', '.join(codes[:3])} on {otype} {oid}"
            conf = "HIGH" if det in HIGH_CONF else ("LOW" if det in LOW_CONF else "MEDIUM")
            rows.append((fid, engagement_id, det, top["code"], CATEGORY.get(det, det), title, explanation,
                         STANDARDS.get(det, ""), json.dumps(refs), json.dumps({"group": gkey, "hits": [h["id"] for h in hs],
                                                                               "codes": codes}),
                         t, tax, t + tax, fy, conf, json.dumps(lines) if lines else None, "system:findings", config.now()))
            new.append(fid)
    if rows:
        with db.borrow("audit", "system") as a, db.tx(a):
            a.executemany("INSERT INTO findings(id, engagement_id, detector, code, category, title, explanation, standards,"
                          " doc_refs_json, evidence_json, taxable_impact_paise, tax_impact_paise, gross_impact_paise,"
                          " affected_fy, confidence, proposed_aje_json, status, prepared_by, prepared_at)"
                          " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'PROPOSED',?,?)", rows)
    return new

# ---------------------------------------------------------------- SA 450

_UNDER = {"DELAYED"}                                   # understatements reduce the net overstatement


def sa450_summary(engagement_id):
    """Uncorrected misstatements vs materiality (SA 450): factual (HIGH confidence), judgemental (MEDIUM/LOW) and
    projected (REPRESENTATIVE-stratum exceptions only, never KEY). Rejected findings are excluded."""
    eng = ensure_materiality(engagement_id)
    with db.borrow("audit", "system") as a:
        fs = [dict(r) for r in a.execute("SELECT * FROM findings WHERE engagement_id = ? AND status != 'REJECTED'"
                                         " AND proposed_aje_json IS NOT NULL", (engagement_id,))]
        reps = [dict(r) for r in a.execute("SELECT s.*, r.population_json FROM samples s JOIN sample_runs r ON r.id = s.run_id"
                                           " WHERE r.engagement_id = ? AND s.stratum = 'REPRESENTATIVE'", (engagement_id,))]
    factual = sum((-1 if f["code"] in _UNDER else 1) * f["taxable_impact_paise"] for f in fs if f["confidence"] == "HIGH")
    judgemental = sum((-1 if f["code"] in _UNDER else 1) * f["taxable_impact_paise"] for f in fs if f["confidence"] != "HIGH")
    projected = 0
    if reps:
        pop = {p["id"]: p for p in json.loads(reps[0]["population_json"])}
        sampled = sum(pop.get(s["doc_id"], {}).get("taxable", 0) for s in reps)
        err = sum(pop.get(s["doc_id"], {}).get("taxable", 0) for s in reps if s["conclusion_proposed"] == "EXCEPTION")
        rest = sum(p["taxable"] for p in pop.values() if p.get("max_sev", 0) < 4)
        projected = (err * rest // sampled) if sampled else 0
    total = factual + judgemental + projected
    return {"factual_paise": factual, "judgemental_paise": judgemental, "projected_paise": projected,
            "total_paise": total, "materiality_paise": eng["materiality_paise"],
            "performance_materiality_paise": eng["performance_materiality_paise"], "trivial_paise": eng["trivial_paise"],
            "exceeds": abs(total) >= (eng["materiality_paise"] or 0) > 0,
            "note": "possible modification of the opinion (SA 705) is the engagement partner's judgement"}

# ---------------------------------------------------------------- partner (web UI only, 06 §9)

def decide(finding_id, decision, note, partner, impact=None, aje_lines=None):
    """The partner's decision on a finding: CONFIRMED / REJECTED / MODIFIED with a mandatory comment. `partner` is the
    identity record ({principal, role, name, membership_no}); a modified AJE must balance."""
    from app import ledger
    if partner.get("role") != "engagement_partner":
        raise PermissionError("PERMISSION_DENIED: only the engagement partner decides findings (web UI)")
    if decision not in ("CONFIRMED", "REJECTED", "MODIFIED"):
        raise ValueError("INVALID_ARGUMENT: decision is CONFIRMED, REJECTED or MODIFIED")
    if not (note or "").strip():
        raise ValueError("INVALID_ARGUMENT: a comment is mandatory for every decision (SA 230)")
    sets = {"status": decision, "decided_by": f"{partner['name']} ({partner['principal']})", "decided_at": config.now(),
            "decision_note": note}
    if decision == "MODIFIED":
        if impact is not None:
            sets["taxable_impact_paise"] = int(impact)
        if aje_lines is not None:
            with db.borrow("erp", "engagement_partner") as e:
                ledger.check_lines(e, aje_lines)
            sets["proposed_aje_json"] = json.dumps(aje_lines)
    with db.borrow("audit", "engagement_partner") as a, db.tx(a):
        cur = a.execute(f"UPDATE findings SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?", (*sets.values(), finding_id))
        if cur.rowcount == 0:
            raise LookupError("NOT_FOUND: no such finding")
    return {"finding_id": finding_id, **sets}


def sign_off(engagement_id, partner):
    """Sign off (06 §9.3): refused while any finding is PROPOSED, any sample is STALE or integrity fails. Writes the
    signoff_hash over the final deliverables + both chain heads, regenerates them without DRAFT, anchors SIGNOFF."""
    from app import chain, evidence, memo, notify, trail, workpaper
    if partner.get("role") != "engagement_partner":
        raise PermissionError("PERMISSION_DENIED: only the engagement partner signs off (web UI)")
    with db.borrow("audit", "system") as a:
        proposed = a.execute("SELECT count(*) FROM findings WHERE engagement_id = ? AND status = 'PROPOSED'",
                             (engagement_id,)).fetchone()[0]
        untested = a.execute("SELECT count(*) FROM samples s JOIN sample_runs r ON r.id = s.run_id WHERE"
                             " r.engagement_id = ? AND s.conclusion_proposed = 'STALE'", (engagement_id,)).fetchone()[0]
    blockers = []
    if proposed:
        blockers.append(f"{proposed} finding(s) still PROPOSED")
    stale = evidence.check_for_changes(engagement_id)["stale_samples"]
    if stale or untested:
        blockers.append(f"{len(stale) + untested} STALE sample(s) to re-test")
    if not evidence.verify_integrity(engagement_id)["ok"]:
        blockers.append("verify_integrity fails")
    if blockers:
        raise ValueError("PRECONDITION_FAILED: sign-off refused: " + "; ".join(blockers))
    with db.borrow("audit", "engagement_partner") as a, db.tx(a):
        a.execute("UPDATE engagements SET signed_by = ?, signed_at = ? WHERE id = ?",
                  (f"{partner['name']} (ICAI M.No. {partner.get('membership_no', '-')})", config.now(), engagement_id))
    wp = workpaper.build(engagement_id, final=True)
    mm = memo.build(engagement_id, final=True)
    with db.borrow("audit", "system") as a, db.borrow("erp", "system") as e:
        t_head, e_head = chain.head(a, "audit_trail"), chain.head(e, "erp_log")
    h = hashlib.sha256(f"{wp['sha256']}{mm['sha256']}{t_head[1]}{e_head[1]}".encode()).hexdigest()
    with db.borrow("audit", "engagement_partner") as a, db.tx(a):
        a.execute("UPDATE engagements SET status = 'SIGNED_OFF', signoff_hash = ? WHERE id = ?", (h, engagement_id))
    trail.trail(partner["principal"], "engagement_partner", "sign_off", {"engagement_id": engagement_id}, "OK",
                {"signoff_hash": h}, transport="UI")
    anchor = trail.anchor(engagement_id, "SIGNOFF")
    notify.emit("SIGNED_OFF", {"signoff_hash": h}, engagement_id)
    return {"engagement_id": engagement_id, "signoff_hash": h, "workpaper": wp, "memo": mm, "anchor": anchor}


def fmt(paise):
    return money.fmt_inr(paise)
