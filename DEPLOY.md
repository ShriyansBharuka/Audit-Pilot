# Deploy AuditPilot

Two pieces:

| Piece | Where | What |
|---|---|---|
| Backend: REST API + MCP server, one port | **Render** (Docker, `render.yaml`) | `https://auditpilot-api.onrender.com` (your name may differ) |
| Web app (`web/`, Next.js) | **Vercel** | `https://<project>.vercel.app` |

Sign-in uses the Supabase project already configured; only its URL settings change.

## 1. Backend on Render (about 10 minutes, mostly the build)

1. Sign in at render.com with GitHub and allow access to the `ELEVATE-1-0/ELEV01` repository.
2. **New → Blueprint**, pick the repo. Render reads `render.yaml` and proposes one web service, `auditpilot-api`.
3. It asks for the one secret: **OPENAI_API_KEY** (paste it; leave empty to keep the AI parts off). Click **Apply**.
4. Wait for the build. It installs Python, then seeds the demo company (7,000 invoices) and the second organisation
   **into the image**, so starts are instant. When the log says `Your service is live`, open
   `https://<service>.onrender.com/api/health`: it answers `"status": "healthy"`.
5. **Demo organisations:** the same build step runs `scripts/demo_seed.py --inprocess`, which creates three
   organisations with e-mail logins (`docs/DEMO_ACCOUNTS.md`). It needs `SUPABASE_ANON_KEY`, which Render passes to
   the Docker build as a build argument from `render.yaml`. Search the build log for `Demo organisations`: each line
   should end in `all plants found`. Without the key the step is skipped, and the service still starts.
6. **Tokens (judge card):** open the build log and search for `Claude Code:` or `Bearer`. One token per role is printed
   there (`aud_…` auditor, `adm_…` client admin, `ptn_…` partner…). They stay the same until the next build.

Free plan notes: the service sleeps after 15 minutes without traffic (the first request then takes about a minute), and
every restart or deploy resets the data to the seeded demo. The three demo organisations come back because they're in
the image; organisations created later by sign-up are lost. For
persistent data choose the Starter plan and add a **Disk** mounted at `/app/data` (1 GB is plenty): the first boot
copies the seeded demo onto it, later boots keep everything.

## 2. Web app on Vercel (about 5 minutes)

1. Sign in at vercel.com with GitHub. **Add New → Project**, import `ELEVATE-1-0/ELEV01`.
2. **Root Directory: `web`** (important). The framework is detected as Next.js; keep the default build settings.
3. **Environment Variables** (replace the host with your Render URL):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<service>.onrender.com` |
   | `NEXT_PUBLIC_MCP_URL` | `https://<service>.onrender.com/mcp` |
   | `NEXT_PUBLIC_MCP_PUBLIC_URL` | `https://<service>.onrender.com` |

4. **Deploy.** These values are built into the app, so after changing them use **Redeploy**.

## 3. Supabase URL settings (2 minutes)

Supabase → **Authentication → URL Configuration**:

- **Site URL:** `https://<project>.vercel.app`
- **Redirect URLs:** add `https://<project>.vercel.app/**` (keep `http://localhost:3100/**` for local work)

## 4. Check it

- Open `https://<project>.vercel.app`: the landing page. **Get started** → sign up → create an organisation.
- **Sign in with an access token** → pick a demo persona (or paste a token from the build log).
- MCP from your machine: `python scripts/mcp_check.py https://<service>.onrender.com/mcp` (needs `identities.json` with
  the deployed tokens, or just try the in-app **Connect an agent** page).
- Claude.ai and ChatGPT connectors can now use `https://<service>.onrender.com/c/<token>/mcp` directly.

## Run the same image anywhere else (Voroa or any Linux box)

```bash
docker build -t auditpilot .
docker run -p 10000:10000 -e OPENAI_API_KEY=... -e SUPABASE_ANON_KEY=... -v auditpilot-data:/app/data auditpilot
```

The API and MCP server answer on port 10000 (`/api/...`, `/mcp`). For the old three-port layout (MCP :8000, Streamlit
:8501, API :8001) run the image with `sh scripts/start.sh`.

## Notes

- `PUBLIC_HOST` is set automatically on Render (from `RENDER_EXTERNAL_HOSTNAME`); elsewhere set it to the public host
  name or the MCP server answers **421 Invalid Host header**.
- **Secrets** (`OPENAI_API_KEY`, `PORTAL_SECRET`) live in the platform's settings, never in git. The Supabase anon key
  is public by design; never put the service-role key anywhere.
- **Health check:** `GET /api/health` (200). `POST /mcp` without a token answers 401, which also proves MCP is up.
- **Never** give the `ptn_` partner token to an agent; the MCP server refuses it anyway.
