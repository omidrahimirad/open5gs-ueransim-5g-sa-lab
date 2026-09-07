#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CAPTURE_DIR="${CAPTURE_DIR:-$ROOT_DIR/evidence/capture_staging}"
PID_FILE="$CAPTURE_DIR/tcpdump.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "ERROR: no capture PID file found under $CAPTURE_DIR." >&2
  exit 1
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  wait "$PID" 2>/dev/null || true
fi

rm -f "$PID_FILE"
echo "Capture stopped. Review $CAPTURE_DIR before moving curated evidence into evidence/real_runs/."
