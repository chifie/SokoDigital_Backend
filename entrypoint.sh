#!/bin/bash
# ── Docker entrypoint ─────────────────────────────────────────────────────────
#
# Run database migrations, then start the FastAPI server.
# This script is the ENTRYPOINT of the production Docker image.
#
# Environment variables:
#   RUN_MIGRATIONS  - Set to "true" (default) to run alembic migrations.
#                     Set to "false" to skip and start the server directly.
#   UVICORN_WORKERS - Number of uvicorn workers (default: 4).
#   UVICORN_PORT    - Port to bind (default: 8000).
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
UVICORN_WORKERS="${UVICORN_WORKERS:-4}"
UVICORN_PORT="${UVICORN_PORT:-8000}"

# ── Database migrations ──────────────────────────────────────────────────────
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "⟳ Running database migrations..."
    alembic upgrade head
    echo "✓ Migrations complete."
else
    echo "→ Skipping database migrations (RUN_MIGRATIONS=${RUN_MIGRATIONS})."
fi

# ── Start server ─────────────────────────────────────────────────────────────
echo "⟳ Starting uvicorn on 0.0.0.0:${UVICORN_PORT} with ${UVICORN_WORKERS} workers..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${UVICORN_PORT}" \
    --workers "${UVICORN_WORKERS}" \
    --proxy-headers \
    --forwarded-allow-ips '*'
