"""The client's system of record: write_doc + every business service (07 §4). STUB until SH-4.

Each service is (actor, role, **args) -> {"result": {...}, "next_steps": [...]}; it opens erp.db read-write,
writes typed rows, posts via ledger, calls portal.* when needed, and ends with write_doc in the same transaction.
The kwargs the seed already calls are listed in vault/PROGRESS.md (DA-1a request).
"""
STUB = True

SERVICES = ("create_party", "link_parties", "create_item", "create_lead", "create_scheme", "create_sales_order",
            "issue_invoice", "generate_eway_bill", "record_dispatch", "record_delivery", "issue_credit_note",
            "record_receipt", "record_payment", "record_purchase", "post_journal_entry", "file_gstr1", "file_gstr3b",
            "amend_record", "cancel_document", "import_records", "export_sales_register", "render_document")


def write_doc(conn, actor, role, tool, action, doc_type, doc_id, reason=None):
    """Append the doc's after-image to erp_log (03 §6). Returns the erp_log seq."""
    return 0


def _stub(name):
    def service(actor, role, **args):
        return {"result": {}, "next_steps": []}
    service.__name__ = service.__qualname__ = name
    service.__doc__ = f"erp.{name}: STUB until SH-4."
    return service


for _name in SERVICES:
    globals()[_name] = _stub(_name)
