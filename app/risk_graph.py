"""AuditGraph: the risk engine over the detectors (05 §19). STUB until DA-6."""
STUB = True


def build(engagement_id, as_of_run=None):
    """-> {nodes: [{id, type, label, E|R, C, band}], edges: [{a, b, kind, amount_paise, ts}],
    cycles: [{members, circular_paise, span_days, residuals}], company: {band, exposure_paise, families, circular_paise}}."""
    return {"nodes": [], "edges": [], "cycles": [],
            "company": {"band": "LOW", "exposure_paise": 0, "families": [], "circular_paise": 0}}


def on_event(doc_type, doc_id, erp_seq):
    """Called by erp.write_doc after commit (05 §19.6): update the graph for one document. -> changed snapshots."""
    return []
