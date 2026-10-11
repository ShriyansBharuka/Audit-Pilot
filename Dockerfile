# AuditPilot AI backend: REST API + MCP server on one port ($PORT), CPU only. Deploys as-is on Render (render.yaml).
# The Next.js web app (web/) deploys separately (Vercel). For the old multi-port box (MCP :8000, Streamlit :8501,
# API :8001) run this image with:  sh scripts/start.sh
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 PORT=10000
ARG SEED_INVOICES=7000
# Pre-seed the demo company (and tenant 2) into the image, so every start is instant and identical on hosts without a
# persistent disk. The judge card (one token per role) is printed in this build step's log and kept in /app/identities.json.
RUN DATA_DIR=/app/seed-data python -m app.seed --reset --invoices ${SEED_INVOICES} \
 && (DATA_DIR=/app/seed-data python -m app.demo_audit --metrics /app/seed-data/metrics.json || echo "demo audit warm-up failed (non-fatal)") \
 && DATA_DIR=/app/seed-data python -m app.tenants --seed-demo
EXPOSE 10000
CMD ["sh", "scripts/serve.sh"]
