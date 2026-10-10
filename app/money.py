"""Money boundary (03 §6): tools take rupees as strings, everything inside is integer paise. No floats, ever."""
from decimal import Decimal, ROUND_HALF_UP


def to_paise(s):  # '118000.50' -> 11800050. Rejects floats, negatives, >2 decimals. Never rounds client money.
    if not isinstance(s, str): raise ValueError('amount must be a string like "118000.50"')
    d = Decimal(s.replace(',', ''))
    if d < 0 or d != d.quantize(Decimal('0.01')): raise ValueError(f'bad amount {s!r}')
    return int(d * 100)


def tax_paise(taxable_paise, rate_bp):  # per line, half-up
    return int((Decimal(taxable_paise) * Decimal(rate_bp) / 10000).quantize(Decimal('1'), ROUND_HALF_UP))


def tax_split(taxable_paise, rate_bp, inter_state):
    """IGST for an inter-state supply; otherwise CGST = SGST at half the rate each (IGST Act s.10)."""
    if inter_state:
        return {"igst_paise": tax_paise(taxable_paise, rate_bp), "cgst_paise": 0, "sgst_paise": 0}
    half = tax_paise(taxable_paise, Decimal(rate_bp) / 2)
    return {"igst_paise": 0, "cgst_paise": half, "sgst_paise": half}


def to_rupees(paise):
    """11800050 -> '118000.50' (the string form tools return; the inverse of to_paise)."""
    sign, p = ("-" if paise < 0 else ""), abs(int(paise))
    return f"{sign}{p // 100}.{p % 100:02d}"


def fmt_inr(paise):
    """11800050 -> '₹1,18,000.50' (Indian lakh/crore grouping) for server-written prose."""
    sign, p = ("-" if paise < 0 else ""), abs(int(paise))
    r, ps = divmod(p, 100)
    s = str(r)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + groups) + "," + tail
    return f"{sign}₹{s}.{ps:02d}"


def round_off(total_paise):
    """Signed paise that rounds an invoice total to the nearest rupee (Fig. 1 'Round' column)."""
    r = total_paise % 100
    return 100 - r if r >= 50 else -r
