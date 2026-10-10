"""Mock government portals + bank (ext.db, role 'portal'; 03 §3).

The IRP, e-way bill system, GSTN and the bank statement are "independent" sources the auditor checks the books
against. They're simulated (05 §19.10 limitation 1): kept in a separate file the client can only read, with
server-clock timestamps (config.now()) and HMAC signatures standing in for the IRP's signed QR.
"""
import hashlib
import hmac
from datetime import datetime, timedelta

from app import chain, config, db


class Refused(ValueError):
    """The portal said no (24 h cancellation window, duplicate IRN, already filed): the caller decides."""


class _Conn:
    """db.borrow as a plain object, so the functions below keep their simple open / try / finally close shape."""
    def __init__(self, name, role):
        self._cm = db.borrow(name, role)
        self.c = self._cm.__enter__()

    def __getattr__(self, k):
        return getattr(self.c, k)

    def close(self):
        self._cm.__exit__(None, None, None)


def _conn():
    return _Conn("ext", "portal")


def fy_label(iso_date):
    y, m = int(iso_date[:4]), int(iso_date[5:7])
    start = y if m >= 4 else y - 1
    return f"{start}-{(start + 1) % 100:02d}"


def irn_of(supplier_gstin, fy, doc_type, doc_no):
    """IRN = sha256(supplier_gstin + fy + doc_type + doc_no), hex (03 #21)."""
    return hashlib.sha256(f"{supplier_gstin}{fy}{doc_type}{doc_no}".encode()).hexdigest()


_SIGNED = ("irn", "ack_no", "ack_at", "supplier_gstin", "buyer_gstin", "doc_type", "doc_no", "doc_date",
           "taxable_paise", "tax_paise", "total_paise")


def _sign(row):
    payload = chain.canon({k: row.get(k) for k in _SIGNED})
    return hmac.new(config.PORTAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(einvoice_row):
    """True when the stored signature matches the canonical payload (D6 IRN_SIGNATURE_BAD otherwise)."""
    row = dict(einvoice_row)
    return hmac.compare_digest(_sign(row), row.get("signature") or "")


def _hours_since(ts):
    return (datetime.fromisoformat(config.now()) - datetime.fromisoformat(ts)).total_seconds() / 3600


def register_irn(supplier_gstin, fy, doc_type, doc_no, doc_date, buyer_gstin, taxable_paise, tax_paise):
    """Register an e-invoice on the mock IRP. -> {irn, ack_no, ack_at, signature}. A duplicate is refused."""
    irn = irn_of(supplier_gstin, fy, doc_type, doc_no)
    c = _conn()
    try:
        with db.tx(c):
            if c.execute("SELECT 1 FROM einvoices WHERE irn = ?", (irn,)).fetchone():
                raise Refused(f"CONFLICT: the IRP already holds an IRN for {doc_type} {doc_no} (duplicate IRN)")
            n = c.execute("SELECT count(*) FROM einvoices").fetchone()[0] + 1
            row = {"irn": irn, "ack_no": f"1125{n:011d}", "ack_at": config.now(), "supplier_gstin": supplier_gstin,
                   "buyer_gstin": buyer_gstin, "doc_type": doc_type, "doc_no": doc_no, "doc_date": doc_date,
                   "taxable_paise": taxable_paise, "tax_paise": tax_paise, "total_paise": taxable_paise + tax_paise}
            row["signature"] = _sign(row)
            row["status"] = "ACT"
            c.execute(f"INSERT INTO einvoices ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    finally:
        c.close()
    return {"irn": irn, "ack_no": row["ack_no"], "ack_at": row["ack_at"], "signature": row["signature"]}


def cancel_irn(irn):
    """Cancel within 24 h of ack_at (CGST Rule 48 / IRP); afterwards the portal refuses."""
    c = _conn()
    try:
        with db.tx(c):
            r = c.execute("SELECT ack_at, status FROM einvoices WHERE irn = ?", (irn,)).fetchone()
            if r is None:
                raise Refused("NOT_FOUND: the IRP has no such IRN")
            if r["status"] == "CNL":
                raise Refused("CONFLICT: the IRN is already cancelled")
            if _hours_since(r["ack_at"]) > 24:
                raise Refused("PRECONDITION_FAILED: the IRP cancels an IRN only within 24 h of acknowledgement; "
                              "issue a credit note instead")
            at = config.now()
            c.execute("UPDATE einvoices SET status = 'CNL', cancelled_at = ? WHERE irn = ?", (at, irn))
    finally:
        c.close()
    return {"irn": irn, "status": "CNL", "cancelled_at": at}


def generate_eway_bill(**f):
    """Fields: supplier_gstin, doc_type, doc_no, doc_date, to_gstin, from_pincode, to_pincode, distance_km,
    value_paise (incl. tax), hsn, vehicle_no, transport_doc_no, reason. -> {ewb_no, generated_at, valid_upto}.
    Validity is 1 day per 200 km (normal cargo; Rule 138(10))."""
    need = ("supplier_gstin", "doc_no", "doc_date", "from_pincode", "to_pincode", "distance_km", "value_paise")
    missing = [k for k in need if f.get(k) in (None, "")]
    if missing:
        raise Refused(f"INVALID_ARGUMENT: e-way bill needs {', '.join(missing)}")
    km = int(f["distance_km"])
    c = _conn()
    try:
        with db.tx(c):
            n = c.execute("SELECT count(*) FROM ewaybills").fetchone()[0] + 1
            at = config.now()
            days = max(1, -(-km // 200))
            row = {"ewb_no": str(341000000000 + n), "generated_at": at,
                   "valid_upto": (datetime.fromisoformat(at) + timedelta(days=days)).isoformat(timespec="seconds"),
                   "supplier_gstin": f["supplier_gstin"], "doc_type": f.get("doc_type") or "INV", "doc_no": f["doc_no"],
                   "doc_date": f["doc_date"], "to_gstin": f.get("to_gstin"), "from_pincode": f["from_pincode"],
                   "to_pincode": f["to_pincode"], "distance_km": km, "value_paise": int(f["value_paise"]),
                   "hsn": f.get("hsn"), "vehicle_no": f.get("vehicle_no"), "transport_doc_no": f.get("transport_doc_no"),
                   "reason": f.get("reason") or "SUPPLY", "status": "ACT"}
            c.execute(f"INSERT INTO ewaybills ({','.join(row)}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    finally:
        c.close()
    return {"ewb_no": row["ewb_no"], "generated_at": row["generated_at"], "valid_upto": row["valid_upto"]}


def cancel_eway_bill(ewb_no):
    c = _conn()
    try:
        with db.tx(c):
            r = c.execute("SELECT generated_at, status FROM ewaybills WHERE ewb_no = ?", (str(ewb_no),)).fetchone()
            if r is None:
                raise Refused("NOT_FOUND: no such e-way bill on the portal")
            if r["status"] == "CNL":
                raise Refused("CONFLICT: the e-way bill is already cancelled")
            if _hours_since(r["generated_at"]) > 24:
                raise Refused("PRECONDITION_FAILED: an e-way bill can be cancelled only within 24 h of generation")
            at = config.now()
            c.execute("UPDATE ewaybills SET status = 'CNL', cancelled_at = ? WHERE ewb_no = ?", (at, str(ewb_no)))
    finally:
        c.close()
    return {"ewb_no": str(ewb_no), "status": "CNL", "cancelled_at": at}


def _books_for(gstin, period):
    """The supplier's outward documents for a month, read from the books (role portal: read-only erp handle)."""
    unit = next((u for u, v in config.UNITS.items() if v["gstin"] == gstin), None)
    if unit is None:
        raise Refused("INVALID_ARGUMENT: gstin is not one of the company's registrations "
                      f"({', '.join(v['gstin'] for v in config.UNITS.values())})")
    month = f"{period[:4]}-{period[4:6]}"
    e = _Conn("erp", "portal")
    try:
        docs = []
        for r in e.execute(
                "SELECT i.invoice_no AS doc_no, i.invoice_date AS doc_date, i.buyer_gstin, i.place_of_supply AS pos,"
                " SUM(l.taxable_paise) t, SUM(l.igst_paise) ig, SUM(l.cgst_paise) cg, SUM(l.sgst_paise) sg"
                " FROM invoices i JOIN invoice_lines l ON l.invoice_id = i.id"
                " WHERE i.supplier_gstin = ? AND substr(i.invoice_date, 1, 7) = ? AND i.status = 'ISSUED'"
                " GROUP BY i.id ORDER BY i.invoice_no", (gstin, month)):
            sec = "EXP" if r["pos"] == "96" else ("B2B" if r["buyer_gstin"] else
                                                   ("B2CL" if r["pos"] != config.UNITS[unit]["state_code"] else "B2CS"))
            docs.append({"section": sec, "doc_no": r["doc_no"], "doc_date": r["doc_date"], "buyer_gstin": r["buyer_gstin"],
                         "pos": r["pos"], "taxable_paise": r["t"], "igst_paise": r["ig"], "cgst_paise": r["cg"],
                         "sgst_paise": r["sg"]})
        for r in e.execute(
                "SELECT c.cn_no AS doc_no, c.cn_date AS doc_date, p.gstin AS buyer_gstin, p.state_code AS pos,"
                " SUM(l.taxable_paise) t, SUM(l.igst_paise) ig, SUM(l.cgst_paise) cg, SUM(l.sgst_paise) sg"
                " FROM credit_notes c JOIN cn_lines l ON l.cn_id = c.id JOIN parties p ON p.id = c.party_id"
                " WHERE c.cn_no LIKE ? AND substr(c.cn_date, 1, 7) = ? AND c.status = 'ISSUED'"
                " GROUP BY c.id ORDER BY c.cn_no", (f"CN/{unit}/%", month)):
            docs.append({"section": "CDNR" if r["buyer_gstin"] else "B2CS", "doc_no": r["doc_no"], "doc_date": r["doc_date"],
                         "buyer_gstin": r["buyer_gstin"], "pos": r["pos"], "taxable_paise": r["t"], "igst_paise": r["ig"],
                         "cgst_paise": r["cg"], "sgst_paise": r["sg"]})
        return docs
    finally:
        e.close()


_CHANGEABLE = ("doc_date", "buyer_gstin", "pos", "taxable_paise", "igst_paise", "cgst_paise", "sgst_paise")


def file_gstr1(gstin, period, omit=(), changes=()):
    """File GSTR-1 for one registration and month (period 'YYYYMM') from the books. `omit` doc numbers are left out
    and `changes` [{doc_no, field, value}] alter what is filed, so a filing can differ from the books (plantable)."""
    if not (isinstance(period, str) and len(period) == 6 and period.isdigit()):
        raise Refused("INVALID_ARGUMENT: period is 'YYYYMM'. Example: file_gstr1(period='202603')")
    docs = [d for d in _books_for(gstin, period) if d["doc_no"] not in set(omit or ())]
    by_no = {d["doc_no"]: d for d in docs}
    for ch in changes or ():
        d = by_no.get(ch.get("doc_no"))
        if d is None or ch.get("field") not in _CHANGEABLE:
            raise Refused(f"INVALID_ARGUMENT: a change needs a filed doc_no and a field in {', '.join(_CHANGEABLE)}")
        d[ch["field"]] = ch["value"]
    c = _conn()
    try:
        with db.tx(c):
            if c.execute("SELECT 1 FROM gstr1_docs WHERE gstin = ? AND period = ?", (gstin, period)).fetchone():
                raise Refused(f"CONFLICT: GSTR-1 for {period} is already filed for this GSTIN")
            at = config.now()
            # the filing itself: a B2CS summary row with no doc_no (nil if nothing else is filed), so a month can't be
            # filed twice even when every document was omitted. Detectors match by doc_no and skip it.
            c.execute("INSERT INTO gstr1_docs(gstin, period, section, taxable_paise, filed_at) VALUES (?,?,'B2CS',0,?)",
                      (gstin, period, at))
            for d in docs:
                c.execute("INSERT INTO gstr1_docs(gstin, period, section, doc_no, doc_date, buyer_gstin, pos, taxable_paise,"
                          " igst_paise, cgst_paise, sgst_paise, filed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (gstin, period, d["section"], d["doc_no"], d["doc_date"], d["buyer_gstin"], d["pos"],
                           d["taxable_paise"], d["igst_paise"], d["cgst_paise"], d["sgst_paise"], at))
    finally:
        c.close()
    return {"gstin": gstin, "period": period, "docs": len(docs), "omitted": len(set(omit or ())),
            "changed": len(changes or ()), "filed_at": at}


def file_gstr3b(gstin, period, figures=None):
    """GSTR-3B 3.1(a) for a month: defaults to the books (invoices - CNs); `figures` overrides (T2)."""
    docs = _books_for(gstin, period)
    sign = lambda d: -1 if d["section"] == "CDNR" or d["doc_no"].startswith("CN/") else 1
    f = {"outward_taxable_paise": sum(sign(d) * d["taxable_paise"] for d in docs),
         "igst_paise": sum(sign(d) * d["igst_paise"] for d in docs),
         "cgst_paise": sum(sign(d) * d["cgst_paise"] for d in docs),
         "sgst_paise": sum(sign(d) * d["sgst_paise"] for d in docs)}
    f.update({k: v for k, v in (figures or {}).items() if k in f})
    f = {k: max(0, int(v)) for k, v in f.items()}
    c = _conn()
    try:
        with db.tx(c):
            if c.execute("SELECT 1 FROM gstr3b WHERE gstin = ? AND period = ?", (gstin, period)).fetchone():
                raise Refused(f"CONFLICT: GSTR-3B for {period} is already filed for this GSTIN")
            at = config.now()
            c.execute("INSERT INTO gstr3b(gstin, period, outward_taxable_paise, igst_paise, cgst_paise, sgst_paise, filed_at)"
                      " VALUES (?,?,?,?,?,?,?)", (gstin, period, f["outward_taxable_paise"], f["igst_paise"],
                                                  f["cgst_paise"], f["sgst_paise"], at))
    finally:
        c.close()
    return {"gstin": gstin, "period": period, **f, "filed_at": at}


def bank_txn(account_no, value_date, amount_paise, cp_name, cp_account, cp_ifsc, utr, narration):
    """One bank statement line (+ in, - out). -> ext.bank_txns id."""
    if not isinstance(amount_paise, int) or amount_paise == 0:
        raise Refused("INVALID_ARGUMENT: amount_paise must be a non-zero integer")
    c = _conn()
    try:
        with db.tx(c):
            n = c.execute("SELECT count(*) FROM bank_txns").fetchone()[0] + 1
            tid = f"BT-{n:06d}"
            c.execute("INSERT INTO bank_txns(id, account_no, value_date, amount_paise, cp_name, cp_account, cp_ifsc, utr,"
                      " narration) VALUES (?,?,?,?,?,?,?,?,?)",
                      (tid, account_no, value_date, amount_paise, cp_name, cp_account, cp_ifsc,
                       utr or f"UTR{value_date.replace('-', '')}{n:06d}", narration))
    finally:
        c.close()
    return tid
