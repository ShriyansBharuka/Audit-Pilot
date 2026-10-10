"""Double-entry ledger (03 §2): chart of accounts, post_journal, reverse_journal, trial_balance.

Journals are append-only; a correction is a REVERSAL voucher (reverses_no) or a new JV, never an UPDATE. Every
voucher and every account is logged through erp.write_doc, so it is in the hash-chained erp_log.
"""
from app import db

# 03 §2 seed COA; is_revenue marks the accounts D7 tests over 100% of lines
COA = [
    ("BANK", "Bank", "ASSET", 0), ("DEBTORS", "Trade receivables", "ASSET", 0),
    ("CREDITORS", "Trade payables", "LIABILITY", 0), ("INVENTORY", "Inventory", "ASSET", 0),
    ("CONTRACT_LIABILITY", "Contract liabilities (Ind AS 115)", "LIABILITY", 0),
    ("REFUND_LIABILITY", "Refund liabilities", "LIABILITY", 0),
    ("SALES", "Sales - goods (domestic)", "INCOME", 1), ("SALES_EXPORT", "Sales - exports", "INCOME", 1),
    ("SALES_SERVICE", "Sales - services", "INCOME", 1),
    ("OTHER_OPERATING_REVENUE", "Other operating revenue", "INCOME", 1),
    ("SALES_RETURNS", "Sales returns", "INCOME", 1), ("DISCOUNTS_ALLOWED", "Discounts and rebates allowed", "INCOME", 1),
    ("OUTPUT_IGST", "Output IGST", "LIABILITY", 0), ("OUTPUT_CGST", "Output CGST", "LIABILITY", 0),
    ("OUTPUT_SGST", "Output SGST", "LIABILITY", 0),
    ("PURCHASES", "Purchases", "EXPENSE", 0), ("COGS", "Cost of goods sold", "EXPENSE", 0),
    ("INPUT_IGST", "Input IGST", "ASSET", 0), ("INPUT_CGST", "Input CGST", "ASSET", 0),
    ("INPUT_SGST", "Input SGST", "ASSET", 0),
    ("ROUND_OFF", "Round off", "EXPENSE", 0), ("SUSPENSE", "Suspense", "ASSET", 0),
    ("DIRECTOR_LOAN", "Loan from directors", "LIABILITY", 0), ("OTHER_INCOME", "Other income", "INCOME", 0),
]
PARTY_ACCOUNTS = {"DEBTORS", "CREDITORS"}
VOUCHER_TYPES = ("OPENING", "SALES", "CREDIT_NOTE", "RECEIPT", "PURCHASE", "PAYMENT", "JOURNAL", "REVERSAL")


def seed_coa(conn, actor="system", role="client_admin"):
    """Create the 03 §2 chart of accounts through erp.write_doc (called by db.init_all). Idempotent."""
    from app import erp
    n = 0
    with db.tx(conn):
        for code, name, typ, rev in COA:
            if conn.execute("SELECT 1 FROM accounts WHERE code = ?", (code,)).fetchone():
                continue
            conn.execute("INSERT INTO accounts(code, name, type, is_revenue) VALUES (?,?,?,?)", (code, name, typ, rev))
            erp.write_doc(conn, actor, role, "init_all", "CREATE", "account", code)
            n += 1
    erp.discard_events(conn)            # the COA is bootstrap, not a business event
    return n


def check_lines(conn, lines):
    """ValueError with an actionable message unless the voucher is balanced, positive and well-formed."""
    if not lines:
        raise ValueError("INVALID_ARGUMENT: a voucher needs at least two lines. "
                         "Example: [{account_code:'SUSPENSE', dr_paise:100}, {account_code:'SALES', cr_paise:100}]")
    dr = cr = 0
    for i, ln in enumerate(lines, 1):
        d, c = ln.get("dr_paise", 0) or 0, ln.get("cr_paise", 0) or 0
        if not (isinstance(d, int) and isinstance(c, int)) or isinstance(d, bool) or isinstance(c, bool):
            raise ValueError(f"INVALID_ARGUMENT: line {i}: amounts must be integer paise")
        if d < 0 or c < 0 or (d == 0) == (c == 0):
            raise ValueError(f"INVALID_ARGUMENT: line {i} must be either a debit or a credit, > 0")
        code = ln.get("account_code")
        if not conn.execute("SELECT 1 FROM accounts WHERE code = ?", (code,)).fetchone():
            raise ValueError(f"INVALID_ARGUMENT: line {i}: unknown account. Valid codes: "
                             + ", ".join(c for c, *_ in COA))
        if code in PARTY_ACCOUNTS and not ln.get("party_id"):
            raise ValueError(f"INVALID_ARGUMENT: line {i}: {code} lines need party_id")
        dr, cr = dr + d, cr + c
    if dr != cr or dr <= 0:
        raise ValueError(f"INVALID_ARGUMENT: voucher does not balance (Dr {dr} paise vs Cr {cr} paise); "
                         "total debits must equal total credits and be > 0")


def post_journal(conn, voucher_date, voucher_type, lines, narration, actor, role, tool,
                 source_type=None, source_id=None, reverses_no=None, aje_ref=None):
    """Post one voucher (raises ValueError unless Dr == Cr > 0, accounts exist, party on DEBTORS/CREDITORS).
    Joins the caller's transaction if one is open. Returns the journal no."""
    from app import config, erp
    if voucher_type not in VOUCHER_TYPES:
        raise ValueError(f"INVALID_ARGUMENT: voucher_type must be one of {', '.join(VOUCHER_TYPES)}")
    if not (narration or "").strip():
        raise ValueError("INVALID_ARGUMENT: narration is mandatory (SA 240 journal-entry testing reads it)")
    with db.tx(conn):
        check_lines(conn, lines)
        cur = conn.execute(
            "INSERT INTO journals(voucher_date, voucher_type, source_type, source_id, reverses_no, aje_ref, narration,"
            " posted_by, recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (voucher_date, voucher_type, source_type, source_id, reverses_no, aje_ref, narration, actor, config.now()))
        no = cur.lastrowid
        for i, ln in enumerate(lines, 1):
            conn.execute("INSERT INTO journal_lines(journal_no, line_no, account_code, party_id, dr_paise, cr_paise)"
                         " VALUES (?,?,?,?,?,?)", (no, i, ln["account_code"], ln.get("party_id"),
                                                   ln.get("dr_paise", 0) or 0, ln.get("cr_paise", 0) or 0))
        erp.write_doc(conn, actor, role, tool, "POST", "journal", no)
    return no


def reverse_journal(conn, journal_no, date, actor, role, tool, reason):
    """A REVERSAL voucher that mirrors `journal_no` line by line. Returns the new journal no."""
    j = conn.execute("SELECT * FROM journals WHERE no = ?", (journal_no,)).fetchone()
    if j is None:
        raise ValueError(f"NOT_FOUND: journal {journal_no}")
    if conn.execute("SELECT 1 FROM journals WHERE reverses_no = ?", (journal_no,)).fetchone():
        raise ValueError(f"CONFLICT: journal {journal_no} is already reversed")
    lines = [{"account_code": r["account_code"], "party_id": r["party_id"],
              "dr_paise": r["cr_paise"], "cr_paise": r["dr_paise"]}
             for r in conn.execute("SELECT * FROM journal_lines WHERE journal_no = ? ORDER BY line_no", (journal_no,))]
    return post_journal(conn, date, "REVERSAL", lines, f"Reversal of journal {journal_no}: {reason}", actor, role, tool,
                        source_type=j["source_type"], source_id=j["source_id"], reverses_no=journal_no)


def trial_balance(conn, upto):
    """{account_code: net paise, Dr positive} over vouchers dated on or before `upto`."""
    return {r[0]: r[1] for r in conn.execute(
        "SELECT l.account_code, SUM(l.dr_paise) - SUM(l.cr_paise) FROM journal_lines l JOIN journals j ON j.no = l.journal_no"
        " WHERE j.voucher_date <= ? GROUP BY l.account_code ORDER BY l.account_code", (upto,))}
