"""Money boundary: rupee strings <-> integer paise (03 §6). STUB until IB-1: copy the 03 §6 code exactly."""
STUB = True


def to_paise(s):
    """'118000.50' -> 11800050. Must reject floats, negatives and >2 decimals (IB-1)."""
    if not isinstance(s, str):
        raise ValueError('amount must be a string like "118000.50"')
    return 0


def fmt_inr(paise):
    """11800050 -> 'Rs 1,18,000.50' (Indian grouping)."""
    return "Rs 0.00"


def tax_paise(taxable_paise, rate_bp):
    """Per-line tax, half-up."""
    return 0


def tax_split(taxable_paise, rate_bp, inter_state):
    """-> {igst_paise, cgst_paise, sgst_paise}."""
    return {"igst_paise": 0, "cgst_paise": 0, "sgst_paise": 0}
