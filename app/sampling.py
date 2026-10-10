"""Sample selection: strata, PPS, cut-off / CN selection, reproduce (05 §15). STUB until AA-1."""
STUB = True


def select(engagement_id, kind, size=30, seed=None, actor=""):
    """kind in sales_tod | cutoff | credit_note. First call = testing start (anchor + snapshots + requests).
    -> {run_id, seed, size, items: [{sample_no, doc_type, doc_id, stratum, reason}], next_steps}."""
    return {"run_id": "", "seed": "", "size": 0, "items": [], "next_steps": []}


def reproduce(run_id):
    """-> {run_id, identical, diff}."""
    return {"run_id": run_id, "identical": True, "diff": []}


def pps(items, k, rng):
    """Systematic PPS over [(invoice_id, weight)] using only rng.random() (05 §15)."""
    return []
