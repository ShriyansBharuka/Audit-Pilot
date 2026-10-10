"""One-command audit run on the seeded company: the client uploads a doctored register (family K plants) and its
RP list, then the auditor's full-population pipeline runs (D0 reconcile, D1-D14 analytics, AuditGraph), and the
result is evaluated against data/answer_key.json. Used for the PPT numbers and as a demo warm-up.

    python -m app.seed --reset [--invoices 7000]
    python -m app.demo_audit [--metrics docs/pitch/metrics.json]

Same service functions the MCP tools call (no shortcuts into the detectors); the answer key is only read by
app.evaluate at the very end.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from openpyxl import load_workbook

from app import analytics, config, db, erp, evaluate, intake, plants, risk_graph


def _step(label, fn):
    t = time.perf_counter()
    out = fn()
    print(f"  {label:<32} {time.perf_counter() - t:6.1f} s")
    return out


def run(metrics_path=None, k=30):
    key_path = config.DATA_DIR / "answer_key.json"
    key = json.loads(key_path.read_text(encoding="utf-8"))
    exp = _step("export register (client)", lambda: erp.export_sales_register("adm.kiran", "client_admin")["result"])
    with db.borrow("pbc", "system") as p:
        path = p.execute("SELECT stored_path FROM exports WHERE id = ?", (exp["export_id"],)).fetchone()[0]
    rows = [r[0] for r in load_workbook(path, read_only=True).active.iter_rows(min_row=2, values_only=True)]
    edits, drop, add, stubs = plants.register_edits(rows)
    with db.borrow("erp", "system") as e:
        inv_id = dict(e.execute("SELECT invoice_no, id FROM invoices"))
    k_plants = []
    for s in stubs:
        if s["code"] == "NOT_IN_SOR":
            oid, otype = str(len(rows) - len(drop) + 1), "register_row"     # the appended row's data row number
        elif s["code"] == "MISSING_FROM_REGISTER":
            oid, otype = inv_id[rows[s["row_no"] - 1]], "invoice"
        else:                                           # altered cells are reported on the register row
            oid, otype = str(s["row_no"] - sum(1 for d0 in drop if d0 < s["row_no"])), "register_row"
        k_plants.append({"family": "K", "code": s["code"], "object_type": otype, "object_id": oid,
                         "note": "register edit at upload"})
    if not any(p["family"] == "K" for p in key["plants"]):
        key["plants"] += k_plants
        key_path.write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")

    def upload_register():
        content, name = intake.build_register(exp["export_id"], edits, drop, add, role="client_admin")
        return intake.on_client_upload(intake.submit("SALES_REGISTER", content, name, "adm.kiran"))
    up = _step("doctored register upload + D0", upload_register)
    rp_csv = (config.DATA_DIR / "rp_list_demo.csv").read_bytes()
    _step("RP list upload + D1/D2", lambda: intake.on_client_upload(
        intake.submit("RP_LIST", rp_csv, "related_parties.csv", "adm.kiran")))
    an = _step("analytics D3-D14 (100%)", lambda: analytics.run_all(config.ENGAGEMENT_ID))
    g = _step("AuditGraph build", lambda: risk_graph.build(config.ENGAGEMENT_ID))
    ev = _step("evaluate vs answer key", lambda: evaluate.evaluate(key["plants"], k))
    print(json.dumps({"register_rows": up.get("rows"), "d0_hits": up.get("d0_hits"), "analytics": an.get("counts"),
                      "company": g.get("company"), "cycles": len(g.get("cycles", []))}, default=str, ensure_ascii=False)[:1500])
    print(json.dumps(ev, indent=1))
    if metrics_path:
        Path(metrics_path).write_text(json.dumps(ev, indent=1), encoding="utf-8")
        print("metrics ->", metrics_path)
    return ev


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.demo_audit", description=__doc__.split("\n\n")[0])
    ap.add_argument("--metrics", help="write the evaluate output here (e.g. docs/pitch/metrics.json)")
    ap.add_argument("--k", type=int, default=30)
    a = ap.parse_args(argv)
    run(a.metrics, a.k)


if __name__ == "__main__":
    sys.exit(main())
