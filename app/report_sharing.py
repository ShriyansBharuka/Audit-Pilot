"""Report sharing: publish, share, field-filter, and track access to audit reports.

Reports are published from the existing SQLite audit engine's output.
Sharing rules are stored in Supabase and enforced at both the API and UI layers.
The actual report content stays in local files; Supabase holds metadata and access controls.
"""
import hashlib
import json
import os

from app import supabase_client as sb


class ShareError(Exception):
    """Business-rule violation in report sharing."""
    pass


# ---------------------------------------------------------------- report publishing

# Standard field manifests for different report types
WORKPAPER_FIELDS = [
    {"name": "invoice_no", "label": "Invoice No", "is_summary": True},
    {"name": "invoice_date", "label": "Invoice Date", "is_summary": True},
    {"name": "party_name", "label": "Party Name", "is_summary": True},
    {"name": "taxable_amount", "label": "Taxable Amount", "is_summary": True},
    {"name": "total_amount", "label": "Total Amount", "is_summary": True},
    {"name": "sor_match", "label": "SoR Match", "is_summary": True},
    {"name": "rp_status", "label": "RP Status", "is_summary": False},
    {"name": "detector_hits", "label": "Detector Hits", "is_summary": False},
    {"name": "risk_score", "label": "Risk Score", "is_summary": False},
    {"name": "sample_ref", "label": "Sample Ref", "is_summary": False},
    {"name": "test_result", "label": "Test Result", "is_summary": False},
    {"name": "evidence_status", "label": "Evidence Status", "is_summary": False},
    {"name": "finding_id", "label": "Finding ID", "is_summary": False},
    {"name": "aje_impact", "label": "AJE Impact", "is_summary": False},
]

FINDINGS_FIELDS = [
    {"name": "finding_id", "label": "Finding ID", "is_summary": True},
    {"name": "title", "label": "Title", "is_summary": True},
    {"name": "category", "label": "Category", "is_summary": True},
    {"name": "severity", "label": "Severity", "is_summary": True},
    {"name": "gross_impact", "label": "Gross Impact", "is_summary": True},
    {"name": "status", "label": "Status", "is_summary": True},
    {"name": "explanation", "label": "Explanation", "is_summary": False},
    {"name": "standards", "label": "Standards", "is_summary": False},
    {"name": "proposed_aje", "label": "Proposed AJE", "is_summary": False},
    {"name": "evidence_refs", "label": "Evidence References", "is_summary": False},
    {"name": "decision_note", "label": "Decision Note", "is_summary": False},
]

FIELD_MANIFESTS = {
    "workpaper": WORKPAPER_FIELDS,
    "memo": FINDINGS_FIELDS,
    "trail": [
        {"name": "seq", "label": "Sequence", "is_summary": True},
        {"name": "at", "label": "Timestamp", "is_summary": True},
        {"name": "principal", "label": "Principal", "is_summary": True},
        {"name": "tool", "label": "Tool", "is_summary": True},
        {"name": "outcome", "label": "Outcome", "is_summary": True},
        {"name": "args_summary", "label": "Arguments", "is_summary": False},
    ],
    "full_audit": WORKPAPER_FIELDS + FINDINGS_FIELDS,
}


def publish_report(org_id, title, engagement_id, report_type, file_path=None,
                   description=None, user_token=None):
    """Publish an audit report (makes it available for sharing).

    Args:
        org_id: organization UUID
        title: human-readable title
        engagement_id: SQLite audit.engagements.id
        report_type: one of 'workpaper', 'memo', 'trail', 'full_audit', 'custom'
        file_path: server-side path to the generated file
        description: optional description
        user_token: authenticated user's JWT
    """
    file_hash = None
    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

    field_manifest = FIELD_MANIFESTS.get(report_type, [])

    row = {
        "org_id": org_id,
        "title": title,
        "description": description,
        "engagement_id": engagement_id,
        "report_type": report_type,
        "status": "draft",
        "file_hash": file_hash,
        "file_path": file_path,
        "field_manifest": json.dumps(field_manifest),
    }

    # Get user id from token
    user = sb.get_user(user_token)
    if user:
        row["created_by"] = user["id"]

    rows = sb.insert("audit_reports", row, token=user_token)
    return rows[0] if rows else None


def finalize_report(report_id, user_token):
    """Mark a report as published (available for sharing)."""
    import datetime
    return sb.update("audit_reports",
                     {"status": "published", "published_at": datetime.datetime.now().isoformat()},
                     {"id": report_id},
                     token=user_token)


def list_reports(org_id, user_token, status=None):
    """List audit reports in an organization."""
    filters = {"org_id": org_id}
    if status:
        filters["status"] = status
    return sb.query("audit_reports", filters=filters,
                    order="created_at.desc", token=user_token) or []


def get_report(report_id, user_token):
    """Get a single report."""
    reports = sb.query("audit_reports", filters={"id": report_id}, token=user_token)
    if not reports:
        raise ShareError(f"Report {report_id} not found or access denied")
    return reports[0]


# ---------------------------------------------------------------- sharing

def share_report(report_id, org_id, scope, shared_by_token,
                 user_id=None, dept_id=None, allowed_fields=None,
                 can_export=False, can_reshare=False, expires_at=None):
    """Share a report with a user or department.

    Args:
        scope: 'full', 'summary', or 'custom'
        allowed_fields: for 'custom' scope, list of field names
    """
    if not user_id and not dept_id:
        raise ShareError("Must specify either user_id or dept_id")
    if user_id and dept_id:
        raise ShareError("Cannot specify both user_id and dept_id")
    if scope == "custom" and not allowed_fields:
        raise ShareError("Custom scope requires allowed_fields")

    sharer = sb.get_user(shared_by_token)
    if not sharer:
        raise ShareError("Could not identify the sharing user")

    row = {
        "report_id": report_id,
        "org_id": org_id,
        "scope": scope,
        "can_export": can_export,
        "can_reshare": can_reshare,
        "shared_by": sharer["id"],
    }
    if user_id:
        row["shared_with_user_id"] = user_id
    if dept_id:
        row["shared_with_dept_id"] = dept_id
    if allowed_fields:
        row["allowed_fields"] = json.dumps(allowed_fields) if isinstance(allowed_fields, list) else allowed_fields
    if expires_at:
        row["expires_at"] = expires_at

    rows = sb.insert("report_shares", row, token=shared_by_token)

    # Log the share action
    _log_access(report_id, sharer["id"], "SHARE", scope=scope, token=shared_by_token)

    return rows[0] if rows else None


def revoke_share(share_id, reason, user_token):
    """Revoke a report share."""
    import datetime
    result = sb.update("report_shares",
                       {"revoked_at": datetime.datetime.now().isoformat(), "revoke_reason": reason},
                       {"id": share_id},
                       token=user_token)
    user = sb.get_user(user_token)
    if user:
        shares = sb.query("report_shares", filters={"id": share_id}, use_service_role=True)
        if shares:
            _log_access(shares[0]["report_id"], user["id"], "REVOKE", token=user_token)
    return result


def list_shares(report_id, user_token):
    """List all shares for a report."""
    return sb.query("report_shares",
                    select="*, profiles!shared_with_user_id(email, full_name), "
                           "departments!shared_with_dept_id(name)",
                    filters={"report_id": report_id},
                    order="shared_at.desc",
                    token=user_token) or []


def get_accessible_fields(report_id, user_token):
    """Get the fields a user can access for a report.

    Uses the database function that merges user + department shares.
    """
    user = sb.get_user(user_token)
    if not user:
        return []
    return sb.rpc("get_report_accessible_fields", {
        "p_report_id": report_id,
        "p_user_id": user["id"],
    }, token=user_token)


def filter_report_data(data, accessible_fields):
    """Filter report data to only include accessible fields.

    Args:
        data: list of dicts (report rows)
        accessible_fields: list of field defs from get_accessible_fields
    Returns:
        filtered list of dicts
    """
    if not accessible_fields:
        return []

    allowed_names = {f["name"] if isinstance(f, dict) else f for f in accessible_fields}

    return [{k: v for k, v in row.items() if k in allowed_names} for row in data]


# ---------------------------------------------------------------- access logging

def _log_access(report_id, user_id, action, scope=None, fields=None, token=None):
    """Log a report access event (append-only)."""
    row = {
        "report_id": report_id,
        "accessed_by": user_id,
        "action": action,
    }
    if scope:
        row["scope_used"] = scope
    if fields:
        row["fields_accessed"] = json.dumps(fields) if isinstance(fields, list) else fields

    try:
        sb.insert("report_access_log", row, token=token)
    except sb.SupabaseError:
        pass  # best-effort logging; don't break the operation


def log_view(report_id, user_token, fields_accessed=None):
    """Log a report view event."""
    user = sb.get_user(user_token)
    if user:
        _log_access(report_id, user["id"], "VIEW", fields=fields_accessed, token=user_token)


def log_export(report_id, user_token):
    """Log a report export/download event."""
    user = sb.get_user(user_token)
    if user:
        _log_access(report_id, user["id"], "EXPORT", token=user_token)


def get_access_log(report_id, user_token, limit=100):
    """Get the access log for a report (admin only via RLS)."""
    return sb.query("report_access_log",
                    filters={"report_id": report_id},
                    order="accessed_at.desc",
                    limit=limit,
                    token=user_token) or []
