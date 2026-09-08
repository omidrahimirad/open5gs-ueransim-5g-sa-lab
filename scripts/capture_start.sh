#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CAPTURE_DIR="${CAPTURE_DIR:-$ROOT_DIR/evidence/capture_staging}"
CAPTURE_IFACE="${CAPTURE_IFACE:-}"
CAPTURE_FILTER="${CAPTURE_FILTER:-sctp port 38412 or udp port 2152 or udp port 8805 or tcp port 7777}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: packet capture workflow is Linux-only for this lab." >&2
  exit 1
fi

if ! command -v tcpdump >/dev/null 2>&1; then
  echo "ERROR: tcpdump is required." >&2
  exit 1
fi

if [[ -z "$CAPTURE_IFACE" ]]; then
  echo "ERROR: set CAPTURE_IFACE to the scoped Docker bridge/interface to capture." >&2
  exit 1
fi

case "$CAPTURE_IFACE" in
  br-*|docker*|open5gs*) ;;
  *)
    echo "ERROR: refusing to capture on unscoped interface '$CAPTURE_IFACE'." >&2
    exit 1
    ;;
esac

mkdir -p "$CAPTURE_DIR/pcap"
PID_FILE="$CAPTURE_DIR/tcpdump.pid"
PCAP_FILE="$CAPTURE_DIR/pcap/combined.pcap"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "ERROR: capture already running with PID $(cat "$PID_FILE")." >&2
  exit 1
fi

tcpdump -i "$CAPTURE_IFACE" -s 0 -w "$PCAP_FILE" "$CAPTURE_FILTER" &
echo "$!" > "$PID_FILE"
echo "Capture started: $PCAP_FILE"
