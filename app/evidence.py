"""Evidence: extract, test_sample (D8), bundle, check_for_changes (D11), verify_integrity (D12). STUB until IB-5."""
STUB = True


def extract(submission_id):
    """-> {submission_id, method: KEY_VALUE|PDF_TEXT|NEEDS_MANUAL_REVIEW, fields: {...}}."""
    return {"submission_id": submission_id, "method": "NEEDS_MANUAL_REVIEW", "fields": {}}


def test_sample(run_id, sample_no, actor, note=None):
    """-> {run_id, sample_no, attributes: {...}, exceptions: [...], conclusion_proposed, next_steps}."""
    return {"run_id": run_id, "sample_no": sample_no, "attributes": {}, "exceptions": [],
            "conclusion_proposed": None, "next_steps": []}


def bundle(invoice_id):
    """-> [(table, pk), ...]: every record a sample's conclusion depends on (05 D11)."""
    return []


def check_for_changes(engagement_id):
    """-> {changes: [{table, pk, fields, by, role, tool, at, seq, affected_samples}], stale_samples: [...]}."""
    return {"changes": [], "stale_samples": []}


def verify_integrity(engagement_id):
    """-> {ok, checks: {erp_chain, out_of_band, balanced, trail_chain, trail_anchors}, problems: [...]} (03 §6)."""
    return {"ok": True, "checks": {}, "problems": []}
