# Deploy (Voroa or any Linux box)

**Needs:** Python 3.11, 2 vCPU / 4 GB is plenty (no GPU), outbound internet only for the optional OpenAI calls.

## Option A: Docker
```bash
docker build -t auditpilot .
docker run -p 8000:8000 -p 8501:8501 \
  -e PUBLIC_HOST=<your-host> -e PUBLIC_URL=https://<your-host>/mcp \
  -e OPENAI_API_KEY=... -e LLM_ENABLED=1 -e OPENAI_MODEL_DEV=... -e OPENAI_MODEL_DEMO=... \
  -v auditpilot-data:/app/data auditpilot
```

## Option B: plain process
```bash
pip install -r requirements.txt
PUBLIC_HOST=<your-host> PUBLIC_URL=https://<your-host>/mcp sh scripts/start.sh
```

## Notes
- **First boot** seeds the demo company with its planted irregularities (about 4 min for 7,000 invoices) and runs one warm-up audit. Later boots reuse `data/`. **If the platform's disk isn't persistent,** mount a volume on `data/`, or the company is re-seeded on every restart (and `identities.json` tokens change; then set `IDENTITIES` to a file kept in the platform's secrets).
- `PUBLIC_HOST` **must** be the public hostname; otherwise the MCP server refuses the request (421 Invalid Host header).
- **The judge card** (tokens per role) is printed in the logs at first boot, and also lives in `identities.json`. **Never** give the `ptn_` partner token to an agent.
- **Secrets** (`OPENAI_API_KEY`, `PORTAL_SECRET`, `N8N_SECRET`) go in the platform's env/secret settings, never in git.
- **Health check:** `GET /mcp` without a token returns 401. That's expected, and it proves the server is up.
- **Connect an agent:** `claude mcp add --transport http auditpilot https://<host>/mcp --header "Authorization: Bearer aud_…"`.
