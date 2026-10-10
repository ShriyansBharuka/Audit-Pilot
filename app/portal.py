"""Mock government portals + bank in ext.db (role 'portal'; server clock = config.now()). STUB until IB-3."""
STUB = True


def register_irn(supplier_gstin, fy, doc_type, doc_no, doc_date, buyer_gstin, taxable_paise, tax_paise):
    """-> {irn, ack_no, ack_at, signature}. irn = sha256(supplier_gstin + fy + doc_type + doc_no)."""
    return {"irn": "", "ack_no": "", "ack_at": "", "signature": ""}


def cancel_irn(irn):
    """-> {irn, status, cancelled_at}; refuses after 24 h of ack_at."""
    return {"irn": irn, "status": "ACT", "cancelled_at": None}


def generate_eway_bill(**f):
    """-> {ewb_no (12 digits), generated_at, valid_upto}; valid 1 day per 200 km."""
    return {"ewb_no": "", "generated_at": "", "valid_upto": ""}


def cancel_eway_bill(ewb_no):
    """-> {ewb_no, status, cancelled_at}; refuses after 24 h of generated_at."""
    return {"ewb_no": ewb_no, "status": "ACT", "cancelled_at": None}


def file_gstr1(gstin, period, omit=(), changes=()):
    """-> {gstin, period, docs, filed_at}; omit/changes let the filing differ from the books."""
    return {"gstin": gstin, "period": period, "docs": 0, "filed_at": ""}


def file_gstr3b(gstin, period, figures=None):
    """-> {gstin, period, outward_taxable_paise, filed_at} (T2)."""
    return {"gstin": gstin, "period": period, "outward_taxable_paise": 0, "filed_at": ""}


def bank_txn(account_no, value_date, amount_paise, cp_name, cp_account, cp_ifsc, utr, narration):
    """-> ext.bank_txns id."""
    return ""


def verify_signature(einvoice_row):
    """HMAC check of an einvoices row with PORTAL_SECRET."""
    return True
