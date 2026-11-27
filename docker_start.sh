#!/usr/bin/env bash
set -euo pipefail

export BACKEND_URL="http://127.0.0.1:8000"
export PYTHONPATH="/app/backend"

# Start single-worker FastAPI + ADK + MCP coordinator on localhost:8000
cd /app/backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Serve Next.js Command Center publicly on Hugging Face's port 7860
cd /app/frontend
exec npx next start -H 0.0.0.0 -p "${PORT:-7860}"
