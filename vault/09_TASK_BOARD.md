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
| IB-7 | when docs arrive | Voroa adapter slot per `10 §3` (1.5 h time box) | IB-6 | one real call/action from the workflow |

## Darshan: data, register, related parties, workpaper, ShipReady
| ID | T | Task | Depends | Done when |
|---|---|---|---|---|
| DA-1 | T1–T6 | `seed.py` complete: FY 2025-26 history **through the erp services** (date order, realistic recorded_at lags), receipts + bank, schemes, CNs, GST filings, post-period Apr–May 2026 docs, demo evidence for likely samples. **Plants:** ≥2 per family in `05 §18` (one naive, one evasive), plus injection regression strings. `data/answer_key.json` (never read by app code). Register export in Fig. 1 columns + a doctored copy + an RP list with an omission and a wrong date. `identities.json` + judge card | SH-4 | `python -m app.seed --reset` runs in <60 s for 7,000 invoices |
| DA-2 | T2–T6 | `intake.py` (`submit`, `on_client_upload`), `register.py` (`parse_verbatim` xlsx/csv, `map_columns` with Fig. 1 headers, `reconcile` = D0 incl. totals tie-out) | SH-2 | `tests/test_verbatim.py` passes; every K-family plant caught |
| DA-3 | T3–T8 | `related_parties.py`: D1 graph (STRONG/MEDIUM/WEAK, fan-out guard, GSTIN checksum, PAN in GSTIN), D2 windows/statuses/RP_PERIOD_MISSTATED | DA-1 | A- and B-family plants caught; a CA's phone shared by 6 customers gives no edge |
| DA-4 | T6–T12 | `workpaper.py`: 4 sheets per `06` (header blocks, verbatim copy rules incl. `data_type='s'`, columns, tick marks, DRAFT, footer chain heads) | DA-2, IB-5, AA-3 | opens in Excel and LibreOffice; looks like Figs. 2–3 |
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

## Demo script (≈7 min; owner Shriyans)
1. **Judge card.** Show the roles; the auditor token can't even *see* client tools.
2. As **client** (Claude Code): run one sale end to end. Then plant three things: an invoice dated 31 Mar with dispatch on 2 Apr; a customer sharing a director's bank account; a manual JV `Cr SALES`. Upload a doctored register (`upload_sales_register` with edits).
3. As **auditor**: `get_engagement_status` → `reconcile_register_to_system` → `run_analytics`, and all three plants plus the register edits surface with plain-language reasons → `select_samples` (show seed + reasons) → the client uploads evidence (one forged) → `test_sample` flags `BELONGS_TO_OTHER_TXN`.
4. The client amends the LR date → `check_for_changes` names the stale sample, the field diff and the actor. Edit the SQLite file directly → `verify_integrity` reports an out-of-band edit + anchor mismatch.
5. **n8n:** the email/Telegram notifications that fired along the way.
6. **Partner UI:** confirm the findings → sign off → open the xlsx (4 sheets) + memo with AJEs → `python scripts/verify_trail.py audit_trail.jsonl` → OK.
