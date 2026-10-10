"""The agent-operability contract (04 §3), shared by tools_client.py and tools_audit.py.

- Errors: ToolError("<CODE>: what. how to fix. Example: ...") with CODE in 04 §3.3; service exceptions are mapped.
- Money in: rupees as strings ("118000.50") -> paise. Money out: paise ints + "₹" text in summaries.
- Lists: limit (default 25, max 100) + opaque cursor; every result ends with next_steps.
- Client text (names, addresses, narrations, reasons, file names, register cells, extracted text) goes under
  client_data, control characters stripped and capped at 300 chars. Server prose never interpolates it.
"""
import re
import sqlite3

from app import money
from app.gateway import ToolError, caller

CODES = ("UNAUTHENTICATED", "PERMISSION_DENIED", "NOT_FOUND", "INVALID_ARGUMENT", "PRECONDITION_FAILED", "CONFLICT")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁦-⁩]")


def coded(e):
    msg = str(e)
    if msg.split(":", 1)[0] in CODES:
        return msg
    if isinstance(e, LookupError):
        return f"NOT_FOUND: {msg}"
    if isinstance(e, PermissionError):
        return f"PERMISSION_DENIED: {msg}"
    if isinstance(e, FileNotFoundError):
        return f"PRECONDITION_FAILED: {msg}"
    return f"INVALID_ARGUMENT: {msg}"


def call(fn):
    """Run fn(principal, role) as the caller; anticipated failures become ToolError (04 §3.3)."""
    who, role = caller()
    try:
        return fn(who, role)
    except ToolError:
        raise
    except (ValueError, LookupError, PermissionError, FileNotFoundError) as e:
        raise ToolError(coded(e)) from e
    except sqlite3.OperationalError as e:
        if "readonly" in str(e):
            raise ToolError("PERMISSION_DENIED: this identity has read-only access to the client's records "
                            "(independence: auditors never change business data).") from e
        raise ToolError("PRECONDITION_FAILED: the database is busy; retry in a moment.") from e


def clean(v, cap=300):
    if isinstance(v, str):
        v = _CTRL.sub("", v)
        return v if len(v) <= cap else v[:cap] + "…"
    return v


def scrub(row, text_fields=()):
    """Sanitise every string; move free-text fields (client-originated) under row['client_data']."""
    out, cd = {}, {}
    for k, v in row.items():
        if k in text_fields and v not in (None, ""):
            cd[k] = clean(v)
        else:
            out[k] = clean(v) if isinstance(v, str) else v
    if cd:
        out["client_data"] = cd
    return out


def paise(v, name, required=False):
    """Rupees as a string -> integer paise; None stays None unless required."""
    if v is None or v == "":
        if required:
            raise ToolError(f"INVALID_ARGUMENT: {name} is required, in rupees as a string. Example: {name}=\"118000.50\"")
        return None
    if not isinstance(v, str):
        raise ToolError(f"INVALID_ARGUMENT: {name} must be rupees as a string with at most 2 decimals, "
                        f"e.g. {name}=\"118000.50\" (numbers are refused so no float ever reaches the books)")
    try:
        return money.to_paise(v)
    except Exception as e:  # noqa: BLE001
        raise ToolError(f"INVALID_ARGUMENT: {name} must be like \"118000.50\" (>= 0, max 2 decimals)") from e


# rupee field -> paise field, converted wherever it appears (lines, rows of import_records)
MONEY = {"rate": "rate_paise", "discount": "discount_paise", "amount": "amount_paise", "taxable": "taxable_paise",
         "tax": "tax_paise", "list_rate": "list_rate_paise", "cost": "cost_paise", "value_override": "value_override_paise",
         "debit": "dr_paise", "credit": "cr_paise", "round_off": "round_off_paise"}


def money_in(obj):
    """Recursively rename rupee fields to *_paise and convert them (lists of lines, import rows)."""
    if isinstance(obj, list):
        return [money_in(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in MONEY:
                out[MONEY[k]] = paise(v, k)
            elif k.endswith("_paise") and not isinstance(v, int):
                raise ToolError(f"INVALID_ARGUMENT: send money as rupee strings ('{k[:-6]}': \"1500.00\"), not {k}")
            else:
                out[k] = money_in(v)
        return {k: v for k, v in out.items() if v is not None}
    return obj


def limit_of(limit):
    try:
        n = int(limit or 25)
    except (TypeError, ValueError):
        n = 25
    return max(1, min(100, n))


def offset_of(cursor):
    if cursor in (None, ""):
        return 0
    if not str(cursor).isdigit():
        raise ToolError("INVALID_ARGUMENT: cursor must be the next_cursor value from the previous page")
    return int(cursor)


def page(rows, limit, cursor):
    """In-memory paging for small lists: -> (items, next_cursor)."""
    n, off = limit_of(limit), offset_of(cursor)
    chunk = rows[off:off + n]
    return chunk, (str(off + n) if off + n < len(rows) else None)


def steps(*triples):
    return [{"tool": t, "example_args": a, "why": w} for t, a, w in triples]


def result(summary, items=None, next_cursor=None, next_steps=(), **extra):
    out = {"summary": summary}
    if items is not None:
        out["items"] = items
        out["next_cursor"] = next_cursor
    out.update(extra)
    out["next_steps"] = list(next_steps)
    return out


def from_service(res, summary=None, text_fields=()):
    """Shape an erp service result {result, next_steps} for the agent."""
    r = scrub(res["result"], text_fields)
    return result(summary or r, next_steps=res.get("next_steps", []), **({"result": r} if summary else {}))


def inr(paise_v):
    return money.fmt_inr(paise_v)
