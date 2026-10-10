"""SH-4 services + IB-3 portal on a tiny company: one sale end to end, the [F] rules, the portal's own rules."""
import base64
import sqlite3

import pytest

from app import chain, config, db, erp, ledger, portal, register

ADM, ACC, WHS, SAL = ("adm.kiran", "client_admin"), ("acc.neha", "accounts"), ("whs.ganesh", "warehouse"), ("sales.priya", "sales")
MH_GSTIN, KA_GSTIN = "27AAPFU0939F1ZV", "29AAGCB7383J1Z4"


def at(ts):
    config.set_clock(ts)


@pytest.fixture()
def co(world):
    at("2025-03-01T10:00:00+05:30")
    erp.create_party(*ADM, id="SELF", tags="SELF", name="Konkan Marine Controls Ltd", gstin=config.UNITS["G2"]["gstin"],
                     state_code="27", bank_account="50100012345678", ifsc="HDFC0001234")
    erp.create_party(*SAL, id="P-0001", name="Arabian Shipyards Pvt Ltd", gstin=MH_GSTIN, pincode="400001",
                     bank_account="111122223333", ifsc="ICIC0000001")
    erp.create_party(*SAL, id="P-0002", name="Karwar Dredging Pvt Ltd", gstin=KA_GSTIN, pincode="581301")
    erp.create_party(*ADM, id="P-TRN1", tags="TRANSPORTER", name="Sahyadri Roadlines")
    erp.create_item(*ADM, id="IT-001", name="Butterfly valve DN50", hsn="8481", gst_rate_bp=1800, list_rate_paise=680000)
    erp.create_item(*ADM, id="IT-099", name="AMC", hsn="998719", gst_rate_bp=1800, list_rate_paise=24000000)
    return world


def sale(party="P-0001", qty=10, inv_date="2026-03-28", terms="FOR_DISPATCH"):
    at(f"{inv_date}T09:30:00+05:30")
    so = erp.create_sales_order(*SAL, party_id=party, channel="EMAIL", enquired_on="2026-03-01", quoted_on="2026-03-03",
                                confirmed_on="2026-03-05", delivery_terms=terms, credit_days=30,
                                lines=[{"item_id": "IT-001", "qty": qty, "rate_paise": 680000, "discount_paise": 0}])
    at(f"{inv_date}T11:00:00+05:30")
    return erp.issue_invoice(*ACC, so_id=so["result"]["id"], series="G2", invoice_date=inv_date)["result"]


def test_one_sale_end_to_end_and_trace(co):
    inv = sale()
    assert inv["invoice_no"] == "G2/0001/25" and inv["taxable_paise"] == 6800000 and inv["tax_paise"] == 1224000
    at("2026-03-28T12:00:00+05:30")
    ewb = erp.generate_eway_bill(*WHS, invoice_id=inv["id"], vehicle_no="MH08AB1234", distance_km=410,
                                 transport_doc_no="SRL/26/00001")["result"]
    assert len(ewb["ewb_no"]) == 12 and ewb["valid_upto"].startswith("2026-03-31")      # 3 days for 410 km
    mv = erp.record_dispatch(*WHS, invoice_nos=[inv["invoice_no"]], moved_on="2026-03-28", transporter_id="P-TRN1",
                             vehicle_no="MH08AB1234", lr_no="SRL/26/00001", ewb_no=ewb["ewb_no"])["result"]
    erp.record_delivery(*WHS, movement_id=mv["id"], delivered_on="2026-03-30", received_by="stores")
    at("2026-04-11T10:00:00+05:30")
    erp.file_gstr1(*ACC, period="202603")
    erp.record_receipt(*ACC, amount_paise=inv["total_paise"], invoice_nos=[inv["invoice_no"]], settled_on="2026-04-20")
    t = erp.trace_sale("audit_staff", inv["invoice_no"])
    assert t["gaps"] == []
    assert t["sales_order"]["enquired_on"] == "2026-03-01" and t["movements"][0]["delivered_on"] == "2026-03-30"
    assert t["einvoice"]["irn"] == portal.irn_of(config.UNITS["G2"]["gstin"], "2025-26", "INV", "G2/0001/25")
    assert t["ewaybills"][0]["value_paise"] == 8024000 and t["gstr1"][0]["taxable_paise"] == 6800000
    assert [j["voucher_type"] for j in t["journals"]] == ["SALES"] and t["settlements"][0]["amount_paise"] == 8024000
    c = db.connect("erp", "audit_staff")
    assert ledger.trial_balance(c, "2026-04-30")["DEBTORS"] == 0
    assert chain.verify(c, "erp_log")["valid"] and erp.out_of_band(c) == []
    c.close()


def test_tax_split_numbering_and_services(co):
    a = sale(qty=1, inv_date="2026-03-01")
    b = sale(party="P-0002", qty=1, inv_date="2026-03-02")                 # Karnataka: inter-state -> IGST
    c_ = sale(qty=1, inv_date="2026-04-01")                                # new FY -> numbering restarts
    assert (a["invoice_no"], b["invoice_no"], c_["invoice_no"]) == ("G2/0001/25", "G2/0002/25", "G2/0001/26")
    c = db.connect("erp", "audit_staff")
    la = c.execute("SELECT igst_paise, cgst_paise, sgst_paise FROM invoice_lines WHERE invoice_id = ?", (a["id"],)).fetchone()
    lb = c.execute("SELECT igst_paise, cgst_paise, sgst_paise FROM invoice_lines WHERE invoice_id = ?", (b["id"],)).fetchone()
    assert tuple(la) == (0, 61200, 61200) and tuple(lb) == (122400, 0, 0)
    c.close()
    svc = erp.issue_invoice(*ACC, party_id="P-0001", series="G2", invoice_date="2026-03-03",
                            lines=[{"item_id": "IT-099", "qty": 1, "rate_paise": 24000000}])
    assert svc["next_steps"][0]["tool"] == "record_receipt"                     # services don't move
    c = db.connect("erp", "audit_staff")
    acct = c.execute("SELECT account_code FROM journal_lines l JOIN journals j ON j.no = l.journal_no WHERE j.source_id = ?"
                     " AND l.cr_paise > 0 AND account_code LIKE 'SALES%'", (svc["result"]["id"],)).fetchone()[0]
    assert acct == "SALES_SERVICE"
    c.close()


def test_financial_documents_are_never_amended(co):
    inv = sale()
    with pytest.raises(ValueError) as e:
        erp.amend_record(*ADM, entity="invoices", id=inv["id"], changes={"invoice_date": "2026-04-02"}, reason="x")
    assert "cancel_document" in str(e.value) and "issue_credit_note" in str(e.value)
    with pytest.raises(PermissionError):
        erp.amend_record(*ACC, entity="movements", id="MV-000001", changes={"lr_date": "2026-04-02"}, reason="x")
    mv = erp.record_dispatch(*WHS, invoice_nos=[inv["id"]], moved_on="2026-03-28", lr_no="LR1")["result"]
    erp.amend_record(*WHS, entity="movements", id=mv["id"], changes={"lr_date": "2026-04-02"}, reason="typo")
    c = db.connect("erp", "audit_staff")
    last = c.execute("SELECT action, actor, reason, before_json, after_json FROM erp_log ORDER BY seq DESC LIMIT 1").fetchone()
    assert last["action"] == "AMEND" and last["actor"] == "whs.ganesh" and last["reason"] == "typo"
    assert '"lr_date":"2026-03-28"' in last["before_json"] and '"lr_date":"2026-04-02"' in last["after_json"]
    c.close()


def test_cancel_reverses_and_the_irp_refuses_after_24h(co):
    inv = sale(inv_date="2026-03-28")
    at("2026-03-28T20:00:00+05:30")                                       # within 24 h: IRN cancelled too
    r = erp.cancel_document(*ACC, doc_type="invoice", id=inv["invoice_no"], reason="wrong customer")["result"]
    assert r["irn"] == "CNL" and len(r["reversal_journals"]) == 1
    inv2 = sale(inv_date="2026-03-29")
    at("2026-04-05T10:00:00+05:30")                                       # 7 days later: the portal refuses
    r2 = erp.cancel_document(*ACC, doc_type="invoice", id=inv2["id"], reason="late", cancelled_on="2026-04-05")["result"]
    assert r2["irn"].startswith("REFUSED") and r2["status"] == "CANCELLED"
    x = db.connect("ext", "audit_staff")
    assert x.execute("SELECT status FROM einvoices WHERE doc_no = ?", (inv2["invoice_no"],)).fetchone()[0] == "ACT"
    x.close()
    c = db.connect("erp", "audit_staff")
    assert ledger.trial_balance(c, "2026-04-30").get("SALES", 0) == 0
    c.close()
    with pytest.raises(ValueError, match="CONFLICT"):
        erp.cancel_document(*ACC, doc_type="invoice", id=inv2["id"], reason="again")


def test_portal_rules(co):
    inv = sale()
    x = db.connect("ext", "audit_staff")
    row = dict(x.execute("SELECT * FROM einvoices").fetchone())
    x.close()
    assert row["irn"] == portal.irn_of(row["supplier_gstin"], "2025-26", "INV", row["doc_no"]) and portal.verify_signature(row)
    assert not portal.verify_signature({**row, "total_paise": row["total_paise"] + 1})
    with pytest.raises(portal.Refused, match="duplicate"):
        portal.register_irn(row["supplier_gstin"], "2025-26", "INV", row["doc_no"], row["doc_date"], None, 1, 1)
    at("2026-04-11T10:00:00+05:30")
    erp.file_gstr1(*ACC, period="202603", omit_doc_nos=[inv["invoice_no"]])     # filed differently from the books
    x = db.connect("ext", "audit_staff")
    assert x.execute("SELECT count(*) FROM gstr1_docs WHERE doc_no = ?", (inv["invoice_no"],)).fetchone()[0] == 0
    x.close()
    with pytest.raises(ValueError, match="already filed"):
        erp.file_gstr1(*ACC, period="202603", gstin=config.UNITS["G2"]["gstin"])
    e = erp.generate_eway_bill(*WHS, invoice_id=inv["id"], vehicle_no="X", distance_km=50)["result"]
    at("2026-04-13T10:00:00+05:30")
    with pytest.raises(portal.Refused, match="24 h"):
        portal.cancel_eway_bill(e["ewb_no"])


def test_credit_note_receipt_and_third_party_payer(co):
    inv = sale(qty=10)
    at("2026-04-10T10:00:00+05:30")
    cn = erp.issue_credit_note(*ACC, cn_date="2026-04-10", reason="RATE_DIFF",
                               lines=[{"invoice_no": inv["invoice_no"], "taxable_paise": 680000}])["result"]
    assert cn["cn_no"] == "CN/G2/0001/26" and cn["tax_paise"] == 122400 and cn["irn"]
    r = erp.record_receipt(*ACC, amount_paise=1000000, invoice_nos=[inv["id"]], settled_on="2026-04-20",
                           payer_name="Someone Else", payer_account="999988887777", payer_ifsc="SBIN0000001")["result"]
    x = db.connect("ext", "audit_staff")
    bt = x.execute("SELECT * FROM bank_txns WHERE id = ?", (r["bank_txn_id"],)).fetchone()
    assert bt["amount_paise"] == 1000000 and bt["cp_account"] == "999988887777" and bt["account_no"] == "50100012345678"
    x.close()
    c = db.connect("erp", "audit_staff")
    assert c.execute("SELECT account_code FROM journal_lines WHERE journal_no = ? AND dr_paise > 0 ORDER BY line_no",
                     (cn["journal_no"],)).fetchone()[0] == "DISCOUNTS_ALLOWED"
    c.close()


def test_auditors_cannot_run_the_business(co):
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        erp.create_party("aud.judge", "audit_staff", name="Ghost")
    with pytest.raises(PermissionError, match="customers only"):
        erp.create_party(*SAL, name="Vendor X", tags="VENDOR")


def test_register_export_round_trips_with_zero_d0_hits(co):
    a = sale(qty=3, inv_date="2026-03-20")
    sale(party="P-0002", qty=2, inv_date="2026-03-21")
    at("2026-03-25T10:00:00+05:30")
    erp.issue_credit_note(*ACC, cn_date="2026-03-25", reason="SALES_RETURN", lines=[{"invoice_no": a["id"], "taxable_paise": 680000}])
    exp = erp.export_sales_register(*ACC, fy_start="2025-04-01")["result"]
    p = db.connect("pbc", "audit_staff")
    path = p.execute("SELECT stored_path FROM exports WHERE id = ?", (exp["export_id"],)).fetchone()[0]
    p.close()
    headers, rows = register.parse_verbatim(open(path, "rb").read(), "register.xlsx")
    assert headers == erp.FIG1 and len(rows) == 3
    mapped = [register.map_row(headers, r) for r in rows]
    c = db.connect("erp", "audit_staff")
    docs = [{"id": r["id"], "doc_no": r["invoice_no"], "doc_type": "INVOICE", "doc_date": r["invoice_date"],
             "party_id": r["party_id"], "party_name": r["name"], "gstin": r["buyer_gstin"], "status": r["status"],
             "taxable_paise": r["t"], "tax_paise": r["x"], "total_paise": r["t"] + r["x"] + r["round_off_paise"]}
            for r in c.execute("SELECT i.*, p.name, SUM(l.taxable_paise) t, SUM(l.igst_paise+l.cgst_paise+l.sgst_paise) x"
                               " FROM invoices i JOIN parties p ON p.id = i.party_id JOIN invoice_lines l ON l.invoice_id ="
                               " i.id GROUP BY i.id")]
    docs += [{"id": r["id"], "doc_no": r["cn_no"], "doc_type": "CN", "doc_date": r["cn_date"], "party_id": r["party_id"],
              "party_name": r["name"], "gstin": r["gstin"], "status": r["status"], "taxable_paise": r["t"],
              "tax_paise": r["x"], "total_paise": r["t"] + r["x"]}
             for r in c.execute("SELECT n.*, p.name, p.gstin, SUM(l.taxable_paise) t, SUM(l.igst_paise+l.cgst_paise+"
                                "l.sgst_paise) x FROM credit_notes n JOIN parties p ON p.id = n.party_id JOIN cn_lines l"
                                " ON l.cn_id = n.id GROUP BY n.id")]
    c.close()
    hits, pairs = register.diff_register(mapped, docs, "2025-04-01", "2026-03-31")
    assert hits == [] and len(pairs) == 3


def test_render_document_and_events_after_commit(co, monkeypatch):
    seen = []
    monkeypatch.setattr("app.risk_graph.on_event", lambda t, i, s: seen.append((t, i, s)) or [])
    inv = sale()
    assert ("invoice", inv["id"]) in [(t, i) for t, i, _ in seen] and ("journal", str(inv["journal_no"])) in [
        (t, i) for t, i, _ in seen]
    txt = erp.render_document(*ACC, doc_type="INVOICE", id=inv["invoice_no"])["result"]["text"]
    assert f"Invoice No: {inv['invoice_no']}" in txt and "Total: 80240.00" in txt
    pdf = erp.render_document(*ACC, doc_type="INVOICE", id=inv["id"], format="pdf")["result"]
    assert base64.b64decode(pdf["pdf_base64"])[:4] == b"%PDF"

    def boom(*a):
        raise RuntimeError("graph down")
    monkeypatch.setattr("app.risk_graph.on_event", boom)
    assert sale(qty=1)["invoice_no"] == "G2/0002/25"                           # best-effort: the sale still lands


def test_import_records_keeps_numbers_and_reports_row_errors(co):
    rows = [{"series": "G2", "invoice_date": "2026-03-30", "party_id": "P-0001", "invoice_no": "G2/9001/25",
             "lines": [{"item_id": "IT-001", "qty": 1, "rate_paise": 4500000}]},
            {"series": "G2", "invoice_date": "2026-03-30", "party_id": "P-NOPE", "lines": [{"item_id": "IT-001", "qty": 1}]},
            {"bogus": 1}]
    r = erp.import_records(*ADM, entity="invoices", rows=rows)["result"]
    assert r["created"] == 1 and r["error_count"] == 2 and r["errors"][0]["error"].startswith("NOT_FOUND")
    c = db.connect("erp", "audit_staff")
    assert c.execute("SELECT 1 FROM invoices WHERE invoice_no = 'G2/9001/25'").fetchone()
    c.close()
