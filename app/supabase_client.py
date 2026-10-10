"""Server-side Supabase client (service-role key stays server-side, never exposed to the browser).

Uses the anon key for user-authenticated requests and the service-role key for admin operations.
The service-role key is read from the SUPABASE_SERVICE_ROLE_KEY environment variable.
"""
import json
import os
from functools import lru_cache
from urllib.parse import urljoin

# ponytail: stdlib-only HTTP — upgrade path: httpx or supabase-py if we need realtime/storage
import urllib.request
import urllib.error

from app import config

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ysimtmaxmdkubvkbpyes.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


class SupabaseError(Exception):
    """Raised when a Supabase API call fails."""
    def __init__(self, message, status=None, details=None):
        super().__init__(message)
        self.status = status
        self.details = details


def _request(method, path, body=None, token=None, use_service_role=False, params=None):
    """Low-level REST call to the Supabase PostgREST API.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        path: API path (e.g. '/rest/v1/organizations')
        body: dict to send as JSON body
        token: user JWT for authenticated requests
        use_service_role: if True, use the service-role key (bypasses RLS)
        params: query parameters dict
    """
    url = urljoin(SUPABASE_URL, path)
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation",
    }

    if use_service_role:
        if not SUPABASE_SERVICE_ROLE_KEY:
            raise SupabaseError("SUPABASE_SERVICE_ROLE_KEY not configured")
        headers["apikey"] = SUPABASE_SERVICE_ROLE_KEY
        headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
    elif token:
        headers["apikey"] = SUPABASE_ANON_KEY
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["apikey"] = SUPABASE_ANON_KEY

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text.strip() else None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(error_body)
        except (json.JSONDecodeError, ValueError):
            details = {"raw": error_body}
        raise SupabaseError(
            f"Supabase API error {e.code}: {details.get('message', error_body[:200])}",
            status=e.code,
            details=details,
        ) from e


def _rpc(fn_name, params=None, token=None, use_service_role=False):
    """Call a Supabase database function (RPC)."""
    return _request("POST", f"/rest/v1/rpc/{fn_name}", body=params or {},
                    token=token, use_service_role=use_service_role)


# ---------------------------------------------------------------- convenience wrappers

def query(table, select="*", filters=None, token=None, use_service_role=False,
          order=None, limit=None, offset=None):
    """SELECT from a table with optional filters.

    Args:
        table: table name
        select: columns to select (PostgREST syntax)
        filters: dict of {column: value} or {column: "operator.value"}
        token: user JWT
        use_service_role: bypass RLS
        order: e.g. "created_at.desc"
        limit: max rows
        offset: pagination offset
    """
    params = {"select": select}
    if filters:
        for k, v in filters.items():
            if isinstance(v, str) and any(v.startswith(op) for op in ("eq.", "neq.", "gt.", "gte.",
                                                                       "lt.", "lte.", "like.", "in.")):
                params[k] = v
            else:
                params[k] = f"eq.{v}"
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)
    if offset:
        params["offset"] = str(offset)

    return _request("GET", f"/rest/v1/{table}", params=params, token=token,
                    use_service_role=use_service_role)


def insert(table, rows, token=None, use_service_role=False):
    """INSERT rows (single dict or list of dicts)."""
    return _request("POST", f"/rest/v1/{table}", body=rows, token=token,
                    use_service_role=use_service_role)


def update(table, values, filters, token=None, use_service_role=False):
    """UPDATE rows matching filters."""
    params = {}
    for k, v in filters.items():
        params[k] = f"eq.{v}" if not (isinstance(v, str) and "." in v) else v
    return _request("PATCH", f"/rest/v1/{table}", body=values, params=params,
                    token=token, use_service_role=use_service_role)


def delete(table, filters, token=None, use_service_role=False):
    """DELETE rows matching filters."""
    params = {}
    for k, v in filters.items():
        params[k] = f"eq.{v}" if not (isinstance(v, str) and "." in v) else v
    return _request("DELETE", f"/rest/v1/{table}", params=params,
                    token=token, use_service_role=use_service_role)


def rpc(fn_name, params=None, token=None, use_service_role=False):
    """Call an RPC function."""
    return _rpc(fn_name, params, token, use_service_role)


# ---------------------------------------------------------------- auth helpers

def sign_up(email, password, metadata=None):
    """Sign up a new user via Supabase Auth."""
    body = {"email": email, "password": password}
    if metadata:
        body["data"] = metadata
    return _request("POST", "/auth/v1/signup", body=body)


def sign_in(email, password):
    """Sign in and return the session (access_token, refresh_token, user)."""
    body = {"email": email, "password": password}
    headers_extra = {"apikey": SUPABASE_ANON_KEY}
    return _request("POST", "/auth/v1/token?grant_type=password", body=body)


def get_user(token):
    """Get the authenticated user from their JWT."""
    return _request("GET", "/auth/v1/user", token=token)
