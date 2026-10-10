"""Hits -> PROPOSED findings, AJE templates (06 §6), materiality, SA 450 summary. STUB until AA-3."""
STUB = True


def from_hits(engagement_id):
    """-> ids of the findings written (F-001 ...)."""
    return []


def aje(finding):
    """-> balanced COA lines [{account_code, party_id?, dr_paise, cr_paise}] or None (disclosure only)."""
    return None


def sa450_summary(engagement_id):
    """-> {factual_paise, judgemental_paise, projected_paise, materiality_paise, exceeds: bool}."""
    return {"factual_paise": 0, "judgemental_paise": 0, "projected_paise": 0, "materiality_paise": 0, "exceeds": False}
