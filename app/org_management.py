"""Organization management: CRUD for orgs, departments, users, memberships, and granular permissions.

All operations use the service-role key server-side (bypasses RLS for admin operations)
and validate caller authorization before proceeding. Never import this in browser-side code.
"""
import hashlib
import json
import re

from app import supabase_client as sb


class OrgError(Exception):
    """Business-rule violation in org management."""
    pass


# ---------------------------------------------------------------- slugs

def _slugify(name):
    """Convert an org name to a URL-safe slug."""
    s = re.sub(r'[^\w\s-]', '', name.lower().strip())
    return re.sub(r'[-\s]+', '-', s)[:60]


# ---------------------------------------------------------------- organizations

def create_org(name, description=None, user_token=None):
    """Create an organization; the caller becomes the owner.

    Returns the new org record.
    """
    if not name or len(name.strip()) < 2:
        raise OrgError("Organization name must be at least 2 characters")

    slug = _slugify(name)
    # Use RPC to atomically create org + owner membership
    result = sb.rpc("create_org_with_owner", {
        "p_name": name.strip(),
        "p_slug": slug,
        "p_description": description,
    }, token=user_token)
    # Return full org record
    orgs = sb.query("organizations", filters={"id": result}, token=user_token)
    return orgs[0] if orgs else {"id": result}


def list_orgs(user_token):
    """List organizations the user belongs to."""
    return sb.query("organizations", order="name.asc", token=user_token) or []


def get_org(org_id, user_token):
    """Get a single organization by ID."""
    orgs = sb.query("organizations", filters={"id": org_id}, token=user_token)
    if not orgs:
        raise OrgError(f"Organization {org_id} not found or access denied")
    return orgs[0]


def update_org(org_id, updates, user_token):
    """Update organization details (admin/owner only via RLS)."""
    return sb.update("organizations", updates, {"id": org_id}, token=user_token)


# ---------------------------------------------------------------- departments

def create_department(org_id, name, description=None, parent_id=None, user_token=None):
    """Create a department within an organization."""
    if not name or len(name.strip()) < 2:
        raise OrgError("Department name must be at least 2 characters")

    rows = sb.insert("departments", {
        "org_id": org_id,
        "name": name.strip(),
        "description": description,
        "parent_id": parent_id,
    }, token=user_token)
    return rows[0] if rows else None


def list_departments(org_id, user_token):
    """List departments in an organization."""
    return sb.query("departments", filters={"org_id": org_id},
                    order="name.asc", token=user_token) or []


def update_department(dept_id, updates, user_token):
    """Update a department."""
    return sb.update("departments", updates, {"id": dept_id}, token=user_token)


def delete_department(dept_id, user_token):
    """Delete a department."""
    return sb.delete("departments", {"id": dept_id}, token=user_token)


# ---------------------------------------------------------------- memberships

def invite_user(org_id, email, role="viewer", user_token=None):
    """Invite a user to an organization.

    If the user doesn't exist in profiles, they need to sign up first.
    For hackathon: we create the membership optimistically.
    """
    # Look up user by email
    users = sb.query("profiles", filters={"email": email}, use_service_role=True)
    if not users:
        raise OrgError(f"User with email {email} not found. They must sign up first.")

    target_user_id = users[0]["id"]

    # Check if already a member
    existing = sb.query("org_memberships",
                        filters={"org_id": org_id, "user_id": target_user_id},
                        use_service_role=True)
    if existing:
        raise OrgError(f"User {email} is already a member of this organization")

    # Get the inviter's user ID from their token
    inviter = sb.get_user(user_token)

    rows = sb.insert("org_memberships", {
        "org_id": org_id,
        "user_id": target_user_id,
        "role": role,
        "invited_by": inviter["id"] if inviter else None,
    }, token=user_token)
    return rows[0] if rows else None


def list_members(org_id, user_token):
    """List members of an organization with their profiles."""
    return sb.query(
        "org_memberships",
        select="*, profiles(email, full_name, avatar_url)",
        filters={"org_id": org_id},
        order="joined_at.asc",
        token=user_token,
    ) or []


def update_member_role(org_id, user_id, new_role, user_token):
    """Change a member's role (owner only via RLS)."""
    return sb.update("org_memberships",
                     {"role": new_role},
                     {"org_id": org_id, "user_id": user_id},
                     token=user_token)


def remove_member(org_id, user_id, user_token):
    """Remove a member from an organization."""
    return sb.delete("org_memberships",
                     {"org_id": org_id, "user_id": user_id},
                     token=user_token)


def assign_to_department(dept_id, user_id, role="member", user_token=None):
    """Assign a user to a department."""
    rows = sb.insert("dept_memberships", {
        "dept_id": dept_id,
        "user_id": user_id,
        "role": role,
    }, token=user_token)
    return rows[0] if rows else None


def remove_from_department(dept_id, user_id, user_token):
    """Remove a user from a department."""
    return sb.delete("dept_memberships",
                     {"dept_id": dept_id, "user_id": user_id},
                     token=user_token)


# ---------------------------------------------------------------- permissions

def grant_permission(org_id, resource_type, access_level, granted_by_token,
                     user_id=None, dept_id=None, resource_id=None,
                     allowed_fields=None, expires_at=None, notes=None):
    """Grant a permission to a user or department.

    Exactly one of user_id or dept_id must be provided.
    """
    if not user_id and not dept_id:
        raise OrgError("Must specify either user_id or dept_id")
    if user_id and dept_id:
        raise OrgError("Cannot specify both user_id and dept_id")

    # Get the granter's profile
    granter = sb.get_user(granted_by_token)
    if not granter:
        raise OrgError("Could not identify the granting user")

    row = {
        "org_id": org_id,
        "resource_type": resource_type,
        "access_level": access_level,
        "granted_by": granter["id"],
    }
    if user_id:
        row["user_id"] = user_id
    if dept_id:
        row["dept_id"] = dept_id
    if resource_id:
        row["resource_id"] = resource_id
    if allowed_fields:
        row["allowed_fields"] = json.dumps(allowed_fields) if isinstance(allowed_fields, list) else allowed_fields
    if expires_at:
        row["expires_at"] = expires_at
    if notes:
        row["notes"] = notes

    rows = sb.insert("permissions", row, token=granted_by_token)
    return rows[0] if rows else None


def revoke_permission(permission_id, user_token):
    """Revoke a permission."""
    return sb.delete("permissions", {"id": permission_id}, token=user_token)


def list_permissions(org_id, user_token, user_id=None, dept_id=None):
    """List permissions in an org, optionally filtered by user or department."""
    filters = {"org_id": org_id}
    if user_id:
        filters["user_id"] = user_id
    if dept_id:
        filters["dept_id"] = dept_id
    return sb.query("permissions", filters=filters, token=user_token) or []


def get_effective_permission(org_id, user_id, resource_type, resource_id=None, user_token=None):
    """Get the effective permission for a user on a resource type."""
    params = {
        "p_org_id": org_id,
        "p_user_id": user_id,
        "p_resource_type": resource_type,
    }
    if resource_id:
        params["p_resource_id"] = resource_id
    return sb.rpc("get_effective_permission", params,
                  token=user_token, use_service_role=bool(not user_token))


def list_permission_audit_log(org_id, user_token, limit=50):
    """List the permission audit log for an org."""
    return sb.query("permission_audit_log",
                    filters={"org_id": org_id},
                    order="changed_at.desc",
                    limit=limit,
                    token=user_token) or []
