"""DA-1 planted irregularities (08 §5) on top of the clean seed year, plus the held-out answer key.

Every plant is a real business event replayed through the same erp services as the clean year, in date order,
so the detectors see exactly what a judge's client agent could create live. Naive and evasive variants per family.
The answer key (data/answer_key.json) is written for app.evaluate only: no engine code reads it (05 §19.8).

Register-level plants (family K) are applied at upload time as edits to the client's export (register_edits()),
the same way a judge would doctor the register with upload_sales_register(base_export_id, edits=...).
Family H (forged / reused evidence) needs samples first, so it is planted live in the demo (evidence upload).
"""
import json
import random
import statistics
from datetime import date, timedelta

from app import seed

FY_END = "2026-03-31"
FAKE_EWB = "999999999999"


def _cust(plan, rng, used, state=None):
    """An ordinary, unrelated customer (not declared, not network, not already used by another plant)."""
    pool = [p for p in plan["parties"] if p["tags"] == "CUSTOMER" and p["id"] not in seed.DECLARED
            and not p["id"].startswith(("P-NET", "P-GRP", "P-PLA")) and p["id"] not in used and p.get("gstin")
            and (state is None or p["state_code"] == state)]
    c = pool[int(rng.random() * len(pool))]
    used.add(c["id"])
    return c


def _goods(plan):
    return [i for i in plan["items"] if not str(i["hsn"]).startswith("99") and not i["id"].startswith("CHG")]


def _lines(plan, rng, target_paise):
    it = _goods(plan)[int(rng.random() * len(_goods(plan)))]
    qty = max(1, round(target_paise / it["list_rate_paise"]))
    return [{"item_id": it["id"], "qty": qty, "rate_paise": it["list_rate_paise"], "discount_paise": 0}]


def _trn(plan):
    return next(p["id"] for p in plan["parties"] if "TRANSPORTER" in p["tags"])


def _sale(plan, rng, key, cust, inv_date, value_paise, unit="G2"):
    unit = "G11" if cust["state_code"] == "30" else unit
    return seed._manual_sale(key, cust, unit, inv_date, _lines(plan, rng, value_paise), 30, _trn(plan),
                             f"MH12PL{int(rng.random() * 9000) + 1000}", 180, f"LR-PL-{key}")


def _evs(rng, sales):
    """Events for plant sales (no extra GSTR-1 filings: the clean year already files every month). Each invoice
    also publishes its number under '<key>/no' so later events can refer to it with '@<key>/no'."""
    out = [e for e in seed._events(rng, sales, []) if e["service"] != "file_gstr1"]
    for e in out:
        if e["service"] == "issue_invoice":
            k = next(iter(e["out"])).split("/")[0]
            e["out"][f"{k}/no"] = "invoice_no"
    return out


def _find(evs, service, key):
    return next(e for e in evs if e["service"] == service and any(o.startswith(f"{key}/") for o in e["out"]))


def _ts(d, minutes):
    return seed._ts(date.fromisoformat(d), minutes)


def add_plants(plan, seed_no=7):
    """Mutates plan (parties, links, events) and returns the answer-key stubs [{family, code, ref, object_type}]
    whose `ref` is resolved to real ids after seed.load()."""
    rng = random.Random(seed_no * 7919 + 13)
    used, key, evs, sales = set(), [], [], []
    by_id = {p["id"]: p for p in plan["parties"]}

    def plant(family, code, object_type, ref, note):
        key.append({"family": family, "code": code, "object_type": object_type, "ref": ref, "note": note})

    # ---- A: undisclosed related parties through shared identifiers (naive: bank; evasive: PAN inside the GSTIN)
    d1, rel = by_id["P-DIR1"], by_id["P-REL3"]
    a1 = seed._party("P-PLA1", "ENTITY", "CUSTOMER", "Seabird Marine Traders", pan="AAQFS7731L",
                     gstin=seed.make_gstin("27", "AAQFS7731L"), state_code="27",
                     address="Office 3, Sagar Arcade, Vashi, Navi Mumbai", pincode="400703", phone="7000000201",
                     email="accounts@seabirdmarine.in", bank_account=d1["bank_account"], ifsc=d1["ifsc"])
    a2 = seed._party("P-PLA2", "ENTITY", "CUSTOMER", "Konkan Coastal Supplies", pan=None,
                     gstin=seed.make_gstin("30", rel["pan"]), state_code="30",
                     address="Shop 9, Market Road, Margao", pincode="403601", phone="7000000202",
                     email="konkancoastal@mailbox.in", bank_account="880011223344", ifsc="SBIN0000889")
    plan["parties"] += [a1, a2]
    for k, c, d, v in (("PA1a", a1, "2025-08-14", 18_00_000_00), ("PA1b", a1, "2026-01-09", 22_50_000_00),
                       ("PA2a", a2, "2025-11-20", 9_40_000_00), ("PA2b", a2, "2026-02-17", 11_20_000_00)):
        sales.append(_sale(plan, rng, k, c, d, v))
    plant("A", "UNDISCLOSED_RP", "party", "P-PLA1", "customer's bank account is director P-DIR1's")
    plant("A", "UNDISCLOSED_RP", "party", "P-PLA2", "proprietorship GSTIN embeds the PAN of P-REL3 (relative of P-DIR2)")

    # ---- B: related party beginning mid-period; the client's RP list says a later date
    b = _cust(plan, rng, used)
    plan["links"].append({"id": "L-PL1", "from_party": "P-DIR3", "to_party": b["id"], "relation": "DIRECTOR_OF",
                          "pct_bp": None, "effective_from": "2025-10-15", "effective_to": None, "source": "DIR-12"})
    plan.setdefault("rp_list_extra", []).append({"party": b["id"], "relation": "director", "since": "2026-01-01"})
    plant("B", "RP_PERIOD_MISSTATED", "party", b["id"], "director joined 2025-10-15, RP list says 2026-01-01")

    # ---- C: cut-off by transfer of control (naive: dispatch after year end; evasive: FOR-destination POD in April)
    c1 = _sale(plan, rng, "PC1", _cust(plan, rng, used), "2026-03-30", 14_80_000_00)
    c1["dispatch"]["moved_on"] = c1["dispatch"]["lr_date"] = "2026-04-03"
    c1["delivery"]["delivered_on"] = "2026-04-04"
    c2 = _sale(plan, rng, "PC2", _cust(plan, rng, used), "2026-03-29", 12_60_000_00)
    c2["so"]["delivery_terms"] = "FOR_DESTINATION"
    c2["delivery"]["delivered_on"] = "2026-04-03"
    sales += [c1, c2]
    plant("C", "PREMATURE", "invoice", "@PC1/inv", "invoiced 30 Mar, goods left 3 Apr")
    plant("C", "PREMATURE", "invoice", "@PC2/inv", "FOR-destination, POD 3 Apr")
    # backdated: dated 25 Mar but keyed in on 25 Apr, after April's documents
    c3 = _sale(plan, rng, "PC3", _cust(plan, rng, used), "2026-03-25", 9_75_000_00)
    sales.append(c3)
    plant("C", "BACKDATED_ENTRY", "invoice", "@PC3/inv", "dated 25 Mar, entered 25 Apr")

    # ---- D: turnover with no physical movement (naive: no dispatch; evasive: split below the e-way threshold)
    d1s = _sale(plan, rng, "PD1", _cust(plan, rng, used), "2026-02-12", 16_40_000_00)
    d1s["dispatch"], d1s["ewb"] = None, False
    sales.append(d1s)
    plant("D", "NO_MOVEMENT", "invoice", "@PD1/inv", "₹16.4 L invoice, nothing ever left the factory")
    ds = _cust(plan, rng, used, state="27")
    for n in range(3):
        s = _sale(plan, rng, f"PD2{n}", ds, "2026-01-20", 38_000_00)
        s["dispatch"], s["ewb"] = None, False
        sales.append(s)
        plant("D", "SPLIT_BELOW_THRESHOLD", "invoice", f"@PD2{n}/inv", "3 invoices < ₹50k same customer same day")

    # ---- E: period-end concentration of sales and discounts
    counts = {}
    for s0 in plan["sales"]:
        counts[s0["party_id"]] = counts.get(s0["party_id"], 0) + 1
    e1c = max((p for p in plan["parties"] if p["tags"] == "CUSTOMER" and p["id"] not in seed.DECLARED and p.get("gstin")
               and not p["id"].startswith(("P-NET", "P-GRP", "P-PLA")) and p["id"] not in used),
              key=lambda p: (counts.get(p["id"], 0), p["id"]))
    used.add(e1c["id"])
    # size each invoice to 0.8x the customer's median monthly billing so 5 of them clear D5's 3x run-rate at any scale
    by_m = {}
    for s0 in plan["sales"]:
        if s0["party_id"] == e1c["id"]:
            by_m[s0["invoice_date"][:7]] = by_m.get(s0["invoice_date"][:7], 0) + s0.get("taxable_paise", 0)
    e1v = max(6_50_000_00, int(0.8 * statistics.median(by_m.values()))) if by_m else 6_50_000_00
    for n, d in enumerate(("2026-03-19", "2026-03-23", "2026-03-25", "2026-03-27", "2026-03-30")):
        sales.append(_sale(plan, rng, f"PE1{n}", e1c, d, e1v))
    plant("E", "END_WINDOW_SHARE", "party", e1c["id"], "5 invoices in the last 10 business days")
    evs.append(seed._ev(_ts("2026-03-22", 600), "sales", "create_scheme",
                        {"name": "March volume push", "kind": "TRADE_DISCOUNT", "rate_bp": 1200, "valid_from": "2026-03-22",
                         "valid_to": "2026-03-31", "announced_on": "2026-03-22"}, out={"PE2/scheme": "id"}))
    e2c = _cust(plan, rng, used)
    for n, d in enumerate(("2026-03-24", "2026-03-26", "2026-03-28")):
        s = _sale(plan, rng, f"PE2{n}", e2c, d, 5_00_000_00)
        for ln in s["lines"] + s["so"]["lines"]:
            ln["discount_paise"] = ln["qty"] * ln["rate_paise"] * 12 // 100
        s["taxable_paise"] = sum(ln["qty"] * ln["rate_paise"] - ln["discount_paise"] for ln in s["lines"])
        s["so"].update(enquired_on="2026-03-22", quoted_on="2026-03-22",          # orders taken under the scheme
                       confirmed_on=(date.fromisoformat(d) - timedelta(days=1)).isoformat())
        sales.append(s)

    plant("E", "SCHEME_WINDOW", "scheme", "@PE2/scheme", "unapproved 12% scheme announced 22 Mar, valid 22-31 Mar")

    # ---- F: statutory documents and filings (value mismatch on the portal EWB; fake EWB number; left out of GSTR-1)
    f1 = _sale(plan, rng, "PF1", _cust(plan, rng, used), "2025-12-05", 10_00_000_00)
    f2 = _sale(plan, rng, "PF2", _cust(plan, rng, used), "2025-09-18", 7_20_000_00)
    f2["ewb"] = False
    f3 = _sale(plan, rng, "PF3", _cust(plan, rng, used), "2025-11-07", 8_10_000_00)
    sales += [f1, f2, f3]
    plant("F", "EWB_VALUE_MISMATCH", "invoice", "@PF1/inv", "e-way bill value 60% of the invoice")
    plant("D", "EWB_NOT_FOUND", "invoice", "@PF2/inv", "dispatch quotes e-way bill 999999999999")
    plant("F", "NOT_IN_GSTR1", "invoice", "@PF3/inv", "left out of the November GSTR-1")

    # ---- I: credit notes after the period end (naive: rate difference; evasive: 'return' with no inward goods)
    i1 = _sale(plan, rng, "PI1", _cust(plan, rng, used), "2026-03-28", 13_30_000_00)
    i2 = _sale(plan, rng, "PI2", _cust(plan, rng, used), "2026-03-27", 9_90_000_00)
    sales += [i1, i2]
    plant("I", "POST_PERIOD_REVERSAL", "credit_note", "@PI1/cn", "28 Mar sale, 12 Apr 'rate difference' CN")
    plant("I", "RETURN_WITHOUT_MOVEMENT", "credit_note", "@PI2/cn", "20 Apr 'sales return', no goods came back")

    # ---- events for all plant sales, then the per-plant twists
    evs += _evs(rng, sales)
    _find(evs, "generate_eway_bill", "PF1")["args"]["value_override_paise"] = f1["total_paise"] * 6 // 10
    _find(evs, "record_dispatch", "PF2")["args"]["ewb_no"] = FAKE_EWB
    for k in ("PE20", "PE21", "PE22"):
        _find(evs, "create_sales_order", k)["refs"]["scheme_id"] = "PE2/scheme"
    pc3 = sorted((e for e in evs if any(o.startswith("PC3/") for o in e["out"])
                  or any(str(r).startswith("PC3/") for r in e["refs"].values())), key=lambda e: e["at"])
    for n, e in enumerate(pc3):                    # PC3: keyed in on 25 Apr, same order (document dates unchanged)
        e["at"] = _ts("2026-04-25", 600 + 15 * n)
    nov = next(e for e in plan["events"] if e["service"] == "file_gstr1" and e["args"].get("period") == "202511")
    nov["args"]["omit_doc_nos"] = ["@PF3/no"]
    for k, cn_day, reason in (("PI1", "2026-04-12", "RATE_DIFF"), ("PI2", "2026-04-20", "SALES_RETURN")):
        s = i1 if k == "PI1" else i2
        evs.append(seed._ev(_ts(cn_day, 720), "accounts", "issue_credit_note",
                            {"cn_date": cn_day, "reason": reason, "lines": [{"invoice_no": f"@{k}/no",
                                                                            "taxable_paise": s["taxable_paise"]}]},
                            out={f"{k}/cn": "id"}))

    # ---- G: revenue entries that did not originate from a sale (naive: JV to SALES; evasive: post-closing JV
    #      to another revenue account against a director loan, dated 31 Mar but keyed in on 5 Apr)
    evs.append(seed._ev(_ts("2026-03-31", 1020), "accounts", "post_journal_entry",
                        {"voucher_date": "2026-03-31", "narration": "Sales adjustment",
                         "lines": [{"account_code": "SUSPENSE", "dr_paise": 25_00_000_00},
                                   {"account_code": "SALES", "cr_paise": 25_00_000_00}]}, out={"PG1/jv": "journal_no"}))
    evs.append(seed._ev(_ts("2026-04-05", 660), "accounts", "post_journal_entry",
                        {"voucher_date": "2026-03-31", "narration": "Year-end service income",
                         "lines": [{"account_code": "DIRECTOR_LOAN", "party_id": "P-DIR1", "dr_paise": 18_00_000_00},
                                   {"account_code": "OTHER_OPERATING_REVENUE", "cr_paise": 18_00_000_00}]},
                        out={"PG2/jv": "journal_no"}))
    plant("G", "REVENUE_WITHOUT_SALE", "journal", "@PG1/jv", "manual JV Dr Suspense / Cr Sales ₹25 L")
    plant("G", "POST_CLOSING", "journal", "@PG2/jv", "dated 31 Mar, posted 5 Apr, Dr director loan / Cr revenue")
    plant("G", "TIEOUT_RESIDUE", "engagement", "ledger", "ledger revenue exceeds sales by the two planted JVs")
    plant("F", "TIEOUT_RESIDUE", "engagement", "gstr1", "GSTR-1 short of the books by the omitted invoice")
    plant("C", "POST_CLOSING", "journal", "journal_of:@PC3/inv", "the backdated invoice's SALES voucher is post-closing")

    # ---- P: purchase to pay (vault/13 MT-2). The ABC case, a duplicate payment, a price variance, a wrong
    #      beneficiary, an unrecorded liability, and one that LOOKS short but is explained by a later receipt.
    abc = seed._party("P-PLV1", "ENTITY", "VENDOR", "ABC Industrial Supplies", pan="AAACA5521K",
                      gstin=seed.make_gstin("27", "AAACA5521K"), state_code="27",
                      address="Gala 14, Bhosari MIDC, Pune", pincode="411026", phone="7000000301",
                      email="sales@abcindustrial.in", bank_account="660011112222", ifsc="ICIC0000066")
    plan["parties"].append(abc)
    p_item = _goods(plan)[0]["id"]

    def p2p(key, vendor, po_date, qty, rate, terms, grns, bill=None, pays=(), advance=None):
        """PO -> optional advance -> GRNs [(date, qty)] -> optional bill (date, qty, taxable) -> payments
        [(date, amount, payee_account|None)]. Publishes <key>/po, /grn (first), /pb, /pay, /pay2."""
        out = [seed._ev(_ts(po_date, 570), "accounts", "create_purchase_order",
                        {"vendor_id": vendor, "item_id": p_item, "qty": qty, "rate_paise": rate, "po_date": po_date,
                         "payment_terms": terms}, out={f"{key}/po": "id"})]
        if advance:
            out.append(seed._ev(_ts(advance[0], 660), "accounts", "record_payment",
                                {"vendor_id": vendor, "amount_paise": advance[1], "settled_on": advance[0],
                                 "narration": "advance against PO"}, refs={"po_id": f"{key}/po"},
                                out={f"{key}/adv": "settlement_id"}))
        for n, (d, q) in enumerate(grns):
            out.append(seed._ev(_ts(d, 700 + n), "warehouse", "record_goods_receipt",
                                {"qty": q, "received_on": d, "received_by": "Stores"}, refs={"po_id": f"{key}/po"},
                                out={f"{key}/grn" if n == 0 else f"{key}/grn{n}": "id"}))
        if bill:
            d, q, taxable = bill
            out.append(seed._ev(_ts(d, 780), "accounts", "record_purchase",
                                {"vendor_id": vendor, "bill_no": f"{key}/BILL", "bill_date": d, "item_id": p_item, "qty": q,
                                 "taxable_paise": taxable, "tax_paise": taxable * 18 // 100},
                                refs={"po_id": f"{key}/po"}, out={f"{key}/pb": "id"}))
        for n, (d, amount, payee) in enumerate(pays):
            args = {"vendor_id": vendor, "amount_paise": amount, "settled_on": d}
            if payee:
                args.update(payee_account=payee, payee_ifsc="SBIN0000998")
            out.append(seed._ev(_ts(d, 840 + n), "accounts", "record_payment", args,
                                refs={"purchase_ids": f"{key}/pb"}, out={f"{key}/pay" if n == 0 else f"{key}/pay2": "settlement_id"}))
        return out

    with_tax = lambda t: t + t * 18 // 100
    evs += p2p("PP1", "P-PLV1", "2026-02-02", 100, 5_000_00, "ADVANCE", [("2026-02-20", 60)],
               bill=("2026-02-21", 100, 4_23_728_82), advance=("2026-02-05", 5_00_000_00))
    plant("P", "SHORT_RECEIPT", "purchase_order", "@PP1/po", "₹5 L paid in advance for 100 units, 60 received")
    evs += p2p("PP2", "P-VEN1", "2025-11-03", 12, 5_296_61, "CREDIT_30", [("2025-11-10", 12)],
               bill=("2025-11-11", 12, 63_559_33),
               pays=[("2025-12-01", with_tax(63_559_33), None), ("2025-12-04", with_tax(63_559_33), None)])
    plant("P", "DUPLICATE_PAYMENT", "settlement", "@PP2/pay2", "the same ₹75,000 bill paid twice, 3 days apart")
    evs += p2p("PP3", "P-VEN3", "2025-12-08", 50, 2_000_00, "CREDIT_30", [("2025-12-15", 50)],
               bill=("2025-12-16", 50, 50 * 2_300_00), pays=[("2026-01-14", with_tax(50 * 2_300_00), None)])
    plant("P", "PRICE_VARIANCE", "purchase_bill", "@PP3/pb", "billed at ₹2,300 a unit against a PO rate of ₹2,000")
    evs += p2p("PP4", "P-VEN4", "2026-01-05", 40, 4_000_00, "CREDIT_30", [("2026-01-12", 40)],
               bill=("2026-01-13", 40, 40 * 4_000_00), pays=[("2026-02-10", with_tax(40 * 4_000_00), "998877665544")])
    plant("P", "BENEFICIARY_MISMATCH", "settlement", "@PP4/pay", "paid to an account that is not the vendor's")
    evs += p2p("PP5", "P-VEN5", "2026-03-15", 30, 3_000_00, "CREDIT_30", [("2026-03-28", 30)],
               bill=("2026-04-03", 30, 30 * 3_000_00), pays=[("2026-05-05", with_tax(30 * 3_000_00), None)])
    plant("P", "UNRECORDED_LIABILITY", "goods_receipt", "@PP5/grn", "goods received 28 Mar, bill dated 3 Apr, no accrual")
    # control: billed and paid for 100 in March with 60 received; the other 40 arrive on 15 Apr -> explained, clean
    evs += p2p("PP6", "P-VEN3", "2026-02-09", 100, 1_000_00, "ADVANCE", [("2026-03-01", 60), ("2026-04-15", 40)],
               bill=("2026-03-02", 100, 1_00_000_00), advance=("2026-02-10", 1_00_000_00))

    plan["events"] = sorted(plan["events"] + evs, key=lambda e: e["at"])
    return key


def register_edits(export_rows):
    """Family K edits for upload_sales_register(base_export_id, edits, drop_rows, add_rows), applied to the export:
    an altered amount, an altered date, a dropped sale and a fabricated row. -> (edits, drop_rows, add_rows, stubs)."""
    n = len(export_rows)
    edits = [{"row_no": n // 3, "column": "Total Cost", "value": 999999},
             {"row_no": n // 2, "column": "Date", "value": "31-03-2026"}]
    drop = [2 * n // 3]
    add = [{"Bill no.": "G2/9999/25", "Date": "30-03-2026", "Customer": "Northline Traders",
            "Ledger Account": "SALES ACCOUNT", "State Code": 27, "GST No.": "27AAACN1234A1Z9",
            "Total Cost": 2450000, "Gross Amt.": 2891000}]
    stubs = [{"family": "K", "code": "TAXABLE_DIFF", "object_type": "invoice", "row_no": n // 3},
             {"family": "K", "code": "DATE_DIFF", "object_type": "invoice", "row_no": n // 2},
             {"family": "K", "code": "MISSING_FROM_REGISTER", "object_type": "invoice", "row_no": 2 * n // 3},
             {"family": "K", "code": "NOT_IN_SOR", "object_type": "register_row", "doc_no": "G2/9999/25"}]
    return edits, drop, add, stubs


def resolve(stubs, ids):
    """Answer-key stubs -> {family, code, object_type, object_id, note}."""
    from app import db
    out = []
    for s in stubs:
        ref = s["ref"]
        if ref.startswith("journal_of:"):
            with db.borrow("erp", "system") as e:
                row = e.execute("SELECT no FROM journals WHERE source_id = ? ORDER BY no LIMIT 1",
                                (ids.get(ref[len("journal_of:@"):]),)).fetchone()
            oid = row[0] if row else None
        else:
            oid = ids.get(ref[1:]) if ref.startswith("@") else ref
        if oid is None:
            raise SystemExit(f"plants: no id published for {ref}")
        out.append({"family": s["family"], "code": s["code"], "object_type": s["object_type"], "object_id": str(oid),
                    "note": s["note"]})
    return out


def write_answer_key(path, plants):
    path.write_text(json.dumps({"plants": plants, "note": "held out: read only by app.evaluate"}, indent=1,
                               ensure_ascii=False), encoding="utf-8")


OMITTED_RP = "P-GRP3"         # a declared group company the client leaves off its RP list


def demo_rp_csv(plan):
    """The client's RP list for the demo: one group company omitted and one relationship dated too late (B)."""
    clean = {**plan, "links": [l for l in plan["links"] if not l["id"].startswith("L-PL")]}   # list predates the plant
    csv = seed.declared_rp_csv(clean, omit=(OMITTED_RP,))
    by = {p["id"]: p for p in plan["parties"]}
    for x in plan.get("rp_list_extra", []):
        p = by[x["party"]]
        csv += f"\"{p['name']}\",{p['pan'] or ''},{p['gstin'] or ''},{x['relation']},{x['since']}\n"
    return csv


def network_and_list_plants(ids=None):
    """Plants that live in the seed's clean-year structures: the 05 §19.10 trading network (J) and the RP omitted
    from the client's list (A)."""
    return [{"family": "J", "code": "CIRCULAR_FLOW", "object_type": "party", "object_id": "P-NET1",
             "note": "goods cycle SELF -> Mandovi -> (common director) Zuari -> SELF"},
            {"family": "J", "code": "ROUND_TRIP_CASH", "object_type": "party", "object_id": "P-NET2",
             "note": "3-hop cash round trip through the Kerkar group"},
            {"family": "J", "code": "CIRCULAR_FLOW", "object_type": "party", "object_id": "P-NET3",
             "note": "cash cycle SELF -> Zuari -> Kerkar -> Sal Marine -> SELF"},
            {"family": "A", "code": "UNDISCLOSED_RP", "object_type": "party", "object_id": OMITTED_RP,
             "note": "declared group company left off the client's RP list"}] + [
            {"family": "J", "code": "ROUND_TRIP_GOODS", "object_type": "invoice", "object_id": str(ids[k]),
             "note": "network sale that closes a goods cycle"} for k in ("S-N0001/inv",) if ids and k in ids]
