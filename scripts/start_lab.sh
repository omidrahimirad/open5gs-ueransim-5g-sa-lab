#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose v2 is required." >&2
  exit 1
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  log "WARNING: $(uname -s) detected. Open5GS/UERANSIM can start on Docker Desktop, but SCTP and TUN validation should be done on Linux."
fi

if [[ ! -c /dev/net/tun ]]; then
  log "WARNING: /dev/net/tun not found on host. UE/UPF tunnel creation may fail."
fi

if command -v ss >/dev/null 2>&1 && ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -Eq '(:7777|:38412)$'; then
  log "WARNING: TCP port 7777 or SCTP/TCP-visible port 38412 appears in use. Check for local conflicts if containers fail to bind."
fi

log "Starting MongoDB and Open5GS 5GC network functions."
docker compose up -d mongodb nrf amf upf smf

log "Core services requested. Check health/logs with:"
echo "  docker compose ps"
echo "  docker compose logs -f amf smf upf"
echo
log "Provision subscriber before starting RAN/UE:"
echo "  ./scripts/add_subscriber.sh"
echo
log "Then start gNB and UE:"
echo "  docker compose --profile ran up -d gnb ue"
