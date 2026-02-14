#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${ROOT_DIR}/.run"

BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"

terminate_process() {
  local pid_file="$1"
  local label="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "$label not running (no PID file)"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"

  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    echo "$label not running (stale pid file removed)"
    rm -f "$pid_file"
    return
  fi

  echo "Stopping $label (pid $pid)..."
  kill "$pid"

  for _ in {1..15}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  if kill -0 "$pid" 2>/dev/null; then
    echo "$label did not stop, forcing kill"
    kill -9 "$pid" || true
  fi

  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    echo "$label stopped"
  else
    echo "Failed to stop $label (pid $pid)"
    return 1
  fi
}

terminate_process "$BACKEND_PID_FILE" "Backend"
terminate_process "$FRONTEND_PID_FILE" "Frontend"

echo "All services stopped."
