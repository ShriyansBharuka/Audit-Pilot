# 09 · Task board (who builds what, in what order, and when it is done)

> Written by Claude, 2026-10-10. Specs: schema `03`, tools `04`, detectors `05`, deliverables `06`, contracts/schedule `07`, sponsors + LLM `10`.
> **How to use this file.**
> 1. Find your task ID.
> 2. Read the linked spec sections.
> 3. Build only the files listed.
> 4. Meet the "done when" check.
> 5. Append one line to `vault/PROGRESS.md` (`date time · ID · done/partial · note · next`).
>
> Prefixes: SH = Shriyans, IB = Ibrahim, DA = Darshan, AA = Aarav (detector codes D0–D14 are a different namespace).
> Worker column: **AG** Antigravity · **C2** Claude Code #2 (second PC) · **CL** this Claude (review/cores on request).

## Queue 2 (from 21:00): money trail + three-layer audit

**C2 (Darshan's Claude) works MT-1 → MT-8 in [`13_MONEY_TRAIL_BUILD.md`](13_MONEY_TRAIL_BUILD.md)** (P2P records, D15
detectors + plants, money trail, cases, multi-agent investigator, year-end layer, reports A/B, docs). Claude on
Shriyans's PC owns `web/` (frontend), `app/explain.py` (exact SHAP) and the REST guards, and builds the case /
money-trail / reports screens against `13 §6`. Queue 1 below is done.

## Who pulls what right now (updated 2026-10-10 15:00 · submission 08:00 tomorrow)

**Decision:** all coding runs on **Darshan's Claude Pro (C2)**, in the order below. Antigravity (Shriyans's PC) takes only the Streamlit UI and overflow. People own review, data plants, deployment, sponsors, the PPT and testing. We **are** using the MCP server (`04`). Short version for people: [`../WHO_DOES_WHAT.md`](../WHO_DOES_WHAT.md).

Status: DA-1a / DA-2 / DA-3 pure cores are done (25 tests green). No platform code yet, so C2 starts with the platform.

**C2 coding queue** (one Claude session per item; commit + push after each; log in `PROGRESS.md`):

| # | Task(s) | Why this order |
|---|---|---|
| 1 | ✅ **done 15:14 (4fa6848)**: **SH-1 + SH-2**: scaffold, `requirements.txt`, `config.py` (incl. `set_clock/now`, `UNITS`, `RISK_WEIGHTS`), `db.py`, `schema/*.sql` | everything imports these |
| 2 | **IB-1 + IB-2**: `chain.py`, `money.py`, `ledger.py`, test_tamper | the ledger is needed by erp |
| 3 | **IB-3 + SH-4**: `portal.py`, `erp.py` services (the kwargs the seed already calls). `write_doc` calls `risk_graph.on_event(doc_type, doc_id, erp_seq)` after commit (best-effort; a no-op stub until item 7; `05 §19.6`) | the system of record |
| 4 | **DA-1 load()**, **DA-2 reconcile + intake**, **DA-3 run_d1_d2**: wire the existing pure cores into the DB. The seed also adds the **synthetic group network** (`05 §19.10`: group entities + purchases/payments closing cycles through SELF, a 3-hop cash round trip, one legitimate job-work pair) | data flows end to end |
| 5 | **IB-4 + SH-3 + SH-5**: `trail.py`, `gateway.py` / `mcp_server.py` (04 §2 verbatim), tool wrappers | MCP server live (judges' entry point) |
| 6 | **AA-1**: sampling; **AA-2**: detectors D3/D4/D5/D6/D7/D9/D13 | what we're judged on |
| 7 | **DA-6**: AuditGraph `risk_graph.py` (`05 §19`: `build` + `on_event` per-event updates + **mandatory minimum-span decomposition** + five-factor E + limitations), `get_risk_graph`, `app/replay.py`, `app/evaluate.py` | the differentiator + demo + PPT numbers |
| 8 | **IB-5**: evidence + D11 stale + D12 integrity | change-after-testing story |
| 9 | **AA-3 + AA-4 + DA-4**: findings/AJEs, memo, 4-sheet xlsx | deliverables |
| 10 | ✅ **done 18:45**: **AA-5** investigator (live test waits for the key in `.env`); D10/D14 done; DA-1 plants + `demo_audit` (31/31 caught); IB-8 deploy files; `docs/FEASIBILITY.md` | P1 |

If C2 hits its Pro quota, hand the next queue item to Antigravity (the same task IDs and specs) and note it in `PROGRESS.md`.

**SH-7 Streamlit UI: ✅ built by Claude (Shriyans's PC), commit 47b5cce.** `ui/app.py` (MCP client) + `app/partner.py` + `app/explorer.py`: login + landing, client portal, auditor Overview / **Audit Investigation Explorer** (Network View, Transaction Timeline, Evidence & Change History) / Workpaper, partner review + sign-off (`HOW_IT_WORKS.md §5b`). C2: don't edit these files; Antigravity: polish only, after asking Shriyans.

## Start now (no dependencies; do these while the rest of the vault is read)
| ID | Owner · Worker | Task | Done when |
|---|---|---|---|
| SH-1 | Shriyans · AG | Repo tree per `07 §3`; `requirements.txt`; `app/config.py`; every module stubbed with the `07 §4` signatures returning valid shapes; `schema/*.sql` from `03` | `pip install -r requirements.txt` OK; `python -m app.selftest` runs on stubs |
| IB-1 | Ibrahim · C2 | `chain.py` + `money.py` exactly as in `03 §6` (port of ReliefNet `backend/app/ledger.py`); `tests/test_tamper.py` (4 cases) | test_tamper passes; `to_paise(1.5)` raises; `to_paise("118000.50") == 11800050` |
| DA-1a | Darshan · AG | Seed skeleton: fictional **Konkan Marine Controls Ltd**, units G2 (MH, state 27) and G11 (Goa, state 30), ~150 customers, ~40 items + CHG items, directors/KMP/relatives | `python -m app.seed --reset --invoices 300` builds the DBs |
| AA-1a | Aarav · C2 | `sampling.pps`, strata, `control_date()` as pure functions + unit tests | tests pass, including same-seed → same picks |

## Shriyans: platform, MCP, integration
| ID | T | Task | Depends | Done when |
|---|---|---|---|---|
| SH-2 | T0–T1 | `db.py`: `connect(db, role)` (03 §6), `init_all(reset)`, `tx()`, WAL, PRAGMAs | SH-1 | audit-role INSERT into erp raises "readonly database"; client role can't open audit.db |
| SH-3 | T0–T3 | `mcp_server.py` from `04 §2` **verbatim** (Gateway, Tokens, `tool()` decorator, TokenInPath, stdio/HTTP), `playbook.py` (PLAYBOOK, DENY_HINT), `whoami` | SH-2, IB-4 stub | `whoami` works over stdio (Claude Code) and HTTP; partner token → 401; audit token doesn't see client tools |
| SH-4 | T1–T6 | `erp.py`: `write_doc` + every service in `07 §4` (system numbering via `doc_counters`; postings via `ledger`; IRN/EWB/GSTR via `portal`; `import_records` ≤1000; `export_sales_register` in Fig. 1 columns; `render_document` as "Key: Value" text + PDF via PyMuPDF; amend/cancel rules for [V]/[F]) | IB-1, IB-2, IB-3 | `trace_sale` on a seeded invoice shows enquiry→…→journals; `amend_record` on an invoice returns a hint naming `cancel_document` |
| SH-5 | T3–T8 | `tools_client.py`, `tools_audit.py`: thin `@tool(...)` wrappers for all 45 tools in `04 §4`, following the operability contract (`04 §3`: pagination, ToolError codes, next_steps, client_data) | SH-3, SH-4 | `tests/test_rbac.py` full matrix passes; erp.db byte-identical after every denied call |
| SH-6 | T5–T11 | `selftest.py` = `07 §8.6`; integration owner at T6 and T11 | all P0 | selftest green on the 300-invoice seed |
| SH-7 | T6–T14 | `ui/app.py` (Streamlit, AG drives): token login; Overview, Transactions, Investigation (register vs SoR vs portal, documents, trail timeline, investigator transcript), Workpaper (sheets + downloads), Client portal (uploads, requests), **Partner review** (confirm/reject/modify, sign-off per `06 §9`) | SH-5 | a partner signs off a seeded engagement in the UI |
| SH-8 | T15–T17 | Judge kit: README run section, `scripts/judge_card.py`, tunnel, demo script, slides with Ibrahim | SH-6 | a teammate who never saw the code connects in <5 min |

## Ibrahim: integrity, portal, evidence, n8n
| ID | T | Task | Depends | Done when |
|---|---|---|---|---|
| IB-2 | T1–T3 | `ledger.py`: COA seed (03 §2), `post_journal` (Dr=Cr>0, accounts exist, party on DEBTORS/CREDITORS), `reverse_journal`, `trial_balance` | IB-1, SH-2 | unbalanced voucher rejected; every posting appears in erp_log |
| IB-3 | T1–T4 | `portal.py` (ext.db): `register_irn` (IRN = sha256(gstin+fy+type+no); HMAC signature with `PORTAL_SECRET`), `cancel_irn` (24 h rule), `generate_eway_bill` (12-digit no., valid 1 day per 200 km), `cancel_eway_bill`, `file_gstr1(omit, changes)`, `file_gstr3b` (T2), `bank_txn`, `verify_signature` | SH-2 | recomputed IRN matches; cancel after 24 h refused; GSTR-1 can be filed differently from the books |
| IB-4 | T2–T4 | `trail.py` (audit_trail row with erp anchor; `anchor()`), `notify.py` (`events` row + optional HMAC webhook) | IB-1 | every MCP call writes OK/DENIED/ERROR; `verify` clean; trail never contains a token |
| IB-5 | T4–T9 | `evidence.py`: content-addressed store, `extract` ("Key: Value" + PyMuPDF text + regex; else NEEDS_MANUAL_REVIEW), `test_sample` (D8 + Fig. 2 attributes), `bundle`, `check_for_changes` (D11), `verify_integrity` (D12, five checks); `scripts/verify_trail.py` (stdlib), `scripts/tamper_demo.py` | IB-3, AA-1 | forged EWB, other-transaction EWB and reused LR all flagged; consolidated LR not flagged; LR date amended after testing → stale sample with field diff + actor |
| IB-6 | T7–T11 | n8n workflows ×4 per `10 §1`; exported JSON in `n8n/`; orchestrator token | IB-4, SH-5 | register upload → notification; evidence request email + reminder; 15-min digest via the MCP Client node |
| IB-8 | **now: hello-world**, T15: real deploy | Deploy on **Voroa** per `10 §3`. First (≤45 min, now): a throwaway `whoami` MCP server + a Streamlit hello on Voroa, to learn the hostname, ports, env/secret handling and **whether the disk persists**. Write the findings in `PROGRESS.md`. T15: deploy the real services | — | judges' agent connects to `https://<voroa-host>/mcp` with a token |

## Darshan: data, register, related parties, workpaper, ShipReady
| ID | T | Task | Depends | Done when |
|---|---|---|---|---|
| DA-1 | T1–T6 | `seed.py` complete: FY 2025-26 history **through the erp services** (date order, realistic recorded_at lags), receipts + bank, schemes, CNs, GST filings, post-period Apr–May 2026 docs, demo evidence for likely samples. **Plants:** ≥2 per family in `05 §18` (one naive, one evasive), plus injection regression strings. `data/answer_key.json` (never read by app code). Register export in Fig. 1 columns + a doctored copy + an RP list with an omission and a wrong date. `identities.json` + judge card | SH-4 | `python -m app.seed --reset` runs in <60 s for 7,000 invoices |
| DA-2 | T2–T6 | `intake.py` (`submit`, `on_client_upload`), `register.py` (`parse_verbatim` xlsx/csv, `map_columns` with Fig. 1 headers, `reconcile` = D0 incl. totals tie-out) | SH-2 | `tests/test_verbatim.py` passes; every K-family plant caught |
| DA-3 | T3–T8 | `related_parties.py`: D1 graph (STRONG/MEDIUM/WEAK, fan-out guard, GSTIN checksum, PAN in GSTIN), D2 windows/statuses/RP_PERIOD_MISSTATED | DA-1 | A- and B-family plants caught; a CA's phone shared by 6 customers gives no edge |
| DA-4 | T6–T12 | `workpaper.py`: 4 sheets per `06` (header blocks, verbatim copy rules incl. `data_type='s'`, columns, tick marks, DRAFT, footer chain heads) | DA-2, IB-5, AA-3 | opens in Excel and LibreOffice; looks like Figs. 2–3 |
| DA-6 | T6–T11 | `risk_graph.py` per `05 §19`: graph, R/R′ (noisy-OR + 2-hop propagation), confidence C, company band. Pure core first over the `risk_hits` shape and DA-3's `analyse()` output; wire to the DB after SH-2; `get_risk_graph` wrapper for SH-5; Streamlit graph view (`st.graphviz_chart`) for SH-7 | DA-3, AA-2 | clean seed → company LOW; full plant set → HIGH with ≥4 families; top-20 nodes are planted items |
| DA-5 | T10–T14 (P1) | ShipReady "AuditPilot for Shopify" connector per `10 §2`; `/connectors/shopify` + `scripts/replay_shopify.py` first | SH-4 | replay creates SO/movement/CN/receipt with erp_log entries; the live store does the same |

## Aarav: audit brain
| ID | T | Task | Depends | Done when |
|---|---|---|---|---|
| AA-1 | T1–T5 | `sampling.py`: `select` (3 kinds per `05 §15`, testing-start anchor + snapshots on first call, evidence requests), `reproduce` | AA-1a, IB-4 | `tests/test_sampling.py` passes |
| AA-2 | T2–T9 | `analytics.py`: D3, D4, D5, D6, D7, D9, D13, D14 (+D10 T2), writing `risk_hits` with server-written plain-language reasons; [REG] rules first | SH-4, IB-3 | C/D/E/F/G/I-family plants caught; FP list reviewed with Claude |
| AA-3 | T5–T9 | `findings.py`: `from_hits`, AJE templates `06 §6` (balanced, COA codes), materiality defaults (OM 0.5% of revenue, PM 75% of OM, trivial 5% of OM; auditor can override), SA 450 summary | AA-2 | every finding has impact + standards + AJE or NULL |
| AA-4 | T8–T12 | `memo.py` per `06 §7` (md + html) | AA-3 | renders; FINAL only after sign-off |
| AA-5 | T9–T13 (P1) | `investigator.py` per `10 §4` (Agents SDK + MCP stdio + CostMeter) | SH-5 | investigates 5 findings for <$1 on Sol; transcript appears in the Investigation view |

## Everyone
| ID | When | Task |
|---|---|---|
| ALL-1 | T11 | Judge simulation (`07 §6`): one person plays client, one plays auditor, each with a fresh agent and only a token |
| ALL-2 | T11–T15 | Recall/false-positive pass vs `answer_key.json`; fix in the owning module |
| ALL-3 | T15–T17 | Rehearse the demo: plant live → catch live → partner signs → verify the trail offline |
| CL-1/2 | T6, T11 | Ping Claude (this machine) with `PROGRESS.md` + the repo for a review pass |
| ALL-4 | T9–T17 | **PPT** (owner: Aarav; Darshan helps): ~10 slides per `07 §6` + a 2-min screen-recorded demo as backup. Screenshots come from the Voroa deployment |

## Demo script (≈7 min; owner Shriyans)
1. **Judge card.** Show the roles; the auditor token can't even *see* client tools.
2. As **client** (Claude Code): run one sale end to end. Then plant three things: an invoice dated 31 Mar with dispatch on 2 Apr; a customer sharing a director's bank account; a manual JV `Cr SALES`. Upload a doctored register (`upload_sales_register` with edits).
3. As **auditor**: `get_engagement_status` → `reconcile_register_to_system` → `run_analytics`, and all three plants plus the register edits surface with plain-language reasons → `select_samples` (show seed + reasons) → the client uploads evidence (one forged) → `test_sample` flags `BELONGS_TO_OTHER_TXN`.
4. The client amends the LR date → `check_for_changes` names the stale sample, the field diff and the actor. Edit the SQLite file directly → `verify_integrity` reports an out-of-band edit + anchor mismatch.
5. **n8n:** the email/Telegram notifications that fired along the way.
6. **Partner UI:** confirm the findings → sign off → open the xlsx (4 sheets) + memo with AJEs → `python scripts/verify_trail.py audit_trail.jsonl` → OK.
