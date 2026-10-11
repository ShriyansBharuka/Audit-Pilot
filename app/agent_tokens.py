"""Agent tokens for web accounts (vault/04 §2, 07 §3b): connect an AI agent over MCP to *your* organisation.

A signed-in web account creates a token in an organisation where it holds a role. The token is shown once; only its
SHA-256 is kept, in that organisation's tenant.json ("agent_tokens"). The agent gets the account's role there, except
the engagement partner, whose agent gets audit_staff: partner decisions and sign-off stay human (web UI only).
The MCP gateway resolves the token to (principal, role, organisation) and runs every call against that organisation.
"""
import hashlib
import json
import secrets

from app import config, tenants

PREFIX = "agt_"
AGENT_ROLE = {"engagement_partner": "audit_staff"}     # never hand the partner's powers to an agent


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _save(t):
    path = tenants._root() / t["slug"] / "tenant.json"
    path.write_text(json.dumps({k: v for k, v in t.items() if k != "default"}, indent=2), encoding="utf-8")


def create(slug, principal, account_role, label):
    """-> (token, record). The plain token exists only in this return value."""
    t = tenants.get(slug)
    if t.get("default"):
        raise PermissionError("PERMISSION_DENIED: the demo company uses the tokens in identities.json")
    label = " ".join(str(label or "").split())[:60] or "My agent"
    token = PREFIX + secrets.token_urlsafe(24)
    rec = {"id": "AT-" + secrets.token_hex(4), "hash": _hash(token), "principal": principal,
           "role": AGENT_ROLE.get(account_role, account_role), "label": label, "hint": token[-4:],
           "created_at": config.now()}
    t.setdefault("agent_tokens", []).append(rec)
    _save(t)
    return token, public(rec)


def public(rec):
    return {k: rec[k] for k in ("id", "role", "label", "hint", "created_at")}


def mine(slug, principal):
    return [public(r) for r in tenants.get(slug).get("agent_tokens", []) if r["principal"] == principal]


def revoke(slug, principal, token_id):
    t = tenants.get(slug)
    keep = [r for r in t.get("agent_tokens", []) if not (r["id"] == token_id and r["principal"] == principal)]
    if len(keep) == len(t.get("agent_tokens", [])):
        raise LookupError("NOT_FOUND: no such agent token of yours in this organisation")
    t["agent_tokens"] = keep
    _save(t)


def lookup(token):
    """agt_ token -> {principal, role, slug, name} or None (revoked / unknown / role since removed)."""
    if not (token or "").startswith(PREFIX):
        return None
    h = _hash(token)
    for t in tenants.registry():
        for r in t.get("agent_tokens", []):
            if secrets.compare_digest(r["hash"], h):
                if r["principal"] not in t.get("roles", {}):       # the account lost its role: the token dies too
                    return None
                return {"principal": r["principal"], "role": r["role"], "slug": t["slug"],
                        "name": f"{r['label']} ({t.get('emails', {}).get(r['principal'], r['principal'])})"}
    return None
