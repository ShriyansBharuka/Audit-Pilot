"""IB-1 money boundary + IB-2 ledger: balanced vouchers only, every posting in erp_log, reversals, TB."""
import pytest

from app import chain, db, erp, ledger, money


def test_money_boundary():
    assert money.to_paise("118000.50") == 11800050 and money.to_paise("1,18,000.50") == 11800050
    for bad in (1.5, 118000, None):
        with pytest.raises(ValueError):
            money.to_paise(bad)
    for bad in ("-1", "1.005", "abc"):
        with pytest.raises(Exception):
            money.to_paise(bad)
    assert money.tax_paise(1559322, 1800) == 280678                 # 06 §6 worked example
    assert money.tax_split(1559322, 1800, True) == {"igst_paise": 280678, "cgst_paise": 0, "sgst_paise": 0}
    assert money.tax_split(1001, 1800, False) == {"igst_paise": 0, "cgst_paise": 90, "sgst_paise": 90}
    assert money.fmt_inr(184000000) == "₹18,40,000.00" and money.fmt_inr(5) == "₹0.05"
    assert money.fmt_inr(1234567890) == "₹1,23,45,678.90" and money.fmt_inr(-100) == "-₹1.00"
    assert money.to_rupees(11800050) == "118000.50" and money.to_rupees(-5) == "-0.05"
    assert money.round_off(1840049) == -49 and money.round_off(1840050) == 50


def test_coa_is_seeded_through_the_edit_log(world):
    c = db.connect("erp", "audit_staff")
    codes = {r[0] for r in c.execute("SELECT code FROM accounts")}
    assert codes == {code for code, *_ in ledger.COA}
    assert c.execute("SELECT count(*) FROM erp_log WHERE doc_type='account'").fetchone()[0] == len(ledger.COA)
    assert {r[0] for r in c.execute("SELECT code FROM accounts WHERE is_revenue=1")} == {
        "SALES", "SALES_EXPORT", "SALES_SERVICE", "OTHER_OPERATING_REVENUE", "SALES_RETURNS", "DISCOUNTS_ALLOWED"}
    assert erp.out_of_band(c) == [] and chain.verify(c, "erp_log")["valid"]
    c.close()


def _party(c):
    with db.tx(c):
        c.execute("INSERT INTO parties(id,kind,name,recorded_by,recorded_at) VALUES ('P-1','ENTITY','x','a','t')")
        erp.write_doc(c, "a", "client_admin", "create_party", "CREATE", "party", "P-1")


def test_post_reverse_and_trial_balance(world):
    c = db.connect("erp", "accounts")
    _party(c)
    lines = [{"account_code": "DEBTORS", "party_id": "P-1", "dr_paise": 118000},
             {"account_code": "SALES", "cr_paise": 100000}, {"account_code": "OUTPUT_IGST", "cr_paise": 18000}]
    no = ledger.post_journal(c, "2026-03-30", "SALES", lines, "Invoice INV-1", "acc.neha", "accounts", "issue_invoice",
                             source_type="invoice", source_id="INV-1")
    log = c.execute("SELECT action, doc_type, doc_id, actor FROM erp_log ORDER BY seq DESC LIMIT 1").fetchone()
    assert tuple(log) == ("POST", "journal", str(no), "acc.neha")      # every posting appears in erp_log
    tb = ledger.trial_balance(c, "2026-03-31")
    assert tb == {"DEBTORS": 118000, "OUTPUT_IGST": -18000, "SALES": -100000}
    rev = ledger.reverse_journal(c, no, "2026-04-02", "acc.neha", "accounts", "cancel_document", "cancelled")
    assert ledger.trial_balance(c, "2026-04-30") == {"DEBTORS": 0, "OUTPUT_IGST": 0, "SALES": 0}
    assert ledger.trial_balance(c, "2026-03-31")["SALES"] == -100000     # the reversal is dated in April
    j = c.execute("SELECT voucher_type, reverses_no FROM journals WHERE no = ?", (rev,)).fetchone()
    assert tuple(j) == ("REVERSAL", no)
    with pytest.raises(ValueError, match="CONFLICT"):
        ledger.reverse_journal(c, no, "2026-04-03", "acc.neha", "accounts", "cancel_document", "again")
    erp.discard_events(c)
    c.close()


@pytest.mark.parametrize("lines, msg", [
    ([{"account_code": "SUSPENSE", "dr_paise": 100}, {"account_code": "SALES", "cr_paise": 90}], "does not balance"),
    ([{"account_code": "SUSPENSE", "dr_paise": 0}, {"account_code": "SALES", "cr_paise": 0}], "either a debit"),
    ([{"account_code": "NOPE", "dr_paise": 100}, {"account_code": "SALES", "cr_paise": 100}], "unknown account"),
    ([{"account_code": "DEBTORS", "dr_paise": 100}, {"account_code": "SALES", "cr_paise": 100}], "need party_id"),
    ([{"account_code": "SUSPENSE", "dr_paise": 1.5}, {"account_code": "SALES", "cr_paise": 1.5}], "integer paise"),
    ([], "at least two"),
])
def test_bad_vouchers_are_rejected_and_nothing_is_written(world, lines, msg):
    c = db.connect("erp", "accounts")
    before = c.execute("SELECT count(*) FROM erp_log").fetchone()[0]
    with pytest.raises(ValueError, match=msg):
        ledger.post_journal(c, "2026-03-31", "JOURNAL", lines, "manual JV", "acc.neha", "accounts", "post_journal_entry")
    assert c.execute("SELECT count(*) FROM journals").fetchone()[0] == 0
    assert c.execute("SELECT count(*) FROM erp_log").fetchone()[0] == before
    c.close()


def test_narration_is_mandatory(world):
    c = db.connect("erp", "accounts")
    with pytest.raises(ValueError, match="narration"):
        ledger.post_journal(c, "2026-03-31", "JOURNAL", [{"account_code": "SUSPENSE", "dr_paise": 1},
                                                         {"account_code": "SALES", "cr_paise": 1}], " ", "a", "accounts", "t")
    c.close()
