"""Supabase accounts for the web app (vault/07 §3b). Identity still comes only from the Bearer token.

A Supabase session token is checked by Supabase itself (GET /auth/v1/user); the answer is cached until the token
expires. The principal is "sb:<user id>". The ROLE is never taken from Supabase (user_metadata is user-editable): it
comes from the organisation's tenant.json "roles" map, for the organisation this request runs against (X-Tenant).
An invited e-mail ("invites" in tenant.json) becomes a member the first time that user's token is seen there.
Agent tokens (identities.json) and the MCP gateway are unchanged.
"""
import base64
import hashlib
import json
import time
import urllib.error
import urllib.request

from app import config, tenants

SUPABASE_URL = config.env("SUPABASE_URL", "https://ysimtmaxmdkubvkbpyes.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = config.env("SUPABASE_ANON_KEY", "")
INVITE_ROLES = ("audit_staff", "engagement_partner", "client_admin", "accounts", "sales", "warehouse")

# ponytail: in-process cache of verified tokens (sha256 -> (user, expiry)); one Supabase round trip per new token.
# Upgrade path: verify ES256 locally against the project's JWKS with `cryptography` if latency matters.
_CACHE = {}


def looks_like_jwt(token):
    return (token or "").count(".") == 2 and (token or "").startswith("ey")


def _exp(token):
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return int(claims.get("exp", 0))
    except Exception:  # noqa: BLE001
        return 0


def verify(token):
    """Supabase session token -> {"id", "email"}; LookupError when Supabase does not accept it."""
    key = hashlib.sha256(token.encode()).hexdigest()
    hit = _CACHE.get(key)
    if hit and hit[1] > time.time():
        return hit[0]
    if not SUPABASE_ANON_KEY:
        raise LookupError("UNAUTHENTICATED: Supabase sign-in is not configured on this server (SUPABASE_ANON_KEY)")
    req = urllib.request.Request(f"{SUPABASE_URL}/auth/v1/user",
                                 headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LookupError("UNAUTHENTICATED: the Supabase session is invalid or expired; sign in again") from e
    except OSError as e:
        raise LookupError("UNAUTHENTICATED: Supabase could not be reached to check the session") from e
    user = {"id": data["id"], "email": (data.get("email") or "").lower()}
    _CACHE[key] = (user, min(_exp(token), time.time() + 3600) or time.time() + 300)
    return user


def principal_of(user):
    return f"sb:{user['id']}"


def current_tenant():
    """The tenant this request runs against (config ContextVar set by tenant_scope), default when none."""
    return tenants.current()


def _save(t):
    path = tenants._root() / t["slug"] / "tenant.json"
    path.write_text(json.dumps({k: v for k, v in t.items() if k != "default"}, indent=2), encoding="utf-8")


def role_in(t, user):
    """The user's role in tenant t (accepting a pending invite for their e-mail), or None."""
    if t.get("default"):
        return None                       # the demo company is for agent/judge tokens only
    p = principal_of(user)
    roles = t.setdefault("roles", {})
    if p not in roles and user["email"] and user["email"] in t.get("invites", {}):
        roles[p] = t["invites"].pop(user["email"])
        t.setdefault("emails", {})[p] = user["email"]
        if p not in t["principals"]:
            t["principals"] = sorted({*t["principals"], p})
        _save(t)
    return roles.get(p)


def identity(token):
    """Supabase token -> {principal, role, name, email}; role is None where the user holds none (403 later)."""
    user = verify(token)
    t = current_tenant()
    role = role_in(t, user)
    p = principal_of(user)
    return {"principal": p, "role": role, "name": user["email"], "email": user["email"], "account": "supabase",
            "membership_no": t.get("membership_no", {}).get(p)}


def memberships(token):
    """Every organisation where this user holds a role (accepting pending invites) -> [{slug, name, role}]."""
    user = verify(token)
    out = []
    for t in tenants.registry():
        r = role_in(t, user)
        if r:
            out.append({"slug": t["slug"], "name": t["name"], "role": r})
    return out


def create_org(token, name, pan, gstin, fy, membership_no=None):
    """Onboarding: a new organisation whose creator is its engagement partner."""
    user = verify(token)
    p = principal_of(user)
    t = tenants.create(name, pan, gstin, fy, [p], p)
    t["roles"] = {p: "engagement_partner"}
    t["emails"] = {p: user["email"]}
    if membership_no:
        t["membership_no"] = {p: str(membership_no).strip()[:20]}
    _save(t)
    return t


def invite(token, slug, email, role):
    """The engagement partner of `slug` invites an e-mail with a role (taken up at that user's next request)."""
    user = verify(token)
    t = tenants.get(slug)
    if role_in(t, user) != "engagement_partner":
        raise PermissionError("PERMISSION_DENIED: only the engagement partner of this organisation can invite")
    email = (email or "").strip().lower()
    if "@" not in email or len(email) > 254:
        raise ValueError("INVALID_ARGUMENT: email must be an e-mail address. Example: cfo@client.in")
    if role not in INVITE_ROLES:
        raise ValueError(f"INVALID_ARGUMENT: role must be one of {', '.join(INVITE_ROLES)}")
    t.setdefault("invites", {})[email] = role
    _save(t)
    return {"slug": slug, "email": email, "role": role, "status": "invited"}


def members(slug):
    """Members and pending invites of a tenant (e-mails, roles) for its partner's screen."""
    t = tenants.get(slug)
    emails = t.get("emails", {})
    return {"members": [{"email": emails.get(p, p), "role": r} for p, r in sorted(t.get("roles", {}).items())],
            "invites": [{"email": e, "role": r} for e, r in sorted(t.get("invites", {}).items())]}
