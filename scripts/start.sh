#!/usr/bin/env sh
# Start AuditPilot on one box (Voroa / any Linux host): MCP server on $PORT (default 8000) + web app on $UI_PORT (8501).
# First boot (no data/erp.db) seeds the demo company; set SEED_INVOICES to change its size (default 7000, ~4 min).
set -e
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"
if [ ! -f data/erp.db ]; then
  echo "first boot: seeding the demo company (${SEED_INVOICES:-7000} invoices)…"
  python -m app.seed --reset --invoices "${SEED_INVOICES:-7000}"
  python -m app.demo_audit --metrics data/metrics.json || echo "demo audit warm-up failed (non-fatal)"
fi
python -m app.mcp_server &
MCP_PID=$!
export MCP_URL="${MCP_URL:-http://127.0.0.1:${PORT}/mcp}"
streamlit run ui/app.py --server.port "$UI_PORT" --server.address 0.0.0.0 --server.headless true &
UI_PID=$!
trap 'kill $MCP_PID $UI_PID 2>/dev/null' INT TERM
wait $MCP_PID $UI_PID
