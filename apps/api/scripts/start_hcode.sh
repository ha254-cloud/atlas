#!/usr/bin/env bash
set -Eeuo pipefail

alembic upgrade head

if [[ "${SEED_DEMO_DATA:-false}" == "true" ]]; then
  python seed.py
fi

celery -A app.workers.celery_app.celery worker \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --concurrency="${CELERY_WORKER_CONCURRENCY:-2}" &
worker_pid=$!

celery -A app.workers.celery_app.celery beat \
  --loglevel="${CELERY_LOG_LEVEL:-info}" &
beat_pid=$!

uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" &
api_pid=$!

shutdown() {
  kill "$api_pid" "$worker_pid" "$beat_pid" 2>/dev/null || true
  wait "$api_pid" "$worker_pid" "$beat_pid" 2>/dev/null || true
}

trap shutdown EXIT INT TERM
wait -n "$api_pid" "$worker_pid" "$beat_pid"
