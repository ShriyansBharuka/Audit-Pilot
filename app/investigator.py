"""GPT investigator: an MCP client with an audit_staff token + CostMeter (10 §4). STUB until AA-5 (P1)."""
STUB = True


async def investigate(task_text, model, aud_token, meter):
    """-> Investigation {facts, discrepancies, missing_evidence, open_questions, recommended_next_step, record_ids_cited}."""
    return {"facts": [], "discrepancies": [], "missing_evidence": [], "open_questions": [],
            "recommended_next_step": "", "record_ids_cited": []}
