# Who does what (submission 08:00 IST, 11 Oct · PPT + working prototype)

**Product:** AuditPilot AI, a web app (Next.js in `web/` + REST API on :8001; the Streamlit UI stays as backup) + an **MCP server** (:8000) that judges' agents connect to, hosted on **Voroa**. Its risk engine is **AuditGraph**. Details: `vault/09_TASK_BOARD.md`.

| Who | Does | Done by |
|---|---|---|
| **Darshan's Claude Pro** | **Backend for the money-trail feature**, queue **MT-1 → MT-8** in `vault/13_MONEY_TRAIL_BUILD.md`: purchase-to-pay records, D15 detectors + plants, money trail, cases, multi-agent investigator, year-end layer, reports A/B | MT-1..MT-4 by ~01:00, rest by ~04:00 |
| **Claude (Shriyans's PC)** | **Frontend** (Next.js app in `web/`) + exact **SHAP** (`app/explain.py`) + REST security; builds the case screen, money-trail view and reports pages against `vault/13 §6` as each MT item lands | as items land |
| **Shriyans** | Lead + integrator: pastes the prompt below into Darshan's Claude, merges, runs the demo and the judge simulation | — |
| **Darshan** | Runs his Claude Pro, reviews each MT push, checks the new P2P plants in the answer key. ShipReady when approved | — |
| **Ibrahim** | Owner of the web app's Supabase pages (orgs, RBAC, sharing, fraud hub). Voroa deploy (now also `uvicorn app.api_server:app --port 8001` + the Next.js build). n8n on the 14-day trial | deploy by ~03:30 |
| **Aarav** | PPT + demo video; add the money-trail / case slide once MT-4 lands; tune weights with `python -m app.evaluate` | PPT by 02:00 |

## Paste this into Darshan's Claude Code

> `git pull --rebase`, then read `CLAUDE.md`, `AGENTS.md` and **`vault/13_MONEY_TRAIL_BUILD.md`** (the whole file:
> §0 rules, §1 the feature, §4 the queue, §6 the REST contract). Work through **MT-1 → MT-2 → MT-3 → MT-4 → MT-5 →
> MT-6 → MT-7 → MT-8** in order without stopping. Don't edit `web/`, `ui/` or `app/explain.py`.
>
> After **each** item: `python -m pytest -q` and `python -m app.selftest` must pass; edit `vault/03` / `04` / `05`
> for any new table, tool or detector in the same commit; commit as `MT-n: <what>`; `git pull --rebase`; push; add
> one line to `vault/PROGRESS.md`. If you're about to run out of quota, finish and push the current item first:
> never leave the tree broken. Spec doubts go under *Questions for Claude* in `vault/PROGRESS.md`; go with the most
> literal reading.

**Rules:**
- Pull before you start and push after every task (`git pull --rebase`).
- Log one line in `vault/PROGRESS.md`.
- Never commit `.env`, keys or `data/`.
- Feature freeze at 05:30; submit by 07:30.
