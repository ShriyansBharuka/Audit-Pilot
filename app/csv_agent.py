"""CSV verification agent (second agent framework: LangGraph).

An auditor uploads a CSV (a client schedule, a register extract, a list someone emailed). A LangGraph StateGraph runs:

    profile ──has data──▶ verify ──▶ summarize ──▶ END
        └────no data────▶ no_data ─┘

- profile: does the file contain data at all? (empty file, not text, header only, only blank rows) + columns, fill.
- verify: every data row against the books: a document-number column (invoice / bill / credit note) must exist in
  erp.db, and an amount column must agree (integer paise, the rupee string parsed exactly; no floats).
- summarize: a deterministic summary always; when the investigator LLM is configured and asked for, the model
  rewrites it from COUNTS and SYSTEM ids only (never the CSV's own text, so a file cannot inject instructions).
  Output is PROPOSED.

The upload is stored byte-for-byte under AUDIT_FILES_DIR/csv_checks/<sha256>.csv with a server-computed SHA-256
(plus the JSON result); nothing is cleaned. Read-only on the books. Deterministic steps decide; the LLM only words.
"""
import csv
import hashlib
import io
import json
import re
from typing import TypedDict

from app import config, db, money

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
KEY_COLS = ("invoice_no", "invoice_number", "invoice", "inv_no", "bill_no", "bill_number", "cn_no", "credit_note_no",
            "doc_no", "document_no", "document_number", "voucher_no")
AMOUNT_COLS = ("total", "total_amount", "invoice_value", "invoice_total", "amount", "value", "gross", "gross_amount",
               "taxable", "taxable_value", "taxable_amount")
DATE_COLS = ("invoice_date", "date", "doc_date", "bill_date", "document_date")
ROUND_OFF = 100                                     # ±₹1: invoice totals carry a round-off line


class State(TypedDict, total=False):
    content: bytes
    filename: str
    sha256: str
    use_llm: bool
    profile: dict
    verification: dict
    summary: dict
    path: list


def _norm(h):
    return re.sub(r"[^a-z0-9]+", "_", str(h or "").strip().lower()).strip("_")


def _decode(content):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return None, None


def profile(content, filename="upload.csv"):
    """-> {has_data, verdict, reason, rows_total, data_rows, blank_rows, columns, fill, delimiter, encoding}."""
    base = {"filename_ext": filename.rsplit(".", 1)[-1].lower() if "." in filename else "", "bytes": len(content)}
    if not content.strip():
        return {**base, "has_data": False, "verdict": "NO_DATA", "reason": "EMPTY_FILE", "rows_total": 0, "data_rows": 0,
                "blank_rows": 0, "columns": [], "fill": {}}
    if b"\x00" in content[:4096]:
        return {**base, "has_data": False, "verdict": "NO_DATA", "reason": "NOT_TEXT", "rows_total": 0, "data_rows": 0,
                "blank_rows": 0, "columns": [], "fill": {}}
    text, enc = _decode(content)
    try:
        delim = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    rows = []
    for i, r in enumerate(csv.reader(io.StringIO(text), delimiter=delim)):
        if i > MAX_ROWS:
            break
        rows.append(r)
    nonblank = [r for r in rows if any(c.strip() for c in r)]
    if not nonblank:
        return {**base, "has_data": False, "verdict": "NO_DATA", "reason": "BLANK_ROWS", "rows_total": len(rows),
                "data_rows": 0, "blank_rows": len(rows), "columns": [], "fill": {}, "delimiter": delim, "encoding": enc}
    header = nonblank[0]
    data = nonblank[1:]
    cols = [_norm(h) or f"col_{i + 1}" for i, h in enumerate(header)]
    fill = {c: sum(1 for r in data if i < len(r) and r[i].strip()) for i, c in enumerate(cols)}
    out = {**base, "rows_total": len(rows), "data_rows": len(data), "blank_rows": len(rows) - len(nonblank),
           "columns": cols, "fill": fill, "delimiter": delim, "encoding": enc, "truncated": len(rows) > MAX_ROWS}
    if not data:
        return {**out, "has_data": False, "verdict": "NO_DATA", "reason": "HEADER_ONLY"}
    return {**out, "has_data": True, "verdict": "HAS_DATA", "reason": None, "_rows": data}


def _paise(v):
    s = re.sub(r"(?i)(₹|rs\.?|inr)", "", str(v or "")).strip().replace(" ", "")
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        p = money.to_paise(s)
    except Exception:
        return "UNPARSED"
    return -p if neg else p


def _pick(cols, wanted):
    return next((cols.index(w) for w in wanted if w in cols), None)


def verify(prof, role="audit_staff"):
    """Every data row against the books -> {key_column, amount_column, counts{status: n}, rows (first 200 non-matches
    + 20 matches), found_doc_types}. Statuses: MATCHED, AMOUNT_MISMATCH, DATE_MISMATCH, NOT_IN_BOOKS, NO_KEY,
    UNPARSED_AMOUNT. Cell text appears only under `client_data`."""
    cols, rows = prof["columns"], prof.get("_rows", [])
    ki, ai, di = _pick(cols, KEY_COLS), _pick(cols, AMOUNT_COLS), _pick(cols, DATE_COLS)
    res = {"key_column": cols[ki] if ki is not None else None, "amount_column": cols[ai] if ai is not None else None,
           "date_column": cols[di] if di is not None else None, "counts": {}, "rows": [], "found_doc_types": {}}
    if ki is None:
        res["note"] = "NO_DOCUMENT_COLUMN"
        res["counts"] = {"NO_KEY": len(rows)}
        return res
    taxable_like = cols[ai].startswith("taxable") if ai is not None else False
    with db.borrow("erp", role) as e:
        inv = {r[0]: {"doc_type": "invoice", "id": r[1], "date": r[2], "taxable": r[3], "total": r[3] + r[4] + (r[5] or 0)}
               for r in e.execute("SELECT i.invoice_no, i.id, i.invoice_date, COALESCE(SUM(l.taxable_paise), 0),"
                                  " COALESCE(SUM(l.igst_paise + l.cgst_paise + l.sgst_paise), 0), i.round_off_paise"
                                  " FROM invoices i LEFT JOIN invoice_lines l ON l.invoice_id = i.id GROUP BY i.id")}
        for r in e.execute("SELECT c.cn_no, c.id, c.cn_date, COALESCE(SUM(l.taxable_paise), 0), COALESCE(SUM(l.igst_paise +"
                           " l.cgst_paise + l.sgst_paise), 0) FROM credit_notes c LEFT JOIN cn_lines l ON l.cn_id = c.id"
                           " GROUP BY c.id"):
            inv.setdefault(r[0], {"doc_type": "credit_note", "id": r[1], "date": r[2], "taxable": r[3], "total": r[3] + r[4]})
        for r in e.execute("SELECT bill_no, id, bill_date, taxable_paise, tax_paise FROM purchase_bills"):
            inv.setdefault(r[0], {"doc_type": "purchase_bill", "id": r[1], "date": r[2], "taxable": r[3], "total": r[3] + r[4]})
    counts, kept, matched_kept, types = {}, [], 0, {}
    for n, r in enumerate(rows, start=2):
        key = r[ki].strip() if ki < len(r) else ""
        cell = {"key": key}
        if ai is not None and ai < len(r):
            cell["amount"] = r[ai]
        if di is not None and di < len(r):
            cell["date"] = r[di]
        doc = inv.get(key) if key else None
        if not key:
            status, detail = "NO_KEY", {}
        elif doc is None:
            status, detail = "NOT_IN_BOOKS", {}
        else:
            types[doc["doc_type"]] = types.get(doc["doc_type"], 0) + 1
            status, detail = "MATCHED", {"doc_type": doc["doc_type"], "doc_id": doc["id"]}
            if ai is not None:
                amt = _paise(cell.get("amount"))
                if amt == "UNPARSED":
                    status = "UNPARSED_AMOUNT"
                elif amt is not None:
                    want = doc["taxable"] if taxable_like else doc["total"]
                    ok = abs(amt - want) <= (0 if taxable_like else ROUND_OFF) or (not taxable_like and amt == doc["taxable"])
                    if not ok:
                        status = "AMOUNT_MISMATCH"
                        detail.update(csv_paise=amt, books_paise=want, difference_paise=amt - want)
            if status == "MATCHED" and di is not None and cell.get("date"):
                d = cell["date"].strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) and d != doc["date"]:
                    status = "DATE_MISMATCH"
                    detail.update(books_date=doc["date"])
        counts[status] = counts.get(status, 0) + 1
        if status != "MATCHED" and len(kept) < 200:
            kept.append({"row": n, "status": status, **detail, "client_data": cell})
        elif status == "MATCHED" and matched_kept < 20:
            matched_kept += 1
            kept.append({"row": n, "status": status, **detail, "client_data": cell})
    res.update(counts=counts, rows=kept, found_doc_types=types)
    return res


def _deterministic_summary(p, v):
    if not p["has_data"]:
        why = {"EMPTY_FILE": "the file is empty", "NOT_TEXT": "the file is not a text CSV",
               "HEADER_ONLY": "it has a header row but no data rows", "BLANK_ROWS": "every row is blank"}[p["reason"]]
        return f"No data: {why}. Nothing was checked against the books."
    c = v.get("counts", {})
    total = sum(c.values())
    if v.get("note") == "NO_DOCUMENT_COLUMN":
        return (f"Has data: {p['data_rows']} data rows in {len(p['columns'])} columns, but no document-number column "
                f"(invoice / bill / credit note no.) was recognised, so rows could not be matched to the books.")
    parts = [f"{c.get('MATCHED', 0)} of {total} rows match the books"]
    for k, label in (("NOT_IN_BOOKS", "not found in the books"), ("AMOUNT_MISMATCH", "differ in amount"),
                     ("DATE_MISMATCH", "differ in date"), ("NO_KEY", "have no document number"),
                     ("UNPARSED_AMOUNT", "have an unreadable amount")):
        if c.get(k):
            parts.append(f"{c[k]} {label}")
    diff = sum(r.get("difference_paise", 0) for r in v.get("rows", []))
    tail = f" Net amount difference on listed rows {money.fmt_inr(diff)}." if diff else ""
    return f"Has data: {p['data_rows']} data rows. " + "; ".join(parts) + "." + tail


# ---------------------------------------------------------------- the LangGraph graph

def _n_profile(s: State) -> dict:
    return {"profile": profile(s["content"], s.get("filename") or "upload.csv"), "path": s.get("path", []) + ["profile"]}


def _n_verify(s: State) -> dict:
    return {"verification": verify(s["profile"]), "path": s["path"] + ["verify"]}


def _n_no_data(s: State) -> dict:
    return {"verification": {"counts": {}, "rows": [], "note": "SKIPPED_NO_DATA"}, "path": s["path"] + ["no_data"]}


def _n_summarize(s: State) -> dict:
    p, v = s["profile"], s["verification"]
    text = _deterministic_summary(p, v)
    out = {"text": text, "by": "deterministic", "status": "PROPOSED"}
    if s.get("use_llm"):
        ai = _llm_summary(p, v, text)
        if ai:
            out = {"text": ai["text"], "by": f"llm:{ai['model']}", "status": "PROPOSED", "usd": ai["usd"],
                   "deterministic": text}
        else:
            out["llm"] = "skipped (LLM off or capped)"
    return {"summary": out, "path": s["path"] + ["summarize"]}


def _route(s: State) -> str:
    return "verify" if s["profile"]["has_data"] else "no_data"


def graph():
    from langgraph.graph import END, START, StateGraph
    g = StateGraph(State)
    g.add_node("profile", _n_profile)
    g.add_node("verify", _n_verify)
    g.add_node("no_data", _n_no_data)
    g.add_node("summarize", _n_summarize)
    g.add_edge(START, "profile")
    g.add_conditional_edges("profile", _route, {"verify": "verify", "no_data": "no_data"})
    g.add_edge("verify", "summarize")
    g.add_edge("no_data", "summarize")
    g.add_edge("summarize", END)
    return g.compile()


def _llm_summary(p, v, fallback):
    """Counts and system ids only go to the model; never the CSV's cells."""
    from app import investigator
    ok, _why = investigator.ready()
    if not ok:
        return None
    try:
        meter = investigator.CostMeter()
        meter.check()
        from openai import OpenAI
        model = investigator.model_for()
        facts = {"data_rows": p["data_rows"], "columns": len(p["columns"]), "key_column": v.get("key_column"),
                 "amount_column": v.get("amount_column"), "counts": v.get("counts"),
                 "doc_types_found": v.get("found_doc_types"),
                 "issues": [{k: r.get(k) for k in ("row", "status", "doc_id", "difference_paise", "books_date")}
                            for r in v.get("rows", []) if r["status"] != "MATCHED"][:30],
                 "deterministic_summary": fallback}
        r = OpenAI().responses.create(
            model=model, max_output_tokens=600,
            instructions=("You are an audit assistant. In at most 90 words, tell the auditor whether this uploaded CSV "
                          "has data and how it reconciles to the books. Use only the JSON given; cite row numbers and "
                          "system ids; copy numbers exactly; amounts are paise (divide by 100 for rupees). No opinion."),
            input=json.dumps(facts))
        usd = meter.add(r.usage, model, "csv_agent:summary") / 1e6
        return {"text": r.output_text.strip(), "model": model, "usd": round(usd, 4)}
    except Exception:
        return None


def run(content, filename, actor, use_llm=False):
    """Store the upload verbatim, run the graph -> {sha256, filename, profile, verification, summary, path, framework}."""
    if len(content) > MAX_BYTES:
        raise ValueError(f"INVALID_ARGUMENT: file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    sha = hashlib.sha256(content).hexdigest()
    out_dir = config.AUDIT_FILES_DIR / "csv_checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{sha}.csv").write_bytes(content)
    st = graph().invoke({"content": content, "filename": filename, "sha256": sha, "use_llm": bool(use_llm), "path": []})
    prof = {k: v for k, v in st["profile"].items() if not k.startswith("_")}
    result = {"sha256": sha, "filename": filename, "checked_by": actor, "checked_at": config.now(),
              "framework": "LangGraph StateGraph", "path": st["path"], "profile": prof,
              "verification": st["verification"], "summary": st["summary"]}
    (out_dir / f"{sha}.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result
