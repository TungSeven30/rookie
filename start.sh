#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
mkdir -p "${RUN_DIR}"

BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_LOG_FILE="${RUN_DIR}/backend.log"
FRONTEND_LOG_FILE="${RUN_DIR}/frontend.log"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VITE_DEMO_API_KEY="${VITE_DEMO_API_KEY:-${DEMO_API_KEY:-}}"

is_running_pid() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

is_running_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "$file")"
  [[ -n "$pid" ]] && is_running_pid "$pid"
}

if is_running_file "$BACKEND_PID_FILE"; then
  echo "Backend already running (pid $(cat "$BACKEND_PID_FILE"))"
else
  (
    cd "$ROOT_DIR" || exit 1
    nohup uv run uvicorn src.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
      >>"$BACKEND_LOG_FILE" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
  )
  echo "Started backend on http://${BACKEND_HOST}:${BACKEND_PORT} (pid $(cat "$BACKEND_PID_FILE"))"
  echo "Backend log: $BACKEND_LOG_FILE"
fi

if is_running_file "$FRONTEND_PID_FILE"; then
  echo "Frontend already running (pid $(cat "$FRONTEND_PID_FILE"))"
else
  (
    cd "$ROOT_DIR/frontend" || exit 1
    if [[ -z "$VITE_DEMO_API_KEY" ]]; then
      nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
        >>"$FRONTEND_LOG_FILE" 2>&1 &
    else
      nohup VITE_DEMO_API_KEY="$VITE_DEMO_API_KEY" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
        >>"$FRONTEND_LOG_FILE" 2>&1 &
    fi
    echo $! > "$FRONTEND_PID_FILE"
  )
  echo "Started frontend on http://${FRONTEND_HOST}:${FRONTEND_PORT} (pid $(cat "$FRONTEND_PID_FILE"))"
  echo "Frontend log: $FRONTEND_LOG_FILE"
fi

echo "Services start request complete."
