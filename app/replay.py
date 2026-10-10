"""Replay mode (05 §19.6): a year of business in minutes, with AuditGraph watching.

    python -m app.replay [--invoices 300] [--seed 7] [--speed 600] [--every 400]

Rebuilds the databases, opens the engagement first (so every ERP commit reaches risk_graph.on_event, the year-round
mode), then replays the seed's entry-time-ordered events through the erp services at --speed events per second
(0 = as fast as possible). Every --every events it runs a full re-baseline (run_analytics: all detectors + cycles)
and prints the company band and the riskiest items, so the audience watches risk evolve before the annual audit.
"""
import argparse
import sys
import time

from app import analytics, config, db, erp, intake, seed


def _line(day, n, total, company, top):
    t = ", ".join(f"{i['object_id']} R={i['R'] // 1000}" for i in top[:3]) or "-"
    return (f"{day}  events {n:>6}/{total:<6} company {company['band']:<8} exposure {company['exposure_paise'] // 100:>12,} "
            f"families {','.join(company['families']) or '-':<12} top: {t}")


def _top(limit=3):
    with db.borrow("audit", "system") as a:
        return [dict(r) for r in a.execute(
            "SELECT object_id, R, band FROM risk_snapshots WHERE object_type = 'INVOICE' AND rowid IN"
            " (SELECT MAX(rowid) FROM risk_snapshots WHERE object_type = 'INVOICE' GROUP BY object_id)"
            " ORDER BY R DESC LIMIT ?", (limit,))]


def replay(n_invoices=300, seed_=7, speed=600.0, every=400, out=print):
    plan = seed.build_plan(n_invoices, seed_)
    db.init_all(reset=True)
    config.set_clock(seed.MASTERS_AT)
    eid = intake.ensure_engagement()                   # year-round mode: on_event scores every commit
    fy_taxable = sum(s["taxable_paise"] for s in plan["sales"] if s["invoice_date"] <= config.PERIOD_END)
    om = fy_taxable * config.OVERALL_MATERIALITY_BP_OF_REVENUE // 10000      # planning materiality for the year
    with db.borrow("audit", "system") as a, db.tx(a):
        a.execute("UPDATE engagements SET materiality_paise = ?, performance_materiality_paise = ?, trivial_paise = ?"
                  " WHERE id = ?", (om, om * config.PERFORMANCE_MATERIALITY_BP_OF_OM // 10000,
                                    om * config.TRIVIAL_BP_OF_OM // 10000, eid))
    events = plan["events"]
    total = len(events)
    ids = {}
    with erp.keep_open():
        config.set_clock(seed.MASTERS_AT)
        for service, rows in (("create_party", plan["parties"]), ("link_parties", plan["links"]),
                              ("create_item", plan["items"])):
            for row in rows:
                seed._call(erp, service, seed.PEOPLE["client_admin"], "client_admin", row, row["id"])
        # the client's (complete) related-party list, uploaded at the start of the year
        intake.on_client_upload(intake.submit("RP_LIST", seed.declared_rp_csv(plan).encode(), "related_parties.csv",
                                              seed.PEOPLE["client_admin"]))
        for n, ev in enumerate(events, 1):
            config.set_clock(ev["at"])
            args = dict(ev["args"])
            for arg, ref in ev["refs"].items():
                args[arg] = [ids[ref]] if arg.endswith(("_nos", "_ids")) else ids[ref]
            res = seed._call(erp, ev["service"], ev["actor"], ev["role"], args, ev["at"])
            for key, field in ev["out"].items():
                ids[key] = res["result"][field]
            if speed:
                time.sleep(1 / speed)
            if n % every == 0 or n == total:
                company = analytics.run_all(config.ENGAGEMENT_ID)["company"]
                out(_line(ev["at"][:10], n, total, company, _top()))
    config.set_clock(None)
    return plan


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.replay", description=__doc__.split("\n\n")[0])
    ap.add_argument("--invoices", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--speed", type=float, default=600.0, help="events per second (0 = no pause)")
    ap.add_argument("--every", type=int, default=400, help="full re-baseline every N events")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    replay(a.invoices, a.seed, a.speed, a.every)
    print(f"replayed in {time.perf_counter() - t0:.1f}s; risk history: list_audit_items / get_risk_graph, or the UI timeline")


if __name__ == "__main__":
    sys.exit(main())
