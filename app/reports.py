"""Reports A and B (vault/13 MT-7), same style as the findings memo (md + printable html), DRAFT until sign-off.

A, continuous audit intelligence (operational): unreconciled transactions, missing evidence, control failures, the
risk trend and open alerts. B, year-end investigation report (for the auditor): transaction risk register,
counterparty exposure, funds-flow summary, investigated cases, March-April links, proposed AJEs, unresolved
questions. Every amount comes from a deterministic module and carries the case or finding id it comes from. An
optional AI executive summary is labelled as such; neither report ever expresses an audit opinion (SA 700).
"""
import json
from collections import defaultdict

from app import cases, config, db, findings, memo, money, workpaper, yearend

NO_OPINION = ("This report does not express an audit opinion. The engagement partner forms the opinion (SA 700) "
              "and decides every finding.")
UNRECONCILED = {"D0", "D6"}                              # register vs books; books vs IRP / EWB / GSTR-1
CONTROLS = {"D7", "D12", "D13", "D14"}                   # journals, integrity, backdating, instruction text
_r = money.fmt_inr


def _base(eid):
    with db.borrow("audit", "system") as a:
        eng = a.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone()
        if eng is None:
            raise LookupError("NOT_FOUND: no engagement yet. Upload the register first (upload_sales_register)")
        eng = dict(eng)
        hits = [dict(r) for r in a.execute("SELECT * FROM risk_hits WHERE engagement_id = ?", (eid,))]
        rows = [dict(r) for r in a.execute("SELECT * FROM cases WHERE engagement_id = ? AND active = 1", (eid,))]
    hit_case = {}
    for c in rows:
        for h in json.loads(c["hit_ids_json"]):
            hit_case[h] = c["id"]
    final = workpaper._is_final(eid, None)
    return eng, hits, rows, hit_case, final


def _head(eng, final, kind):
    return {"report": kind, "engagement_id": eng["id"], "entity": eng["entity_name"],
            "period": {"start": eng["period_start"], "end": eng["period_end"]},
            "status": "FINAL" if final else "DRAFT", "generated_at": config.now(), "no_opinion": NO_OPINION}


def _hit_rows(hits, hit_case, dets):
    """Serious hits of these detectors, grouped by case: amounts only with a case id."""
    by_case, loose = defaultdict(list), 0
    for h in hits:
        if h["detector"] in dets:
            if h["id"] in hit_case:
                by_case[hit_case[h["id"]]].append(h)
            else:
                loose += 1
    out = []
    for cid, hs in sorted(by_case.items()):
        best = {}
        for h in hs:
            k = (h["object_type"], h["object_id"])
            best[k] = max(best.get(k, 0), h["impact_paise"] or 0)
        out.append({"case_id": cid, "codes": sorted({h["code"] for h in hs}),
                    "objects": sorted(f"{t} {i}" for t, i in best), "impact_paise": sum(best.values())})
    return out, loose


def continuous(engagement_id=None):
    """Report A as a dict (render() makes md / html)."""
    eid = engagement_id or config.ENGAGEMENT_ID
    cases.refresh_if_stale(eid)
    eng, hits, rows, hit_case, final = _base(eid)
    unrec, unrec_loose = _hit_rows(hits, hit_case, UNRECONCILED)
    ctrl, ctrl_loose = _hit_rows(hits, hit_case, CONTROLS)
    with db.borrow("pbc", "system") as p:
        reqs = [dict(r) for r in p.execute("SELECT id, sample_ref, doc_kind, about_doc_no, due_on, status FROM"
                                           " evidence_requests WHERE engagement_id = ? AND status IN ('OPEN', 'OVERDUE')"
                                           " ORDER BY due_on, id", (eid,))]
    overdue = [r for r in reqs if r["status"] == "OVERDUE" or r["due_on"] < config.today()]
    with db.borrow("audit", "system") as a:
        alerts = [dict(r) for r in a.execute("SELECT id, kind, at FROM events WHERE engagement_id = ? AND kind IN"
                                             " ('RISK_ESCALATED', 'STALE_DETECTED', 'INTEGRITY_ALERT') ORDER BY id DESC"
                                             " LIMIT 20", (eid,))]
    open_cases = [c for c in rows if c["status"] in ("OPEN", "ESCALATED", "EVIDENCE_REQUESTED")]
    by_band = defaultdict(int)
    for c in open_cases:
        by_band[c["band"]] += 1
    trend = yearend.timeline(engagement_id=eid)["months"]
    return {**_head(eng, final, "A_CONTINUOUS"),
            "unreconciled": {"items": unrec, "lower_severity_hits": unrec_loose},
            "missing_evidence": {"open_requests": len(reqs), "overdue": len(overdue),
                                 "items": [{"request_id": r["id"], "ref": r["sample_ref"], "doc_kind": r["doc_kind"],
                                            "about": r["about_doc_no"], "due_on": r["due_on"]} for r in reqs[:50]]},
            "control_failures": {"items": ctrl, "lower_severity_hits": ctrl_loose},
            "risk_trend": [{"ym": m["ym"], "open_exceptions": m["open_exceptions"], "band": m["band"],
                            "band_source": m["band_source"]} for m in trend],
            "open_alerts": {"events": alerts, "open_cases": len(open_cases), "by_band": dict(by_band),
                            "top": [{"case_id": c["id"], "title": c["title"], "band": c["band"], "risk_score": c["risk_score"],
                                     "affected_paise": c["affected_paise"]}
                                    for c in sorted(open_cases, key=lambda c: (-c["risk_score"], -c["affected_paise"]))[:10]]}}


def year_end(engagement_id=None, ai_summary=False):
    """Report B as a dict. ai_summary=True asks the reporting agent for a labelled DRAFT summary (skipped when the LLM
    is off); every number in it is already in the deterministic sections."""
    eid = engagement_id or config.ENGAGEMENT_ID
    cases.refresh_if_stale(eid)
    eng, hits, rows, hit_case, final = _base(eid)
    register = sorted(rows, key=lambda c: (-c["risk_score"], -c["affected_paise"], c["id"]))
    names = cases._names({c["counterparty_id"] for c in rows})
    exposure = defaultdict(lambda: {"case_ids": [], "affected_paise": 0, "verified_paise": 0, "recorded_paise": 0})
    for c in rows:
        if c["counterparty_id"]:
            x = exposure[c["counterparty_id"]]
            x["case_ids"].append(c["id"])
            for k in ("affected_paise", "verified_paise", "recorded_paise"):
                x[k] += c[k]
    flows = [c for c in rows if c["root_type"] in ("purchase_order", "settlement", "party", "purchase_bill")]
    with db.borrow("audit", "system") as a:
        inv = {}
        for r in a.execute("SELECT case_id, payload_json FROM case_events WHERE action = 'AI_INVESTIGATION' ORDER BY id"):
            inv[r[0]] = json.loads(r[1] or "{}")
        acted = {r[0]: r[1] for r in a.execute("SELECT case_id, action FROM case_events WHERE action NOT IN"
                                                " ('OPENED', 'AI_INVESTIGATION') ORDER BY id")}
        fs = [dict(r) for r in a.execute("SELECT id, title, status, taxable_impact_paise, gross_impact_paise, evidence_json"
                                         " FROM findings WHERE engagement_id = ? AND proposed_aje_json IS NOT NULL ORDER BY id",
                                         (eid,))]
    ma = yearend.march_april_links(eid)["items"]
    questions = []
    for cid, p in sorted(inv.items()):
        questions += [{"case_id": cid, "question": q} for q in p.get("open_questions", [])]
    for c in register:
        if c["status"] in ("OPEN", "ESCALATED", "EVIDENCE_REQUESTED") and c["id"] not in inv:
            questions.append({"case_id": c["id"], "question": next((cases.SUGGEST[k] for k in json.loads(c["codes_json"])
                                                                    if k in cases.SUGGEST), "Inspect and request the missing evidence.")})
    s450 = findings.sa450_summary(eid)
    out = {**_head(eng, final, "B_YEAR_END"),
           "risk_register": [{"case_id": c["id"], "title": c["title"], "root": f"{c['root_type']} {c['root_id']}",
                              "counterparty_id": c["counterparty_id"], "band": c["band"], "risk_score": c["risk_score"],
                              "confidence": c["confidence"] / 1000, "recorded_paise": c["recorded_paise"],
                              "verified_paise": c["verified_paise"], "affected_paise": c["affected_paise"],
                              "status": c["status"]} for c in register],
           "counterparty_exposure": sorted(({"counterparty_id": k, "counterparty_name": names.get(k), **v}
                                            for k, v in exposure.items()), key=lambda x: -x["affected_paise"]),
           "funds_flow": [{"case_id": c["id"], "root": f"{c['root_type']} {c['root_id']}", "recorded_paise": c["recorded_paise"],
                           "verified_paise": c["verified_paise"], "received_paise": c["received_paise"],
                           "affected_paise": c["affected_paise"], "attribution": "NOT_ESTABLISHED"} for c in flows],
           "investigated": [{"case_id": c["id"], "status": c["status"], "last_action": acted.get(c["id"]),
                             "ai_conclusion": (inv.get(c["id"]) or {}).get("conclusion")}
                            for c in register if c["id"] in inv or c["id"] in acted],
           "march_april": [{"doc": f"{i['march_doc']['doc_type']} {i['march_doc']['doc_id']}",
                            "events": [e["kind"] for e in i["april_events"]],
                            "case_ids": sorted({hit_case[h] for h in _hit_ids(hits, i) if h in hit_case}),
                            "affected_paise": i["affected_paise"]} for i in ma],
           "proposed_ajes": [{"finding_id": f["id"], "title": f["title"], "status": f["status"],
                              "taxable_impact_paise": f["taxable_impact_paise"], "gross_impact_paise": f["gross_impact_paise"],
                              "case_id": (json.loads(f["evidence_json"] or "{}") or {}).get("case")} for f in fs],
           "sa450": s450,
           "unresolved_questions": questions[:50],
           "executive_summary": None}
    out["executive_summary"] = _summary(out)
    if ai_summary:
        out["ai_executive_summary"] = _ai_summary(out)
    return out


def _hit_ids(hits, item):
    keys = {(h["object_type"], h["object_id"]) for h in item["hits"]}
    return [h["id"] for h in hits if (h["object_type"], h["object_id"]) in keys]


def _summary(b):
    """Deterministic executive summary: counts and sums of the listed rows, with their ids."""
    reg = b["risk_register"]
    high = [c for c in reg if c["band"] == "HIGH"]
    top = reg[:3]
    return (f"{len(reg)} active cases ({len(high)} HIGH). Potentially affected across cases "
            f"{_r(sum(c['affected_paise'] for c in reg))} (an amount to investigate, not a loss); bank-verified "
            f"{_r(sum(c['verified_paise'] for c in reg))} against {_r(sum(c['recorded_paise'] for c in reg))} recorded. "
            f"Highest risk: {', '.join(c['case_id'] for c in top) or 'none'}. {len(b['march_april'])} March documents "
            f"changed after the period end; {len(b['proposed_ajes'])} proposed adjusting entries "
            f"({', '.join(f['finding_id'] for f in b['proposed_ajes'][:5]) or 'none'}). SA 450 uncorrected total "
            f"{_r(b['sa450']['total_paise'])} ({'exceeds' if b['sa450']['exceeds'] else 'below'} materiality).")


def _ai_summary(b):
    import asyncio
    from app import investigator
    ok, why = investigator.ready()
    if not ok:
        return {"label": "AI-DRAFTED EXECUTIVE SUMMARY", "text": None, "skipped": why}
    brief = json.dumps({k: b[k] for k in ("executive_summary", "risk_register", "march_april", "proposed_ajes")},
                       default=str)[:12000]
    instr = ("Write a 120-word executive summary for the engagement partner from this JSON. Cite case and finding ids; "
             "copy amounts exactly as given (paise / 100 in rupees) or omit them. Never give an audit opinion.")
    out, usage, _ = asyncio.run(investigator._sdk_run("reporting", instr, brief, investigator.model_for(), [], ""))
    usd = investigator.CostMeter().add(usage, investigator.model_for(), "report:summary") / 1e6
    return {"label": "AI-DRAFTED EXECUTIVE SUMMARY (DRAFT; not an audit opinion; numbers above are authoritative)",
            "text": str(out), "usd": round(usd, 4)}

# ---------------------------------------------------------------- rendering

def _md_a(r):
    L = ["# Report A: continuous audit intelligence", ""]
    if r["status"] == "DRAFT":
        L += [f"**{memo.DRAFT}**", ""]
    L += [f"{r['entity']} · Period {r['period']['start']} to {r['period']['end']} · Generated {r['generated_at'][:16]} · "
          f"Status {r['status']}", "", "## 1. Unreconciled transactions (register, books, portals)", "",
          "| Case | Codes | Objects | Impact |", "|---|---|---|---:|"]
    L += [f"| {x['case_id']} | {', '.join(x['codes'])} | {', '.join(x['objects'][:3])} | {_r(x['impact_paise'])} |"
          for x in r["unreconciled"]["items"]]
    L += ["", f"Lower-severity differences not in a case: {r['unreconciled']['lower_severity_hits']} (list_audit_items).",
          "", "## 2. Missing evidence", "",
          f"- Open evidence requests: {r['missing_evidence']['open_requests']} (overdue {r['missing_evidence']['overdue']})."]
    L += [f"- {x['request_id']} · {x['ref']} · {x['doc_kind']} · due {x['due_on']}" for x in r["missing_evidence"]["items"][:15]]
    L += ["", "## 3. Control failures", "", "| Case | Codes | Objects | Impact |", "|---|---|---|---:|"]
    L += [f"| {x['case_id']} | {', '.join(x['codes'])} | {', '.join(x['objects'][:3])} | {_r(x['impact_paise'])} |"
          for x in r["control_failures"]["items"]]
    L += ["", "## 4. Risk trend", "", "| Month | Open exceptions | Band | Source |", "|---|---:|---|---|"]
    L += [f"| {m['ym']} | {m['open_exceptions']} | {m['band']} | {m['band_source']} |" for m in r["risk_trend"]]
    oa = r["open_alerts"]
    L += ["", "## 5. Open alerts", "", f"- Open cases: {oa['open_cases']} "
          f"({', '.join(f'{k} {v}' for k, v in sorted(oa['by_band'].items())) or 'none'}).",
          f"- Recent alerts: {', '.join('{} #{}'.format(e['kind'], e['id']) for e in oa['events'][:10]) or 'none'}.", "",
          "| Case | Title | Band | Risk | Affected |", "|---|---|---|---:|---:|"]
    L += [f"| {c['case_id']} | {c['title']} | {c['band']} | {c['risk_score']} | {_r(c['affected_paise'])} |" for c in oa["top"]]
    L += ["", "## 6. Note", "", r["no_opinion"], ""]
    return "\n".join(L)


def _md_b(r):
    L = ["# Report B: year-end investigation report", ""]
    if r["status"] == "DRAFT":
        L += [f"**{memo.DRAFT}**", ""]
    L += [f"{r['entity']} · Period {r['period']['start']} to {r['period']['end']} · Generated {r['generated_at'][:16]} · "
          f"Status {r['status']}", "", "## 1. Executive summary", "", r["executive_summary"], ""]
    if r.get("ai_executive_summary") and r["ai_executive_summary"].get("text"):
        L += [f"**{r['ai_executive_summary']['label']}.** {r['ai_executive_summary']['text']}", ""]
    L += ["## 2. Transaction risk register", "",
          "| Case | Title | Band | Risk | Confidence | Recorded | Verified | Affected | Status |",
          "|---|---|---|---:|---:|---:|---:|---:|---|"]
    L += [f"| {c['case_id']} | {c['title']} | {c['band']} | {c['risk_score']} | {c['confidence']:.2f} | "
          f"{_r(c['recorded_paise'])} | {_r(c['verified_paise'])} | {_r(c['affected_paise'])} | {c['status']} |"
          for c in r["risk_register"]]
    L += ["", "## 3. Counterparty exposure", "", "| Counterparty | Cases | Affected | Verified |", "|---|---|---:|---:|"]
    L += [f"| {x['counterparty_id']} | {', '.join(x['case_ids'])} | {_r(x['affected_paise'])} | {_r(x['verified_paise'])} |"
          for x in r["counterparty_exposure"]]
    L += ["", "## 4. Funds-flow summary", "",
          "Recorded = the company's books; verified = bank lines naming the recorded counterparty; nothing is attributed "
          "beyond the counterparty, and a cycle counts once at its minimum-span value.", "",
          "| Case | Root | Recorded | Verified | Received | Affected |", "|---|---|---:|---:|---:|---:|"]
    L += [f"| {x['case_id']} | {x['root']} | {_r(x['recorded_paise'])} | {_r(x['verified_paise'])} | "
          f"{_r(x['received_paise']) if x['received_paise'] is not None else '-'} | {_r(x['affected_paise'])} |"
          for x in r["funds_flow"]]
    L += ["", "## 5. Investigated cases", ""]
    L += [f"- {x['case_id']}: {x['status']}; last action {x['last_action'] or '-'}; AI conclusion "
          f"{x['ai_conclusion'] or '-'} (PROPOSED)." for x in r["investigated"]] or ["- none yet."]
    L += ["", "## 6. March to April (cut-off and subsequent events)", "", "| Document | After the period end | Cases | Affected |",
          "|---|---|---|---:|"]
    L += [f"| {x['doc']} | {', '.join(x['events'])} | {', '.join(x['case_ids']) or '-'} | {_r(x['affected_paise'])} |"
          for x in r["march_april"]]
    L += ["", "## 7. Proposed adjusting entries", "", "| Finding | Case | Status | Taxable | Gross |", "|---|---|---|---:|---:|"]
    L += [f"| {f['finding_id']} | {f['case_id'] or '-'} | {f['status']} | {_r(f['taxable_impact_paise'])} | "
          f"{_r(f['gross_impact_paise'])} |" for f in r["proposed_ajes"]]
    s = r["sa450"]
    L += ["", f"SA 450: factual {_r(s['factual_paise'])}, judgemental {_r(s['judgemental_paise'])}, projected "
          f"{_r(s['projected_paise'])}; total {_r(s['total_paise'])} against materiality {_r(s['materiality_paise'])}.", "",
          "## 8. Unresolved questions", ""]
    L += [f"- {q['case_id']}: {q['question']}" for q in r["unresolved_questions"]] or ["- none."]
    L += ["", "## 9. Note", "", r["no_opinion"], ""]
    return "\n".join(L)


def render(report, fmt="json"):
    """-> dict (json) | markdown str | html str."""
    if fmt == "json":
        return report
    md = _md_a(report) if report["report"] == "A_CONTINUOUS" else _md_b(report)
    if fmt == "md":
        return md
    if fmt == "html":
        title = "Report A: continuous audit" if report["report"] == "A_CONTINUOUS" else "Report B: year-end investigation"
        return memo._html(md, report["status"] == "FINAL", title)
    raise ValueError("INVALID_ARGUMENT: format is json, md or html")
