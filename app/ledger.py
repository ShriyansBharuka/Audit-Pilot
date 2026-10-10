"""Double-entry ledger: COA, post_journal, reverse_journal, trial_balance (03 §2). STUB until IB-2."""
STUB = True


def seed_coa(conn):
    """Bootstrap the 03 §2 chart of accounts through erp.write_doc (so each account has an erp_log row).
    Called by db.init_all. Returns the number of accounts created. No-op until IB-2."""
    return 0


def post_journal(conn, voucher_date, voucher_type, lines, narration, actor, role, tool,
                 source_type=None, source_id=None, reverses_no=None, aje_ref=None):
    """-> journal no. Raises ValueError unless Dr == Cr > 0, every account exists, DEBTORS/CREDITORS lines have a party."""
    return 0


def reverse_journal(conn, journal_no, date, actor, role, tool, reason):
    """-> the REVERSAL journal's no."""
    return 0


def trial_balance(conn, upto):
    """-> {account_code: net paise (Dr positive)}."""
    return {}
