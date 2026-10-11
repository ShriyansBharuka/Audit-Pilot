#!/usr/bin/env sh
# Single-port start for hosts like Render: REST API + MCP server in one process on $PORT (app/serve.py).
# The Docker image carries a pre-seeded demo company in seed-data/ (built at image build time). On a host without a
# persistent disk every start begins from it; with a disk mounted on data/, the first boot copies it there once.
set -e
cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-data}"
export DATA_DIR
if [ ! -f "$DATA_DIR/erp.db" ] && [ -f seed-data/erp.db ]; then
  echo "first boot: copying the pre-seeded demo company into $DATA_DIR"
  mkdir -p "$DATA_DIR"
  cp -R seed-data/. "$DATA_DIR/"
fi
if [ ! -f "$DATA_DIR/erp.db" ]; then
  echo "first boot: seeding the demo company (${SEED_INVOICES:-7000} invoices, a few minutes)"
  python -m app.seed --reset --invoices "${SEED_INVOICES:-7000}"
  python -m app.demo_audit --metrics "$DATA_DIR/metrics.json" || echo "demo audit warm-up failed (non-fatal)"
fi
exec python -m uvicorn app.serve:app --host 0.0.0.0 --port "${PORT:-10000}" --proxy-headers --forwarded-allow-ips="*"
