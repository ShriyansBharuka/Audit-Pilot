"""Events -> audit.events + optional n8n webhook (X-AuditPilot-Signature: HMAC) (10 §1). STUB until IB-4."""
STUB = True


def emit(kind, payload, engagement_id=None):
    """Write an events row; POST {kind, engagement_id, payload, at} to N8N_WEBHOOK_URL when set."""
    return None
