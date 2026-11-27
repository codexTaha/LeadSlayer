#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "❌ Missing .env file at $ROOT_DIR/.env"
  echo "   Copy .env.example to .env and add your GEMINI_API_KEY."
  exit 1
fi

set -a
source "$ROOT_DIR/.env"
set +a

if [[ -z "${GEMINI_API_KEY:-}" || "${GEMINI_API_KEY}" == "your_gemini_api_key_here" ]]; then
  echo "❌ GEMINI_API_KEY is not configured in $ROOT_DIR/.env"
  exit 1
fi

if [[ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]]; then
  echo "❌ Backend virtualenv not found at $BACKEND_DIR/.venv"
  exit 1
fi

BACK_PID=""
FRONT_PID=""

cleanup() {
  echo ""
  echo "Shutting down LeadSlayer AI servers..."
  if [[ -n "$FRONT_PID" ]]; then
    pkill -P "$FRONT_PID" 2>/dev/null || true
    kill "$FRONT_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACK_PID" ]]; then
    pkill -P "$BACK_PID" 2>/dev/null || true
    kill "$BACK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "🚀 Starting FastAPI + ADK 2.0 backend on http://127.0.0.1:8000 ..."
(
  cd "$BACKEND_DIR"
  exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
BACK_PID=$!

echo "⏳ Waiting for /api/health..."
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "❌ Backend failed health check on port 8000."
  exit 1
fi
echo "✅ Backend healthy!"

echo "🎨 Starting Next.js Command Center on http://localhost:3000 ..."
(
  cd "$FRONTEND_DIR"
  if [[ -d ".next" && -x "node_modules/.bin/next" ]]; then
    exec node_modules/.bin/next start -p 3000
  else
    exec npm run dev
  fi
) &
FRONT_PID=$!

sleep 2
echo ""
echo "================================================================"
echo "  LeadSlayer AI — Autonomous GTM Command Center Ready"
echo "================================================================"
echo "  Command Center UI : http://localhost:3000"
echo "  Safe Replay Mode  : http://localhost:3000/?mode=replay"
echo "  Backend API Docs  : http://127.0.0.1:8000/docs"
echo "  Press Ctrl+C to stop both servers cleanly."
echo "================================================================"
echo ""

wait
