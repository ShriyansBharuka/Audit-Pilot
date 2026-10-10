# AuditPilot AI: is it sound, fast enough and affordable?

Measured on the demo company (Konkan Marine Controls, FY 2025-26, **7,000 invoices + planted irregularities**) on a
laptop (Python 3.11, one core used: everything is single-threaded). Voroa's 2 vCPU shared box will be roughly 1.5-2x
slower per step; every number below still fits the demo with room to spare.

## 1. Results on the planted dataset

| | |
|---|---|
| Planted irregularities | **36** across the 10 PS families A-K plus purchase-to-pay P (32 in the books + 4 register edits at upload); one more P plant is an *explained* control that must stay clean, and does |
| Recall (plant caught by the right family/code) | **100%** (36/36; every family 100%, P 5/5) |
| Precision, severity >= 4 hits | **100%** (0 serious hits on un-planted records) |
| Invoices prioritised (R >= 60) | **13** of 7,003 |
| Company band | **HIGH**: risk-weighted exposure Rs 72.2 L vs performance materiality Rs 68.4 L; circular value Rs 56.4 L; 10 families hit |
| Audit cases (one per root cause of severity >= 4 hits) | **31**; every severity >= 4 plant sits in exactly one case (the 3 severity <= 3 plants stay hits) |
| Planted invoices in the top 30 by R (recall@30) | 100% for transaction-only, +graph, and +entity scoring alike |

The last row means the ablation doesn't separate the three scorers on this data (the plants are strong enough that
transaction features alone rank them). Entity risk earns its keep on the party view (round trips, undisclosed related
parties), not in this metric; we say so rather than claim a lift.

Honest framing: these are **our** plants on **our** synthetic data, so the numbers are a regression test that every
detector fires on the case it was built for and stays quiet on a clean year, not real-world accuracy. The clean
7k year (plants off) produces zero severity >= 4 hits on D0/D3/D4/D6/D7/D9/D13.

## 2. Latency

| Step | Time (7,003 invoices) |
|---|---|
| First boot only: seed the demo year (44k business events through the real ERP services) | 221 s |
| Client exports its sales register (xlsx) | 3.3 s |
| Client uploads the register: parse verbatim + freeze + D0 reconcile to the books + RP tagging | 8.5 s isolated (16.6 s inside the full pipeline run) |
| Client uploads the related-party list: D1/D2 | 5.7 s |
| Analytics D3-D14 over **100%** of the population | 11.1 s |
| AuditGraph full build (scores + cycle decomposition + company band) | 1.3 s |
| Re-run analytics + graph (warm) | 7.7 s |
| **Live client write -> risk updated** (per-event AuditGraph update) | 0.9 s for a 27-invoice customer, 1.7 s for 255, 2.3-3.4 s for the largest (818 invoices) |
| Peak memory (analytics + graph in one process) | 362 MB |


### Money trail, cases, year-end and reports (vault/13, measured 10 Oct on the same 7k company)

| Step | Time |
|---|---|
| `trace_money` on a PO chain, an invoice or a payment (hops 2) | 0.05 s |
| `trace_money` on the largest customer (818 invoices, aggregated edges) | 0.22 s |
| `trace_money` on a network party, hops 3 | 0.20 s |
| Rebuild all 31 cases (one money trail per case; runs at the end of every analytics run) | 1.2 s |
| `list_cases` (25) / `get_case` with its money trail | 0.02 s / 0.06 s |
| Year-end timeline (14 months) / March-April links | 0.12 s / 0.10 s |
| Report A / Report B, json + html | 0.13 s / 0.12 s |

All of these are interactive-speed. The cases rebuild adds about 1 s to a full analytics run.

So the whole audit, upload to risk map, is **under a minute**, and a judge's live edit shows up in the risk view
**within ~1-3 s**.

What dominates: openpyxl parsing the 7k-row xlsx (about 4 s of the upload). Everything else is SQLite reads into
memory plus Python loops, linear in the population. Rough scaling: 70k invoices ~ 10x these numbers (about 2.5 min
for a full analytics + graph run), still a batch job, not a request-path cost. The per-event update only loads the
touched customer's documents, so it stays flat as the company grows.

## 3. LLM cost (OpenAI investigator, the only paid part)

The deterministic engine (D0-D14, sampling, AuditGraph, workpapers) uses **no LLM at all**. The LLM only writes the
narrative investigation for one flagged item, through the same MCP tools any agent gets (audit_staff token).

Per-turn fixed prefix, measured: audit-role tool schemas **21 tools, ~3.4k tokens** + server PLAYBOOK ~0.3k + prompt
~0.2k + task ~0.3k = **~4.3k tokens**. A tool result is capped at ~8k tokens by pagination; a typical one is 1-3k.

Model of one investigation (max 8 turns, ~2.5k tokens of tool result + ~0.3k output per turn, final answer ~1.2k,
reasoning tokens counted as 2x visible output; turn n re-sends turn n-1's whole input, which OpenAI caches):

| | input uncached | input cached | output | Astra ($10 / $1 / $50) | Sol ($2 / $0.10 / $10) | Luna ($0.10 / $0.01 / $0.50) |
|---|---|---|---|---|---|---|
| typical | 24k | 89k | 7k | **$0.68** | **$0.13** | **$0.007** |
| worst case (no cache hits, every turn at max_tokens 2500) | 113k | 0 | 20k | $2.13 | $0.43 | $0.02 |

Per demo: the analyst investigates the prioritised items (R >= 60: 13 invoices) = **~$9 on
Astra, ~$1.70 on Sol**. Budget plan for the $700 credits: development on Sol (~100 runs, ~$13), three full
Astra rehearsals + the live demo (~4 x $9), about **$50 total, under 10% of the $700**.

Guard rails (code, not policy): `LLM_ENABLED=0` by default; CostMeter in `app/investigator.py` prices every call from
the API's own usage numbers and refuses a run when **today's spend + the run cap (default $3) > the day cap (default
$40)**; unknown model names are priced as Astra (safe side); every call is a row in `audit.llm_usage`. Also set a
project budget on the OpenAI key itself.

**Measured (first live run, 10 Oct 19:08):** one investigation of a flagged invoice on `gpt-6.1-sol` = **$0.024, 31 s, 3 tool calls**, about 5x cheaper than the typical-case model above (the agent needed 3 turns, not 8). Astra at the same token count is ~5x Sol, so **~$0.12**; a 13-item demo on Astra is ~$1.60. The table above stays as the conservative bound.
with a spinner in the UI; it never blocks the deterministic audit.

**Multi-agent case investigation (MT-5), cost model.** The risk, evidence and money-flow agents run in parallel, and each sees
only its read-only allow-list of tools. Measured schema prefixes: risk ~0.55k, evidence ~1.0k and money-flow ~0.56k tokens,
against ~4.7k for all 25 audit tools. Each agent is capped at 5 turns and 1,500 output tokens; the reporting agent has no tools,
2 turns and 2,500 output tokens. Assuming ~3 turns per specialist with 2-4k-token tool results, a run is about 29k uncached
input, 21k cached input and 7.5k output tokens: roughly **$0.13 on Sol** (bound) and $0.65 on Astra. The single-agent run
measured above came in 5x under its model, which would put a case at **~$0.03 on Sol**. Wall time is about the slowest
specialist plus the reporter, roughly 40 s.
**Measured live (11 Oct, case AUD-0014, the ABC short receipt, `gpt-6.1-sol`): $0.0917, 41 s, 11 tool calls** across
the three specialists + reporter; every cited record id was returned by a tool (0 unverified); amounts attached by code.
So the bound above was the right order: ~$0.09 per case on Sol, ~$0.45 on Astra.

## 4. Is the math sound?

| Piece | Claim | Check |
|---|---|---|
| Why 100% analytics, not sampling | 30 random picks out of 7,000 catch >= 1 of 10 planted items with p = 1 - C(6990,30)/C(7000,30) = **4.2%** (even 10x risk weighting only gets ~35%) | so detection runs on every record (SA 500 / SA 520 style analytics); samples are only for vouching evidence |
| Sampling | systematic PPS: item i is picked with p = min(1, n * v_i / V); items above the interval are certain picks | seed = `secrets.randbits(64)` stored with the population hash: unpredictable to the client (SA 240), yet `reproduce_selection` replays it exactly |
| Money trail | edges carry provenance VERIFIED / CLAIMED / INFERRED; numbers cover only the traced documents | no downstream attribution (A pays B, B pays C never implies A's money reached C); a cycle counts once at its minimum-span value, never the sum of its edges |
| Money | integer paise, GST rates in basis points | sums are exact (no 0.1 + 0.2 != 0.3); Dr = Cr checked per journal |
| Entry score A | noisy-OR: A = 100 * (1 - prod(1 - min(1, w_code * sev / 5))) | bounded [0, 100], monotone, order-independent. **Caveat:** it assumes detectors are independent, so two detectors flagging the same root cause push A up; acceptable for ranking, and the findings themselves are per detector |
| Entity score E | E = 0.35C + 0.25F + 0.15T + 0.15H + 0.10N, each term in [0, 100] | weights sum to 1.00, so E is in [0, 100] |
| Propagation N | N = max over related neighbours of (their previous E x link strength 1 / 0.5) | one hop, from the **previous** snapshot, weight 0.1: the update is a contraction (Lipschitz 0.1), so it converges and cannot run away even when related parties form a loop. One weak link alone can't lift a party above Review (clamped to 59) |
| Final R | R = max(0.7A + 0.3E, 60 if hard evidence of severity >= 4) | bounded [0, 100]; the floor stops averaging from hiding a portal/bank/register contradiction |
| Company band | exposure = sum(R / 100 x taxable) over entries with R >= 30, compared with performance materiality | **a risk-weighted exposure, not a probability**: R is a ranking score, not calibrated. That's why the memo quotes the actual findings vs materiality (SA 450) and uses the band only to prioritise |
| Round trips | minimum-span decomposition of time-ordered cycles (window 90 days, max 5 transaction edges, max 3 identity hops in a row) | terminates: each pass zeroes the residual of at least one edge; cost bounded by length and window |
| D5 period-end concentration | flag when share > median + 3 x MAD of the other month-ends (MAD floored at 2 points) | 3 raw MADs ~ 2 sigma (sigma ~ 1.48 MAD), so it is deliberately sensitive; it is severity 2 (an indicator) and only matters when cut-off or credit-note tests corroborate it |
| Benford (first digit) | MAD > 0.015 = nonconformity (Nigrini) | only meaningful when amounts span several orders of magnitude; reported as an indicator, never a finding on its own |
| Integrity | SHA-256 hash chain over canonical JSON, anchors copied into audit.db | tamper-**evident**: an edit without rehash, a rehash, or a rewritten tail all fail `verify_integrity`. Someone with write access to both files could rewrite both, so the chain head is also printed in the workpaper footer and the trail export |

## 5. Fits Voroa (2 vCPU / 4 GB shared, CPU only)

- Peak memory ~360 MB for the audit process; the MCP server + Streamlit add ~300 MB. Well inside 4 GB.
- CPU: the 7k audit is ~30 s of one core; a shared vCPU at half speed still finishes in about a minute.

- No GPU, no model hosting: the LLM is an API call and is optional.
- Disk: the four SQLite files are ~100 MB at 7k invoices; exports and evidence are small.
- First boot seeds and warms up once (`scripts/start.sh`); later boots reuse `data/`, so mount a persistent volume.
- Two processes (MCP server :8000, Streamlit :8501) on one box; n8n runs on n8n's cloud and calls in over HTTPS.

## 6. Known limits (said up front)

- Single-threaded Python: fine to ~100k invoices for a batch run; beyond that, move the population load to SQL
  aggregates first.
- Scores are heuristic rankings, not calibrated probabilities (no labelled real-world fraud data to calibrate on).
- The planted-data metrics measure detector coverage, not accuracy on real companies.
- The mock IRP/EWB/GSTN/bank portals stand in for the real APIs; the code reads them through one module, so a real
  connector replaces one file.
