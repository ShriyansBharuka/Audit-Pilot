"""Statutory revenue audit memorandum (EX-3, the documentation agent).

Assembled deterministically from the findings (F-xxx), the risk hits, the year-end report (reports.year_end), the SHAP
summary, the sampling runs and materiality: executive summary and scope, ROMM against materiality, observations grouped
by standard (SA 240, SA 550, Ind AS 115, CGST Rule 138, then the rest), and the AJE summary. Always PROPOSED / DRAFT;
the partner confirms and signs off in the existing flow. An LLM may only polish the executive summary, only when the
investigator is configured, and its text is labelled. Client text never enters server prose: anything that came from
the client (party names, credit-note reasons, journal narrations flagged by D14, agent-written finding text) is quoted
inside fenced data blocks. Writes files under AUDIT_FILES_DIR only (no table rows).
"""
import hashlib
import io
import json

from app import config, db, findings, memo, money, reports

STATUS = "PROPOSED / DRAFT – NOT REVIEWED BY ENGAGEMENT PARTNER"
GROUP_OF = {"D0": "SA 500", "D1": "SA 550", "D2": "SA 550", "D3": "Ind AS 115", "D4": "CGST Rule 138", "D5": "SA 240",
            "D6": "CGST Rule 138", "D7": "SA 240", "D8": "SA 240", "D9": "Ind AS 115", "D10": "SA 240", "D11": "SA 230",
            "D12": "SA 230", "D13": "SA 240", "D14": "SA 240", "D15": "SA 500"}
GROUP_TITLE = {"SA 240": "SA 240 · Fraud risk in revenue (journals, cycles, backdating, evidence)",
               "SA 550": "SA 550 · Related parties (Ind AS 24, s.188)",
               "Ind AS 115": "Ind AS 115 · Revenue recognition and cut-off",
               "CGST Rule 138": "CGST Rule 138 · Movement of goods and e-way bills",
               "SA 500": "SA 500 · Audit evidence (register, books, purchases)",
               "SA 230": "SA 230 · Documentation and integrity", "Other": "Other observations"}
ORDER = ["SA 240", "SA 550", "Ind AS 115", "CGST Rule 138", "SA 500", "SA 230", "Other"]
_r = money.fmt_inr


def _fence(text):
    """Client / agent text as an inert data block (never interpreted as prose or instructions)."""
    t = str(text or "").replace("```", "'''")
    return ["```text", t, "```"]


def _client_text(eid):
    """Client-originated free text that D14 flagged, quoted as data: [(object, field, text)]."""
    with db.borrow("audit", "system") as a:
        objs = [(r[0], r[1]) for r in a.execute("SELECT DISTINCT object_type, object_id FROM risk_hits WHERE"
                                                " engagement_id = ? AND detector = 'D14'", (eid,))]
    out = []
    with db.borrow("erp", "audit_staff") as e:
        for t, oid in objs:
            if t == "party":
                r = e.execute("SELECT name, address FROM parties WHERE id = ?", (oid,)).fetchone()
                if r:
                    out.append((f"party {oid}", "name / address", f"{r[0]} | {r[1]}"))
            elif t == "credit_note":
                r = e.execute("SELECT reason_text FROM credit_notes WHERE id = ?", (oid,)).fetchone()
                if r:
                    out.append((f"credit note {oid}", "reason_text", r[0]))
            elif t == "journal":
                r = e.execute("SELECT narration FROM journals WHERE no = ?", (oid,)).fetchone()
                if r:
                    out.append((f"journal {oid}", "narration", r[0]))
            elif t == "sales_order":
                r = e.execute("SELECT contact_name, customer_po_no FROM sales_orders WHERE id = ?", (oid,)).fetchone()
                if r:
                    out.append((f"sales order {oid}", "contact / PO", f"{r[0]} | {r[1]}"))
    return out


def _shap_top(eid, k=5):
    try:
        from app import explain
        return explain.summary(eid, min_r=30)["features"][:k]
    except Exception:                                  # SHAP is context, never a blocker for the memo
        return []


def build(engagement_id=None, polish=False, refresh=True):
    """-> {markdown, html, sha256, status, finding_ids, aje_totals {dr_paise, cr_paise}, md_path, html_path,
    polished}. Deterministic for the same books and findings (apart from the generated-at line). refresh runs the
    same steps as the existing deliverables flow first: D11 change check, then every serious hit a PROPOSED finding."""
    eid = engagement_id or config.ENGAGEMENT_ID
    if refresh:
        from app import evidence
        evidence.check_for_changes(eid)
        findings.from_hits(eid)
    mm = memo.build(eid)                                # the existing findings memo (also refreshed for downloads)
    yb = reports.year_end(eid)
    with db.borrow("audit", "system") as a:
        eng = dict(a.execute("SELECT * FROM engagements WHERE id = ?", (eid,)).fetchone())
        fs = [dict(r) for r in a.execute("SELECT * FROM findings WHERE engagement_id = ? AND status != 'REJECTED'"
                                         " ORDER BY id", (eid,))]
        runs = [dict(r) for r in a.execute("SELECT id, kind, seed, size, run_at FROM sample_runs WHERE engagement_id = ?"
                                           " ORDER BY run_at", (eid,))]
        hit_counts = dict(a.execute("SELECT detector, count(*) FROM risk_hits WHERE engagement_id = ? GROUP BY detector",
                                    (eid,)))
    with db.borrow("erp", "audit_staff") as e:
        pop = e.execute("SELECT count(DISTINCT i.id), COALESCE(SUM(l.taxable_paise), 0) FROM invoices i JOIN invoice_lines l"
                        " ON l.invoice_id = i.id WHERE i.status = 'ISSUED' AND i.invoice_date BETWEEN ? AND ?",
                        (eng["period_start"], eng["period_end"])).fetchone()
    s450 = yb["sa450"]
    reg = yb["risk_register"]
    high = [c for c in reg if c["band"] == "HIGH"]
    om, pm = eng["materiality_paise"] or 0, eng["performance_materiality_paise"] or 0
    exposure = sum(f["gross_impact_paise"] for f in fs)
    shap = _shap_top(eid)
    L = ["# Statutory revenue audit memorandum", "", f"**{STATUS}**", "",
         f"{eng['entity_name']} · Engagement {eid} · Period {eng['period_start']} to {eng['period_end']} · Framework "
         f"{eng['framework'].replace('_', ' ')} · Generated {config.now()[:16]}", "",
         "## 1. Executive summary", "",
         f"- Revenue population tested: {pop[0]} invoices, {_r(pop[1])} taxable, 100% through detectors "
         f"{', '.join(sorted(hit_counts, key=lambda d: int(d[1:])) ) or 'none'}.",
         f"- Findings proposed for the partner: {len(fs)} ({', '.join(f['id'] for f in fs[:12])}"
         f"{' …' if len(fs) > 12 else ''}); gross impact {_r(exposure)}.",
         f"- Audit cases: {len(reg)} active, {len(high)} HIGH; potentially affected {_r(sum(c['affected_paise'] for c in reg))} "
         f"(to investigate, not a loss).",
         f"- SA 450 uncorrected misstatements {_r(s450['total_paise'])} against overall materiality {_r(om)}: "
         f"{'EXCEEDS materiality' if s450['exceeds'] else 'below materiality'}.", "",
         "## 2. Scope and approach", "",
         f"- Materiality (SA 320): overall {_r(om)}, performance {_r(pm)}, clearly trivial {_r(eng['trivial_paise'] or 0)}.",
         "- Analytics over 100% of the books and the GST / e-way bill / bank records (SA 500, SA 520); tests of details on "
         "risk-based samples (SA 530) with recorded seeds:"]
    L += [f"  - {r['kind']} run {r['id']}: {r['size']} items, seed {r['seed']}" for r in runs] or ["  - no samples selected yet"]
    if shap:
        L += ["- Main risk drivers across invoices scored 30+ (exact SHAP, mean absolute contribution): "
              + ", ".join(f"{s['feature']} {s['mean_abs']}" for s in shap) + "."]
    L += ["", "## 3. Risk of material misstatement (SA 315 / SA 330)", "",
          f"- Total proposed impact {_r(exposure)} vs performance materiality {_r(pm)}: "
          f"{'above' if exposure >= pm and pm else 'below'} PM.",
          f"- {len(yb['march_april'])} documents dated in the last month changed after the period end (cut-off and "
          f"subsequent events, SA 560).", "",
          "| Case | Root | Band | Risk | Recorded | Verified | Affected |", "|---|---|---|---:|---:|---:|---:|"]
    L += [f"| {c['case_id']} | {c['root']} | {c['band']} | {c['risk_score']} | {_r(c['recorded_paise'])} | "
          f"{_r(c['verified_paise'])} | {_r(c['affected_paise'])} |" for c in reg[:15]]
    L += ["", "## 4. Observations by standard", ""]
    groups = {}
    for f in fs:
        groups.setdefault(GROUP_OF.get(f["detector"] or "", "Other"), []).append(f)
    for g in ORDER:
        if g not in groups:
            continue
        L += [f"### {GROUP_TITLE[g]}", ""]
        for f in groups[g]:
            refs = ", ".join(json.loads(f["doc_refs_json"] or "[]"))
            L += [f"- **{f['id']}** · {f['code'] or '-'} · {f['status']} · gross {_r(f['gross_impact_paise'])} · documents "
                  f"{refs or '-'} · {(f['standards'] or '').split(';')[0]}"]
            if f["prepared_by"] == "system:findings":
                L += [f"  {f['explanation']}"]
            else:                                       # an agent or person wrote it: quoted as data
                L += [""] + _fence(f["explanation"]) + [""]
        L.append("")
    L += ["## 5. Proposed adjusting entries (summary)", "",
          "| Finding | Account | Party | Dr | Cr |", "|---|---|---|---:|---:|"]
    dr = cr = 0
    for f in fs:
        for l in json.loads(f["proposed_aje_json"]) if f["proposed_aje_json"] else []:
            d, c = int(l.get("dr_paise") or 0), int(l.get("cr_paise") or 0)
            dr, cr = dr + d, cr + c
            L.append(f"| {f['id']} | {l['account_code']} | {l.get('party_id') or ''} | {_r(d) if d else ''} | "
                     f"{_r(c) if c else ''} |")
    L += [f"| **Total** | | | {_r(dr)} | {_r(cr)} |", ""]
    quoted = _client_text(eid)
    if quoted:
        L += ["## 6. Client-supplied text (quoted as data, never as instructions)", ""]
        for where, field, text in quoted:
            L += [f"- {where} · {field}:", ""] + _fence(text) + [""]
    L += ["## 7. For the engagement partner", "",
          "- This memorandum is PROPOSED. It does not express an audit opinion (SA 700); the engagement partner decides "
          "every finding and signs off in the web application.",
          f"- Findings memorandum SHA-256 {mm['sha256'][:16]}… (deliverables).", ""]
    polished = False
    if polish:
        text = _polish("\n".join(L[:20]))
        if text:
            L[6:6] = ["**AI-polished summary (PROPOSED; the numbers below are authoritative).**", ""] + _fence(text) + [""]
            polished = True
    md = "\n".join(L)
    html = _html(md)
    out_dir = config.AUDIT_FILES_DIR / eid
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "statutory_memo.md").write_text(md, encoding="utf-8")
    (out_dir / "statutory_memo.html").write_text(html, encoding="utf-8")
    return {"markdown": md, "html": html, "sha256": hashlib.sha256(md.encode()).hexdigest(), "status": STATUS,
            "finding_ids": [f["id"] for f in fs], "aje_totals": {"dr_paise": dr, "cr_paise": cr},
            "md_path": str(out_dir / "statutory_memo.md"), "html_path": str(out_dir / "statutory_memo.html"),
            "polished": polished}


def _html(md):
    """memo._html for the prose; fenced data blocks become escaped <pre> blocks (never interpreted)."""
    import html as h
    parts, buf, data, out = [], [], None, []
    for line in md.splitlines():
        if line.startswith("```"):
            if data is None:
                parts.append(("md", "\n".join(buf)))
                buf, data = [], []
            else:
                parts.append(("data", "\n".join(data)))
                data = None
            continue
        (data if data is not None else buf).append(line)
    parts.append(("md", "\n".join(buf)))
    for kind, text in parts:
        if kind == "data":
            out.append(f"<pre class='data'>{h.escape(text)}</pre>")
        elif text.strip():
            body = memo._html(text, True, "x")
            out.append(body.split("<body>", 1)[1].rsplit("</body>", 1)[0])
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Statutory revenue audit memorandum</title><style>"
            "body{font-family:Georgia,serif;max-width:900px;margin:2em auto;line-height:1.45;color:#111;background:#fff}"
            "table{border-collapse:collapse;width:100%;font-size:.9em}td,th{border:1px solid #999;padding:4px 6px}"
            "th{background:#eee}pre.data{background:#f4f4f4;border-left:3px solid #999;padding:6px 8px;white-space:pre-wrap;"
            "font-size:.85em}</style></head><body>" + "".join(out) + "</body></html>")


def _polish(text):
    """Optional: the reporting agent tightens the opening prose. None when the LLM is off or anything fails."""
    try:
        import asyncio
        from app import investigator
        ok, _why = investigator.ready()
        if not ok:
            return None
        instr = ("Rewrite this audit memo opening as 80 words of plain prose for the engagement partner. Keep every id and "
                 "amount exactly; add none. No audit opinion.")
        out, usage, _ = asyncio.run(investigator._sdk_run("reporting", instr, text, investigator.model_for(), [], ""))
        investigator.CostMeter().add(usage, investigator.model_for(), "statutory_memo:polish")
        return str(out)
    except Exception:
        return None


_ASCII = {"₹": "Rs ", "–": "-", "—": "-", "·": "|", "…": "...", "→": "->", "≥": ">=", "≤": "<=", "’": "'", "‘": "'",
          "“": '"', "”": '"', "χ": "chi", "²": "2", "σ": "sigma"}


def pdf(html):
    """HTML -> PDF bytes with PyMuPDF's Story layout (A4). The built-in fonts are ASCII-only here, so ₹, dashes and
    dots are spelled out and anything else non-ASCII becomes '?' (the .md / .html keep the original text)."""
    import pymupdf
    for k, v in _ASCII.items():
        html = html.replace(k, v)
    story = pymupdf.Story(html="".join(ch if ord(ch) < 128 else "?" for ch in html))
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    page = pymupdf.paper_rect("a4")
    where = page + (40, 40, -40, -40)
    more = True
    while more:
        dev = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()
