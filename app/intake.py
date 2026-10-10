"""Client submissions (register, RP list, evidence) and the upload notification (02 §3.1-2). STUB until DA-2."""
STUB = True


def submit(kind, content, filename, submitted_by, request_id=None, declared=None):
    """Store bytes content-addressed with a server-computed sha256 -> pbc.submissions id."""
    return ""


def on_client_upload(submission_id):
    """System principal: freeze rows verbatim, create/refresh the engagement, D0 + RP tags, event + anchor."""
    return {"engagement_id": "", "submission_id": submission_id, "rows": 0, "next_steps": []}
