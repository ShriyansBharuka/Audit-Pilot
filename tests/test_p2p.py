"""MT-1: purchase-to-pay records (PO -> GRN -> bill -> payment), append-only, logged, and in the clean seed year."""
import asyncio
import json

import pytest

from app import config, db, erp, seed

ACC, WHS, ADM = ("acc.neha", "accounts"), ("whs.ganesh", "warehouse"), ("adm.kiran", "client_admin")


@pytest.fixture()
def p2p(world):
    config.set_clock("2026-03-01T10:00:00+05:30")
    erp.create_party(*ADM, id="SELF", tags="SELF", name=config.ENTITY_NAME, gstin=config.UNITS["G2"]["gstin"],
                     bank_account="50100012345678", ifsc="HDFC0001234")
    erp.create_party(*ADM, id="P-VEN9", tags="VENDOR", name="ABC Industrial Supplies", gstin="27AAPFU0939F1ZV",
                     bank_account="660011112222", ifsc="ICIC0000066")
    erp.create_item(*ADM, id="IT-001", name="Valve body casting", hsn="8481", list_rate_paise=800000, cost_paise=500000)
    return world


def test_po_grn_bill_payment_through_the_edit_log(p2p):
    po = erp.create_purchase_order(*ACC, vendor_id="P-VEN9", item_id="IT-001", qty=100, rate_paise=500000,
                                   po_date="2026-03-01", payment_terms="ADVANCE")["result"]
    assert po["value_paise"] == 5_00_000_00 and po["id"] == "PO-000001"
    g = erp.record_goods_receipt(*WHS, po_id=po["id"], qty=60, received_on="2026-03-10", received_by="Stores")["result"]
    assert g["kind"] == "RECEIPT" and g["grn_no"] == "GRN-000001"
    b = erp.record_purchase(*ACC, po_id=po["id"], bill_no="ABC/101", bill_date="2026-03-11", qty=100,
                            taxable_paise=5_00_000_00, tax_paise=90_000_00)["result"]
    pay = erp.record_payment(*ACC, vendor_id="P-VEN9", amount_paise=5_90_000_00, settled_on="2026-03-12",
                             purchase_ids=[b["id"]])["result"]
    ret = erp.record_goods_receipt(*WHS, po_id=po["id"], qty=5, kind="RETURN", received_on="2026-03-15")["result"]
    with db.borrow("erp", "audit_staff") as e:
        bill = e.execute("SELECT * FROM purchase_bills WHERE id = ?", (b["id"],)).fetchone()
        assert bill["po_id"] == po["id"] and bill["vendor_id"] == "P-VEN9" and bill["item_id"] == "IT-001"
        logged = {(r[0], r[1]) for r in e.execute("SELECT doc_type, doc_id FROM erp_log")}
        assert {("purchase_order", po["id"]), ("goods_receipt", g["id"]), ("goods_receipt", ret["id"]),
                ("purchase_bill", b["id"])} <= logged
        assert erp.out_of_band(e) == []
        assert e.execute("SELECT direction, doc_type, doc_id FROM settlements WHERE id = ?",
                         (pay["settlement_id"],)).fetchone()[2] == b["id"]
    with db.borrow("ext", "audit_staff") as x:
        bt = x.execute("SELECT * FROM bank_txns WHERE id = ?", (pay["bank_txn_id"],)).fetchone()
        assert bt["amount_paise"] == -5_90_000_00 and bt["cp_account"] == "660011112222"


def test_p2p_records_are_append_only(p2p):
    po = erp.create_purchase_order(*ACC, vendor_id="P-VEN9", item_id="IT-001", qty=10)["result"]
    erp.record_goods_receipt(*WHS, po_id=po["id"], qty=10)
    with pytest.raises(ValueError, match="record_goods_receipt\\(kind='RETURN'"):
        erp.amend_record(*ADM, entity="goods_receipts", id="GRN-000001", changes={"qty": 5}, reason="x")
    with db.borrow("erp", "client_admin") as c:
        for sql in ("UPDATE purchase_orders SET qty = 1", "DELETE FROM goods_receipts"):
            with pytest.raises(Exception, match="append-only"):
                c.execute(sql)
    with pytest.raises(ValueError, match="payment_terms"):
        erp.create_purchase_order(*ACC, vendor_id="P-VEN9", item_id="IT-001", qty=1, payment_terms="LATER")
    with pytest.raises(LookupError, match="purchase order"):
        erp.record_goods_receipt(*WHS, po_id="PO-999999", qty=1)


def test_mcp_roles_for_p2p_tools(p2p):
    from app import gateway, mcp_server  # noqa: F401
    assert gateway.TOOL_ROLES["create_purchase_order"] == {"accounts", "client_admin"}
    assert gateway.TOOL_ROLES["record_goods_receipt"] == {"warehouse", "client_admin"}
    gateway.STDIO_ID = ("whs.ganesh", "warehouse")
    try:
        po = erp.create_purchase_order(*ACC, vendor_id="P-VEN9", item_id="IT-001", qty=10)["result"]["id"]
        out = asyncio.run(gateway.mcp.call_tool("record_goods_receipt", {"po_id": po, "qty": 10}))
        assert json.loads(out.content[0].text)["summary"]["po_id"] == po
        gateway.STDIO_ID = ("aud.judge", "audit_staff")
        with pytest.raises(Exception, match="PERMISSION_DENIED"):
            asyncio.run(gateway.mcp.call_tool("create_purchase_order", {"vendor_id": "P-VEN9", "item_id": "IT-001",
                                                                        "qty": 1}))
    finally:
        gateway.STDIO_ID = None


def test_clean_seed_year_has_po_and_grn_behind_every_bill(world):
    plan = seed.build_plan(120, 7)
    seed.load(plan, reset=True)
    with db.borrow("erp", "audit_staff") as e:
        bills = [dict(r) for r in e.execute("SELECT * FROM purchase_bills")]
        assert bills and all(b["po_id"] for b in bills)
        for b in bills:
            po = e.execute("SELECT * FROM purchase_orders WHERE id = ?", (b["po_id"],)).fetchone()
            grn = e.execute("SELECT SUM(qty), MAX(received_on) FROM goods_receipts WHERE po_id = ? AND kind = 'RECEIPT'",
                            (po["id"],)).fetchone()
            assert po["vendor_id"] == b["vendor_id"] and po["qty"] == b["qty"] == grn[0]
            assert po["po_date"] <= grn[1] <= b["bill_date"]
            assert b["taxable_paise"] == po["qty"] * po["rate_paise"]
            assert e.execute("SELECT count(*) FROM settlements WHERE doc_type = 'PURCHASE' AND doc_id = ?",
                             (b["id"],)).fetchone()[0] == 1
