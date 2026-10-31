#!/usr/bin/env bash
set -Eeuo pipefail

alembic upgrade head

if [[ "${SEED_DEMO_DATA:-false}" == "true" ]]; then
  python seed.py
fi

process_pids=()

if [[ "${DOCUMENT_MALWARE_SCAN_ENABLED:-false}" == "true" ]]; then
  freshclam --stdout
  clamd --foreground=true &
  scanner_pid=$!
  process_pids+=("$scanner_pid")

  python - <<'PY'
import socket
import time

for attempt in range(30):
    try:
        with socket.create_connection(("127.0.0.1", 3310), timeout=2) as connection:
            connection.sendall(b"zPING\0")
            if connection.recv(4096).decode(errors="replace").strip("\0\n") == "PONG":
                break
    except OSError:
        pass
    time.sleep(1)
else:
    raise RuntimeError("ClamAV did not become ready within 30 seconds")
PY
fi

celery -A app.workers.celery_app.celery worker \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --concurrency="${CELERY_WORKER_CONCURRENCY:-2}" &
worker_pid=$!
process_pids+=("$worker_pid")

celery -A app.workers.celery_app.celery beat \
  --loglevel="${CELERY_LOG_LEVEL:-info}" &
beat_pid=$!
process_pids+=("$beat_pid")

uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" &
api_pid=$!
process_pids+=("$api_pid")

shutdown() {
  kill "${process_pids[@]}" 2>/dev/null || true
  wait "${process_pids[@]}" 2>/dev/null || true
}

trap shutdown EXIT INT TERM
wait -n "${process_pids[@]}"
