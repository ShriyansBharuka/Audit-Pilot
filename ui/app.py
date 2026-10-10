"""AuditPilot AI web app (Streamlit). Run: streamlit run ui/app.py   (needs: python -m app.mcp_server running)

Login by token. Client roles get the client portal; audit_staff gets the auditor workspace incl. the
Audit Investigation Explorer (Network View, Transaction Timeline, Evidence & Change History); the engagement
partner gets the review queue and sign-off. All actions except the partner's go through the MCP server.
"""
import asyncio
import base64
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import explorer, investigator, money, partner  # noqa: E402
from ui.mcp_client import MCP_URL, ToolFailed, call  # noqa: E402

st.set_page_config(page_title="AuditPilot AI", page_icon="🔎", layout="wide")
CLIENT_ROLES = {"sales", "warehouse", "accounts", "client_admin"}
BAND_COLOUR = {"HIGH": "#d62728", "REVIEW": "#ff7f0e", "MODERATE": "#ff7f0e", "LOW": "#2ca02c"}


def inr(p):
    return "—" if p is None else money.fmt_inr(int(p))


def tool(name, args=None, quiet=False):
    """Call an MCP tool as the logged-in user; show the server's message on refusal."""
    try:
        return call(st.session_state.token, name, args or {})
    except ToolFailed as e:
        if not quiet:
            st.error(str(e))
        return None


def band(score):
    s = score or 0
    return "HIGH" if s >= 60 else "REVIEW" if s >= 30 else "LOW"


def cd(item, key):
    """A field that may sit under client_data (untrusted client text, shown as data)."""
    return item.get(key) if key in item else (item.get("client_data") or {}).get(key)

def flat(rows):
    """Table-safe rows: client_data fields become columns (still shown as data); nested values become JSON text."""
    out = []
    for r in rows or []:
        r = dict(r)
        r.update({f"client: {k}": v for k, v in (r.pop("client_data", None) or {}).items()})
        out.append({k: json.dumps(v, default=str) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    return out

# ------------------------------------------------------------------ login + landing


def login():
    st.title("🔎 AuditPilot AI")
    st.caption("AI-run statutory revenue audit · ELEVATE 1.0 · PS-04 · risk engine: AuditGraph")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(
            "**Audit the business, not the spreadsheet.** A mini ERP with a tamper-evident ledger and mock GST "
            "portals; every sale tested against the register the client uploads (detectors D0–D14); AuditGraph "
            "risk scores per transaction and per company; risk-based samples, automatic evidence requests, the "
            "4-sheet workpaper, a findings memo and a hash-chained audit trail. A human partner signs off.")
        st.markdown(f"**Connect your own AI agent (MCP):** `{MCP_URL}` with header "
                    "`Authorization: Bearer <token>`. Example: `claude mcp add --transport http auditpilot "
                    f"{MCP_URL} --header \"Authorization: Bearer aud_…\"`")
    with c2:
        tok = st.text_input("Your token (from the judge card)", type="password")
        if st.button("Sign in", type="primary") and tok:
            try:
                rec = partner.identity(tok)
            except LookupError:
                st.error("Unknown token.")
                return
            st.session_state.update(token=tok.strip(), role=rec["role"], name=rec.get("name", rec["principal"]),
                                    principal=rec["principal"])
            st.rerun()

# ------------------------------------------------------------------ client portal


def client_portal():
    st.header("Client portal")
    st.caption("Upload the sales register and related-party list, and answer the auditor's evidence requests. "
               "Files are stored exactly as sent; the server computes their fingerprints.")
    t1, t2 = st.tabs(["Upload register / related parties", "Evidence requests"])
    with t1:
        f = st.file_uploader("Sales register (.xlsx or .csv)", type=["xlsx", "csv"], key="reg")
        if f and st.button("Send sales register"):
            raw = f.getvalue()
            args = ({"csv_text": raw.decode("utf-8-sig"), "filename": f.name} if f.name.lower().endswith(".csv")
                    else {"content_base64": base64.b64encode(raw).decode(), "filename": f.name})
            r = tool("upload_sales_register", args)
            if r:
                st.success("Register received; the auditor has been notified.")
                st.json(r.get("summary", r))
        g = st.file_uploader("Related-party list (.xlsx or .csv)", type=["xlsx", "csv"], key="rp")
        if g and st.button("Send related-party list"):
            raw = g.getvalue()
            args = ({"csv_text": raw.decode("utf-8-sig"), "filename": g.name} if g.name.lower().endswith(".csv")
                    else {"content_base64": base64.b64encode(raw).decode(), "filename": g.name})
            r = tool("upload_related_parties", args)
            if r:
                st.success("Related-party list received.")
    with t2:
        r = tool("list_evidence_requests", {"limit": 100})
        items = (r or {}).get("items", [])
        if not items:
            st.info("No evidence requests yet.")
        for q in items:
            with st.expander(f"{q.get('sample_ref')} · {q.get('doc_kind')} for {q.get('about_doc_no')} · "
                             f"{q.get('status')} · due {q.get('due_on')}"):
                up = st.file_uploader("Document (PDF / image)", key=f"ev{q['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Upload this file", key=f"u{q['id']}") and up:
                    tool("upload_evidence", {"request_id": q["id"], "filename": up.name,
                                             "content_base64": base64.b64encode(up.getvalue()).decode()})
                    st.rerun()
                if c2.button("Attach the system's official copy", key=f"e{q['id']}"):
                    tool("upload_evidence", {"request_id": q["id"], "from_erp": True})
                    st.rerun()

# ------------------------------------------------------------------ auditor: overview


def overview():
    st.header("Engagement overview")
    s = tool("get_engagement_status") or {}
    sm = s.get("summary", {})
    if not sm.get("engagement_id"):
        st.info(sm.get("message", "No client upload yet."))
        return
    comp = sm.get("company_risk") or {}
    c = st.columns(5)
    c[0].metric("Company risk (SA 315)", comp.get("band", "—"))
    c[1].metric("Register rows", sm.get("register_rows", 0))
    c[2].metric("Risk hits", sum((sm.get("risk_hits_by_detector") or {}).values()))
    c[3].metric("Samples tested", f"{sm.get('samples', {}).get('tested', 0)}/{sm.get('samples', {}).get('total', 0)}")
    c[4].metric("Findings", sum((sm.get("findings") or {}).values()))
    if comp:
        st.caption(f"Exposure {inr(comp.get('exposure_paise'))} · families hit {comp.get('families')} · "
                   f"circular value {inr(comp.get('circular_paise'))}")
    st.subheader("Run the audit")
    b = st.columns(6)
    actions = [("Reconcile register ↔ books", "reconcile_register_to_system", {}),
               ("Run 100% analytics", "run_analytics", {}),
               ("Select Sales TOD", "select_samples", {"kind": "sales_tod"}),
               ("Select cut-off TOD", "select_samples", {"kind": "cutoff"}),
               ("Select credit-note TOD", "select_samples", {"kind": "credit_note"}),
               ("Check changes & integrity", "verify_integrity", {})]
    for col, (label, name, args) in zip(b, actions):
        if col.button(label, width="stretch"):
            r = tool(name, args)
            if r:
                st.session_state.last = (label, r)
    if st.session_state.get("last"):
        label, r = st.session_state.last
        with st.expander(f"Result: {label}", expanded=True):
            st.json(r.get("summary", r))
            if r.get("items"):
                st.dataframe(flat(r["items"]), width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Risk hits by detector**")
        st.bar_chart(sm.get("risk_hits_by_detector") or {})
    with c2:
        st.markdown("**Top exception codes**")
        st.dataframe([{"code": k, "count": v} for k, v in (sm.get("top_codes") or {}).items()],
                     width="stretch", hide_index=True)
    st.markdown("**Next steps**")
    for n in s.get("next_steps", []):
        st.write(f"→ `{n['tool']}`: {n['why']}")

# ------------------------------------------------------------------ auditor: Investigation Explorer


def _dot(nodes, edges, focus):
    lines = ['digraph G { rankdir=LR; node [style=filled, fontname="Helvetica", fontsize=10];']
    esc = lambda s: str(s).replace('"', "'")
    for n in nodes:
        score = n.get("R") if n.get("R") is not None else n.get("E")
        col = BAND_COLOUR.get(n.get("band") or band(score), "#999999")
        label = f"{n['id']}\\n{esc(cd(n, 'label') or '')[:24]}\\nrisk {score if score is not None else '—'}"
        pen = 3 if n["id"] == focus else 1
        lines.append(f'"{esc(n["id"])}" [label="{label}", fillcolor="{col}44", color="{col}", penwidth={pen}];')
    for e in edges:
        style = "dashed" if e.get("kind") in ("SHARED_ID", "DIRECTOR", "RELATIVE", "CONTROL") else "solid"
        amt = f"\\n{inr(e['amount_paise'])}" if e.get("amount_paise") else ""
        lines.append(f'"{esc(e["a"])}" -> "{esc(e["b"])}" [label="{e.get("kind", "")}{amt}", style={style}, fontsize=8];')
    return "\n".join(lines + ["}"])


def network_view():
    st.markdown("Start from a suspicious company, follow its connections, then open a transaction. "
                "Solid edges are observed transactions; dashed edges are identity links (shared PAN/bank/phone/"
                "director). Colour = risk band.")
    c1, c2 = st.columns([1, 3])
    min_risk = c1.slider("Minimum risk", 0, 100, 30, 5)
    focus = st.session_state.get("focus_party")
    g = tool("get_risk_graph", {"min_risk": 0 if focus else min_risk, "focus_party": focus, "limit": 150})
    if not g:
        return
    nodes, edges = g.get("items", []), g.get("edges", [])
    comp = (g.get("summary") or {}).get("company") or {}
    c1.metric("Company risk", comp.get("band", "—"))
    if focus:
        c1.info(f"Focused on {focus}")
        if c1.button("Clear focus"):
            st.session_state.focus_party = None
            st.rerun()
    with c2:
        if nodes:
            st.graphviz_chart(_dot(nodes, edges, focus), width="stretch")
        else:
            st.info("No nodes at this risk level yet (run analytics first).")
    st.markdown("**Entities and transactions in view**: select a row to drill in")
    table = [{"id": n["id"], "type": n.get("type"), "name": cd(n, "label"), "risk": n.get("R", n.get("E")),
              "confidence": n.get("C"), "band": n.get("band") or band(n.get("R", n.get("E")))} for n in nodes]
    ev = st.dataframe(table, width="stretch", hide_index=True, on_select="rerun", selection_mode="single-row")
    rows = ev.selection.rows if ev and ev.selection else []
    if rows:
        pick = table[rows[0]]
        if str(pick["type"]).lower() in ("party", "person", "self", "entity"):
            if st.button(f"Focus the graph on {pick['id']}"):
                st.session_state.focus_party = pick["id"]
                st.rerun()
        else:
            if st.button(f"Open transaction {pick['id']} in the timeline"):
                st.session_state.focus_invoice = pick["id"]
                st.rerun()
    if g.get("cycles"):
        st.markdown("**Circular flows (minimum-span decomposition)**")
        st.dataframe([{"members": " → ".join(c.get("members", [])), "circular value": inr(c.get("circular_paise")),
                       "span (days)": c.get("span_days")} for c in g["cycles"]], width="stretch", hide_index=True)


def _events(t):
    """trace_sale -> chronological paper trail [(date, stage, detail)]."""
    so, inv = t.get("sales_order") or {}, t.get("invoice") or {}
    ev = []
    add = lambda d, s, x: d and ev.append({"date": str(d)[:19], "stage": s, "detail": x})
    add(so.get("enquired_on"), "Enquiry", f"SO {so.get('id', '')} · channel {so.get('channel', '')}")
    add(so.get("quoted_on"), "Quotation", "")
    add(so.get("confirmed_on"), "Order confirmed", f"terms {so.get('delivery_terms', '')}, credit {so.get('credit_days', '')} d")
    add(inv.get("invoice_date"), "Invoice", f"{inv.get('invoice_no', '')} · taxable {inr(t.get('taxable_paise'))} · "
        f"total {inr(t.get('total_paise'))} · {inv.get('status', '')}")
    irn = t.get("einvoice") or {}
    add(irn.get("ack_at"), "IRN (e-invoice portal)", f"{str(irn.get('irn', ''))[:16]}… · {irn.get('status', '')}")
    for w in t.get("ewaybills") or []:
        add(w.get("generated_at"), "E-way bill (portal)", f"{w.get('ewb_no')} · {inr(w.get('value_paise'))} · vehicle "
            f"{w.get('vehicle_no')} · {w.get('status')}")
    for m in t.get("movements") or []:
        add(m.get("moved_on"), "Dispatch", f"{m.get('id')} · LR {m.get('lr_no')} ({m.get('lr_date')}) · vehicle "
            f"{m.get('vehicle_no')} · {m.get('direction', 'OUT')}")
        add(m.get("delivered_on"), "Delivery (POD)", f"{m.get('id')} · control transfers if FOR-destination")
    for gr in t.get("gstr1") or []:
        add(gr.get("filed_at"), "GSTR-1 filed", f"period {gr.get('period')} · taxable {inr(gr.get('taxable_paise'))}")
    for s in t.get("settlements") or []:
        add(s.get("settled_on"), "Payment received", f"{inr(s.get('amount_paise'))} · bank txn {s.get('bank_txn_id')}")
    for cn in t.get("credit_notes") or []:
        add(cn.get("cn_date"), "Credit note", f"{cn.get('cn_no', cn.get('id'))} · {cn.get('reason', '')}")
    for j in t.get("journals") or []:
        add(j.get("voucher_date"), "Ledger posting", f"journal {j.get('no')} · {j.get('voucher_type')}")
    return sorted(ev, key=lambda e: e["date"])


def timeline_view():
    focus = st.session_state.get("focus_party")
    c1, c2 = st.columns([2, 3])
    if focus:
        inv = tool("query_records", {"entity": "invoices", "filters": {"party_id": focus}, "limit": 100}) or {}
        options = [i.get("invoice_no") for i in inv.get("items", [])]
        c1.caption(f"Invoices of {focus}")
        pick = c1.selectbox("Invoice", options) if options else None
    else:
        pick = None
    typed = c2.text_input("…or type an invoice number / id", st.session_state.get("focus_invoice") or "")
    invoice = typed or pick
    if not invoice:
        st.info("Pick a company in the Network View, or type an invoice number.")
        return
    st.session_state.focus_invoice = invoice
    t = tool("trace_sale", {"invoice": invoice})
    if not t:
        return
    t = t.get("summary", t) if "invoice" not in t else t
    inv = t.get("invoice") or {}
    st.subheader(f"Paper trail · {inv.get('invoice_no', invoice)}")
    if t.get("gaps"):
        st.error("Missing links: " + ", ".join(map(str, t["gaps"])))
    st.dataframe(_events(t), width="stretch", hide_index=True)
    hist = explorer.risk_history(st.session_state.role, "INVOICE", inv.get("id", invoice))
    if hist:
        st.markdown("**AuditGraph risk over time** (snapshots are never overwritten)")
        st.line_chart({"R (risk)": [h["R"] for h in hist], "A (own anomalies)": [h["A"] for h in hist],
                       "E (counterparty)": [h["E"] for h in hist]})
        st.dataframe([{"at": h["at"], "trigger": h["run_id"], "band": h["band"], "R": h["R"], "confidence": h["C"],
                       "why": "; ".join(map(str, h["reasons"]))[:300]} for h in hist],
                     width="stretch", hide_index=True)
    else:
        st.caption("No AuditGraph snapshots for this invoice yet.")


def _diff(before, after):
    try:
        b, a = json.loads(before or "{}"), json.loads(after or "{}")
    except ValueError:
        return "(content truncated for display)"
    if not isinstance(b, dict) or not isinstance(a, dict):
        return ""
    keys = sorted(set(b) | set(a))
    return "; ".join(f"{k}: {b.get(k)!r} → {a.get(k)!r}" for k in keys if b.get(k) != a.get(k))[:400]


def evidence_view():
    invoice = st.session_state.get("focus_invoice")
    if not invoice:
        st.info("Open a transaction first (Network View or Transaction Timeline).")
        return
    t = tool("trace_sale", {"invoice": invoice}, quiet=True) or {}
    inv = t.get("invoice") or {}
    inv_id, inv_no = inv.get("id", invoice), inv.get("invoice_no", invoice)
    st.subheader(f"Why {inv_no} is risky")
    hits = tool("list_audit_items", {"kind": "risk_hits", "filters": {"object_id": inv_id}, "limit": 50}) or {}
    if hits.get("items"):
        st.dataframe([{"detector": h.get("detector"), "code": h.get("code"), "severity": h.get("severity"),
                       "impact": inr(h.get("impact_paise")), "reason": h.get("reason")} for h in hits["items"]],
                     width="stretch", hide_index=True)
    else:
        st.caption("No detector hits on this invoice.")
    with st.expander("🤖 AuditPilot investigator: a GPT agent that is just another MCP client (auditor token)"):
        ok, why = investigator.ready()
        if not ok:
            st.caption(f"Off: {why}. Deterministic detectors above already decide every finding.")
        elif st.button("Investigate this transaction", key="inv_run"):
            task, target = investigator.task_for(invoice=inv_no)
            with st.spinner("Investigating through the MCP server (every tool call is in the audit trail)…"):
                try:
                    r = asyncio.run(investigator.investigate(task, save_note=("risk_hit", inv_id)))
                    st.caption(f"model {r['model']} · {r['tool_calls']} tool calls · cost ${r['usd']}")
                    st.json(r["investigation"])
                except Exception as e:  # noqa: BLE001 - surface caps / config errors to the auditor
                    st.error(str(e))
    st.subheader("Supporting documents")
    for q in explorer.evidence_for(st.session_state.role, inv_no):
        st.markdown(f"**{q['doc_kind']}** · request {q['id']} ({q['status']}, due {q['due_on']})")
        for s in q["submissions"]:
            st.write(f"• `{s['filename']}` · sha256 `{s['sha256'][:16]}…` · by {s['submitted_by']} at {s['submitted_at']}")
    c = st.columns(4)
    for col, kind in zip(c, ("INVOICE", "EWAY_BILL", "LR", "POD")):
        if col.button(f"View system copy: {kind}", key=f"rd{kind}"):
            st.session_state.render = tool("render_document", {"doc_type": kind, "id": inv_no}, quiet=True)
    if st.session_state.get("render"):
        r = st.session_state.render
        st.code(cd(r, "text") or json.dumps(r.get("summary", r), indent=1)[:3000])
    st.subheader("Change history (hash-chained edit log)")
    ids = [inv_id] + [m.get("id") for m in t.get("movements") or []] + [(t.get("sales_order") or {}).get("id")]
    rows = []
    for d in filter(None, ids):
        log = tool("query_records", {"entity": "erp_log", "filters": {"doc_id": d}, "limit": 50}, quiet=True) or {}
        for e in log.get("items", []):
            rows.append({"seq": e.get("seq"), "at": e.get("recorded_at"), "doc": f"{e.get('doc_type')} {e.get('doc_id')}",
                         "action": e.get("action"), "by": f"{e.get('actor')} ({e.get('role')})", "tool": e.get("tool"),
                         "change": _diff(cd(e, "before_json"), cd(e, "after_json")) if e.get("action") == "AMEND" else "",
                         "reason": cd(e, "reason")})
    st.dataframe(sorted(rows, key=lambda r: r["seq"] or 0), width="stretch", hide_index=True)
    ch = tool("check_for_changes", {"limit": 100}, quiet=True) or {}
    mine = [c for c in ch.get("items", []) if str(c.get("pk")) in map(str, ids) or inv_no in map(str, c.get("affected_samples", []))]
    if mine:
        st.warning("Changed after testing began: these samples are stale and must be re-tested.")
        st.dataframe(flat(mine), width="stretch")


def explorer_page():
    st.header("Audit Investigation Explorer")
    tabs = st.tabs(["🕸 Network View", "🧾 Transaction Timeline", "📎 Evidence & Change History"])
    with tabs[0]:
        network_view()
    with tabs[1]:
        timeline_view()
    with tabs[2]:
        evidence_view()

# ------------------------------------------------------------------ auditor: workpaper


def workpaper_page():
    st.header("Workpaper")
    sheet = st.selectbox("Sheet", ["sales_register", "sales_tod", "cutoff_tod", "cn_tod"],
                         format_func={"sales_register": "Sales Register", "sales_tod": "Sales TOD",
                                      "cutoff_tod": "Sales Cut-off TOD", "cn_tod": "Credit Note TOD"}.get)
    page = st.number_input("Page", 0, 10_000, 0)
    r = tool("get_workpaper_sheet", {"sheet": sheet, "limit": 50, "cursor": str(page * 50) if page else None})
    if r:
        st.json(r.get("summary", {}))
        st.dataframe(flat(r.get("items", [])), width="stretch")
    c1, c2 = st.columns(2)
    if c1.button("Generate deliverables (xlsx + memo + trail)"):
        st.session_state.deliv = tool("generate_deliverables")
    if c2.button("Submit for partner review"):
        st.session_state.deliv = tool("submit_for_partner_review")
    if st.session_state.get("deliv"):
        st.json(st.session_state.deliv.get("summary", st.session_state.deliv))

# ------------------------------------------------------------------ partner


def partner_page():
    st.header("Engagement partner review")
    st.caption("Only a human partner decides findings and signs off. This page is not reachable by any AI agent: "
               "the partner token is refused by the MCP server.")
    tok = st.session_state.token
    queue = partner.review_queue(tok)
    st.metric("Findings awaiting decision", sum(1 for f in queue if f["status"] == "PROPOSED"))
    for f in queue:
        with st.expander(f"{f['id']} · {f['status']} · {f['title']} · gross {inr(f['gross_impact_paise'])}",
                         expanded=f["status"] == "PROPOSED"):
            st.write(f["explanation"])
            st.caption(f"{f.get('standards') or ''} · confidence {f['confidence']} · FY {f.get('affected_fy') or ''}")
            if f.get("proposed_aje_json"):
                st.dataframe(json.loads(f["proposed_aje_json"]), width="stretch", hide_index=True)
            if f["status"] == "PROPOSED":
                note = st.text_input("Comment (required)", key=f"n{f['id']}")
                c = st.columns(3)
                for col, d in zip(c, ("CONFIRM", "REJECT", "MODIFY")):
                    if col.button(d.title(), key=f"{d}{f['id']}"):
                        try:
                            partner.decide_finding(tok, f["id"], d, note)
                            st.rerun()
                        except (ValueError, LookupError, PermissionError) as e:
                            st.error(str(e))
            else:
                st.caption(f"Decided by {f.get('decided_by')} at {f.get('decided_at')}: {f.get('decision_note')}")
    st.subheader("Sign-off")
    block = partner.blockers()
    if block:
        st.warning("Sign-off is blocked: " + "; ".join(block))
    concl = st.text_area("Partner's conclusion")
    if st.button("Sign off the engagement", type="primary", disabled=bool(block)):
        try:
            r = partner.sign_off(tok, concl)
            st.success(f"Signed off by {r['signed_by']}. Sign-off hash {r['signoff_hash'][:16]}…")
        except (ValueError, LookupError, PermissionError) as e:
            st.error(str(e))

# ------------------------------------------------------------------ router


def main():
    if "token" not in st.session_state:
        login()
        return
    role = st.session_state.role
    st.sidebar.markdown(f"**{st.session_state.name}**  \n`{role}`")
    if st.sidebar.button("Sign out"):
        st.session_state.clear()
        st.rerun()
    if role in CLIENT_ROLES:
        client_portal()
    elif role == "audit_staff":
        page = st.sidebar.radio("Auditor workspace", ["Overview", "Investigation Explorer", "Workpaper"])
        {"Overview": overview, "Investigation Explorer": explorer_page, "Workpaper": workpaper_page}[page]()
    elif role == "engagement_partner":
        partner_page()
    else:
        st.info(f"The `{role}` identity has no web pages (it works through MCP only).")


main()
