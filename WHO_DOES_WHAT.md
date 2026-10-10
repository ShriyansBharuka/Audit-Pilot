# Who does what (submission 08:00 IST, 11 Oct · PPT + working prototype)

**Product:** AuditPilot AI, one web app (Streamlit) + an **MCP server** that judges' agents connect to, hosted on **Voroa**. Its risk engine is **AuditGraph**. Details: `vault/09_TASK_BOARD.md`.

| Who | Does | Done by |
|---|---|---|
| **Darshan's Claude Pro** | **All backend coding**, in the queue order in `vault/09` ("C2 coding queue"): platform → ledger → ERP → wire register/RP code → MCP server → detectors → AuditGraph → evidence/stale/integrity → workpaper/memo | queue items 1–6 by ~21:00, 7–9 by ~01:00 |
| **Shriyans + Antigravity** | Lead and integrator. Antigravity builds the **Streamlit UI** (incl. the risk graph and timeline). Shriyans merges, runs `python -m app.selftest`, drives the demo, and runs the judge simulation at ~23:30 | UI usable by 23:00 |
| **Darshan** | Run his Claude Pro (paste the next queue item, review, push). Own the **synthetic dataset plants** (≥2 per irregularity family, `vault/08 §5`) and check the answer key. ShipReady connector when its creds arrive | plants by 20:00 |
| **Ibrahim** | **Voroa:** hello-world deploy *now* (hostname, ports, secrets, does the disk persist?), real deploy at ~03:30. **n8n:** 4 workflows when the login arrives. Reviews chain/ledger/evidence code | hello-world by 16:00 |
| **Aarav** | **AuditGraph design owner:** review DA-6 against `vault/05 §19`, tune the weights, run `python -m app.evaluate` (precision/recall + ablation). Own the **PPT** (~10 slides) + the 2-min backup demo video. Investigator once the OpenAI key arrives | PPT draft by 02:00 |
| **Claude (Shriyans's PC)** | Spec owner. Reviews at ~18:30 and ~23:30; answers *Questions for Claude* in `vault/PROGRESS.md` | on ping |

**Rules:**
- Pull before you start and push after every task (`git pull --rebase`).
- Log one line in `vault/PROGRESS.md`.
- Never commit `.env`, keys or `data/`.
- Feature freeze at 05:30; submit by 07:30.
