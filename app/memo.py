"""The findings memorandum (06 §7): memo.md + a printable memo.html.

DRAFT until the partner signs off; in the FINAL memo only CONFIRMED / MODIFIED findings appear as findings and
REJECTED ones are listed with the partner's reason (SA 230). The AI never recommends an opinion: section 6 lists the
matters for the partner's judgement. Prose cites ids and server-written reasons only.
"""
import hashlib
import html
import json

from app import chain, config, db, money

DRAFT = "DRAFT – NOT REVIEWED BY ENGAGEMENT PARTNER"
S143_12 = 1_00_00_000_00                 # Rs 1 crore: suspected fraud reportable to the Central Government (ADT-4)


def _r(p):
    return money.fmt_inr(p or 0)


def _aje_table(lines):
    out = ["| Account | Party | Dr | Cr |", "|---|---|---:|---:|"]
    for l in lines:
        out.append(f"| {l['account_code']} | {l.get('party_id') or ''} | {_r(l.get('dr_paise')) if l.get('dr_paise') else ''} "
                   f"| {_r(l.get('cr_paise')) if l.get('cr_paise') else ''} |")
    return out


_CHECK = {"D3": "obtain the LR / e-way bill / POD and confirm the delivery terms; confirm goods on hand at the period end",
          "D4": "confirm the goods physically moved (LR, e-way bill on the portal, POD) and who paid",
          "D6": "compare the portal records (IRP, e-way bill, GSTR-1) with the invoice and discuss with the tax team",
          "D7": "obtain the support and approval for the journal; confirm it was not a sale booked by journal",
          "D9": "obtain the credit-note approval, return inward evidence and the original sale; assess the provision",
          "D0": "ask management to correct the register and explain each difference",
          "D1": "obtain management's identification of all transactions with the party (SA 550 para 22)",
          "D2": "correct the related-party disclosure dates; check s.188 approvals",
          "D8": "obtain the original document from an independent source (portal / transporter / customer confirmation)",
          "D10": "trace the goods and money round the cycle; consider s.143(12)",
          "D12": "investigate who edited the records outside the application; consider the control deficiency (SA 265)",
          "D13": "obtain the reason for the late entry / sequence break", "D11": "re-test the stale sample"}


def build(engagement_id, final=None):
    """Write memo.md and memo.html -> {path, html_path, sha256, download_key}. final=None follows the engagement
    (FINAL once SIGNED_OFF)."""
    from app import findings, risk_graph, workpaper
    final = workpaper._is_final(engagement_id, final)
    s450 = findings.sa450_summary(engagement_id)
    with db.borrow("audit", "system") as a:
        eng = dict(a.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone())
        fs = [dict(r) for r in a.execute("SELECT * FROM findings WHERE engagement_id = ? ORDER BY id", (engagement_id,))]
        runs = {r[0]: r[1] for r in a.execute("SELECT kind, count(*) FROM samples s JOIN sample_runs r ON r.id = s.run_id"
                                              " WHERE r.engagement_id = ? GROUP BY kind", (engagement_id,))}
        seeds = [tuple(r) for r in a.execute("SELECT id, kind, seed FROM sample_runs WHERE engagement_id = ? ORDER BY run_at",
                                             (engagement_id,))]
        sampled = a.execute("SELECT COALESCE(SUM(json_extract(p.value, '$.taxable')), 0) FROM sample_runs r, json_each("
                            "r.population_json) p JOIN samples s ON s.run_id = r.id AND s.doc_id = json_extract(p.value, '$.id')"
                            " WHERE r.engagement_id = ? AND r.kind = 'SALES_TOD'", (engagement_id,)).fetchone()[0]
        anchors = [dict(r) for r in a.execute("SELECT label, at FROM anchors WHERE engagement_id = ? ORDER BY id",
                                              (engagement_id,))]
        t_head = chain.head(a, "audit_trail")
        prepared = a.execute("SELECT principal FROM audit_trail WHERE role = 'audit_staff' ORDER BY seq DESC LIMIT 1"
                             ).fetchone()
    with db.borrow("erp", "system") as e:
        pop = e.execute("SELECT count(DISTINCT i.id), COALESCE(SUM(l.taxable_paise), 0) FROM invoices i JOIN invoice_lines l"
                        " ON l.invoice_id = i.id WHERE i.status = 'ISSUED' AND i.invoice_date BETWEEN ? AND ?",
                        (eng["period_start"], eng["period_end"])).fetchone()
        e_head = chain.head(e, "erp_log")
    company = risk_graph.company_band(engagement_id) or {}
    shown = [f for f in fs if f["status"] in ("CONFIRMED", "MODIFIED")] if final else fs
    rejected = [f for f in fs if f["status"] == "REJECTED"]
    by_status = {}
    for f in fs:
        by_status[f["status"]] = by_status.get(f["status"], 0) + 1
    net = sum((-1 if f["code"] == "DELAYED" else 1) * f["taxable_impact_paise"] for f in shown
              if f["proposed_aje_json"] and f["status"] != "REJECTED")
    status = "FINAL" if final else "DRAFT"
    period = f"{eng['period_start']} to {eng['period_end']}"
    anchor_list = ", ".join(x["label"] + " " + x["at"][:16] for x in anchors)
    fraud_like = sum(f["gross_impact_paise"] for f in shown if f["code"] in
                     ("NO_MOVEMENT", "REVENUE_WITHOUT_SALE", "ROUND_TRIP_GOODS", "ROUND_TRIP_CASH", "BELONGS_TO_OTHER_TXN"))
    L = [f"# Findings memorandum: statutory audit of revenue", ""]
    if not final:
        L += [f"**{DRAFT}**", ""]
    L += [f"{eng['entity_name']} · Period {period} · Framework {eng['framework'].replace('_', ' ')} · Prepared by "
          f"{prepared[0] if prepared else 'audit_staff'} ({config.today()}) · Reviewed by "
          f"{eng['signed_by'] + ' (' + (eng['signed_at'] or '')[:10] + ')' if eng['signed_by'] else 'PENDING'} · Status {status}",
          "", "## 1. Scope and approach", "",
          "SA 315/330 risk response; SA 500 analytics over 100% of the books and portals (detectors D0-D14) plus tests of "
          "details; SA 530 sampling with recorded random seeds "
          f"({', '.join(f'{k} {s}' for _i, k, s in seeds) or 'none yet'}); SA 240 journal-entry tests; SA 550 related "
          "parties; SA 560 subsequent events (credit notes after the period end). "
          f"Materiality (SA 320): OM {_r(eng['materiality_paise'])}, PM {_r(eng['performance_materiality_paise'])}, "
          f"clearly trivial {_r(eng['trivial_paise'])}.", "",
          "## 2. Summary", "",
          f"- Population: {pop[0]} invoices, {_r(pop[1])} taxable.",
          f"- Samples: Sales TOD {runs.get('SALES_TOD', 0)}, cut-off {runs.get('CUTOFF_TOD', 0)}, credit notes "
          f"{runs.get('CN_TOD', 0)}; Sales TOD coverage {(100 * (sampled or 0) / pop[1]) if pop[1] else 0:.1f}% of value.",
          f"- Findings by status: {', '.join(f'{k} {v}' for k, v in sorted(by_status.items())) or 'none'}.",
          f"- Net effect on revenue of the findings with adjustments: {_r(net)} (overstatement +).",
          f"- Company risk of material misstatement (AuditGraph, SA 315): {company.get('band', 'not assessed')}"
          f"{'; families ' + ', '.join(company.get('families', [])) if company.get('families') else ''}.", "",
          "## 3. Findings", "",
          "| ID | Category | Standard | Doc refs | Taxable impact | Tax impact | FY | Confidence | Status |",
          "|---|---|---|---|---:|---:|---|---|---|"]
    for f in shown:
        L.append(f"| {f['id']} | {f['category']} | {(f['standards'] or '').split(';')[0]} | "
                 f"{', '.join(json.loads(f['doc_refs_json'] or '[]'))} | {_r(f['taxable_impact_paise'])} | "
                 f"{_r(f['tax_impact_paise'])} | {f['affected_fy'] or ''} | {f['confidence']} | {f['status']} |")
    L.append("")
    L += ["## 4. Findings in detail", ""]
    for f in shown:
        lines = json.loads(f["proposed_aje_json"]) if f["proposed_aje_json"] else None
        L += [f"### {f['id']} · {f['title']}", "", f"**What we found.** {f['explanation']}", "",
              f"**Why it matters.** {f['standards']}", "",
              f"**Evidence.** Documents {', '.join(json.loads(f['doc_refs_json'] or '[]'))}; risk hits "
              f"{', '.join(map(str, json.loads(f['evidence_json'] or '{}').get('hits', [])))}.", "",
              f"**Impact.** Taxable {_r(f['taxable_impact_paise'])}, tax {_r(f['tax_impact_paise'])}, gross "
              f"{_r(f['gross_impact_paise'])}; FY {f['affected_fy'] or '-'}.", "",
              "**Proposed adjusting entry.**" + (" None: disclosure / correction only." if not lines else ""), ""]
        if lines:
            L += _aje_table(lines) + [""]
        L += [f"**What the partner should check.** {_CHECK.get(f['detector'], 'review the evidence')}.", "",
              f"**Partner decision.** {f['status']}{' - ' + f['decision_note'] if f['decision_note'] else ''}", "",
              "**Management response.** ", ""]
    if final and rejected:
        L += ["### Rejected by the engagement partner", ""] + [f"- {f['id']} ({f['category']}): {f['decision_note']}"
                                                               for f in rejected] + [""]
    L += ["## 5. Uncorrected misstatements (SA 450)", "",
          f"- Factual: {_r(s450['factual_paise'])}", f"- Judgemental: {_r(s450['judgemental_paise'])}",
          f"- Projected (REPRESENTATIVE stratum only, never KEY): {_r(s450['projected_paise'])}",
          f"- Total {_r(s450['total_paise'])} against materiality {_r(s450['materiality_paise'])}: "
          f"{'EXCEEDS materiality' if s450['exceeds'] else 'below materiality'}.", "",
          "## 6. Matters for the partner's judgement", "",
          "- Possible modification of the opinion (SA 705) if uncorrected misstatements are material. The AI does not "
          "recommend an opinion.",
          f"- Companies Act 2013 s.143(12): suspected fraud of Rs 1 crore or more is reported to the Central Government "
          f"(ADT-4), below that to the audit committee / board; CARO 2020 cl. 3(xi). Findings of fictitious-sale type "
          f"total {_r(fraud_like)}{' (at or above Rs 1 crore)' if fraud_like >= S143_12 else ''}.",
          "- Related-party disclosure (Ind AS 24) and s.188 approvals for every related or undisclosed party found.",
          "- Control deficiencies to communicate (SA 265): records edited outside the application, journals posted to "
          "revenue without a sale, and any single user creating a customer, its invoice and its credit note.", "",
          "## 7. Integrity statement", "",
          f"- erp_log head: seq {e_head[0]} / {e_head[1][:12]}; audit_trail head: seq {t_head[0]} / {t_head[1][:12]}.",
          f"- Anchors: {anchor_list or 'none'}."]
    wb = _workbook_sha(engagement_id)
    if wb:
        L.append(f"- Workbook SHA-256: {wb}.")
    L += ["", "## 8. Sign-off", "",
          (f"Signed off by {eng['signed_by']} on {(eng['signed_at'] or '')[:10]}." if final and eng["signed_by"] else
           "Awaiting the engagement partner's review and sign-off (web UI)."), ""]
    md = "\n".join(L)
    out = config.AUDIT_FILES_DIR / engagement_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "memo.md").write_text(md, encoding="utf-8")
    (out / "memo.html").write_text(_html(md, final), encoding="utf-8")
    return {"path": str(out / "memo.md"), "html_path": str(out / "memo.html"),
            "sha256": hashlib.sha256(md.encode()).hexdigest(), "download_key": ""}


def _workbook_sha(eid):
    p = config.AUDIT_FILES_DIR / eid / "workpaper.xlsx"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _html(md, final, title="Findings memorandum"):
    out, table = [], []

    def flush():
        if table:
            rows = [r for r in table if not set(r.replace("|", "").strip()) <= set("-: ")]
            out.append("<table>" + "".join(
                "<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{html.escape(c.strip())}</{'th' if i == 0 else 'td'}>"
                                 for c in r.strip().strip("|").split("|")) + "</tr>" for i, r in enumerate(rows)) + "</table>")
            table.clear()
    for line in md.splitlines():
        if line.startswith("|"):
            table.append(line)
            continue
        flush()
        if line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- "):
            out.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip():
            t = html.escape(line)
            t = t.replace("**", "<b>", 1).replace("**", "</b>", 1) if t.count("**") >= 2 else t
            out.append(f"<p>{t}</p>")
    flush()
    banner = "" if final else f'<div class="draft">{DRAFT}</div>'
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>"
            "body{font-family:Georgia,serif;max-width:900px;margin:2em auto;line-height:1.45}table{border-collapse:collapse;"
            "width:100%;font-size:.9em}td,th{border:1px solid #999;padding:4px 6px}th{background:#eee}"
            ".draft{background:#c00;color:#fff;font-weight:bold;padding:.5em;text-align:center}"
            "@media print{.draft{-webkit-print-color-adjust:exact}}</style></head><body>" + banner + "".join(out) +
            "</body></html>")
