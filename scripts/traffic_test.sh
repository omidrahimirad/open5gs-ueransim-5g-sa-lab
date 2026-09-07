#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT="${OUT:-$ROOT_DIR/logs/traffic_test_result.txt}"
TARGET="${TARGET:-10.46.0.100}"
COUNT="${COUNT:-5}"
UE_TUNNEL="${UE_TUNNEL:-uesimtun0}"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

: > "$OUT"
log "Starting UE user-plane traffic test."
log "Target=${TARGET}, Count=${COUNT}, UE_TUNNEL=${UE_TUNNEL}"

if ! command -v docker >/dev/null 2>&1; then
  log "ERROR: docker is required."
  exit 1
fi

if ! docker compose ps ue --format '{{.State}}' 2>/dev/null | grep -qi running; then
  log "ERROR: UERANSIM UE container is not running. Start with: docker compose --profile ran up -d gnb ue"
  exit 1
fi

log "Inspecting UE network interfaces."
docker compose exec -T ue sh -lc "ip addr || true" | tee -a "$OUT"

if ! docker compose exec -T ue sh -lc "ip link show '$UE_TUNNEL'"; then
  log "ERROR: UE tunnel interface not visible. Check UE registration/PDU session logs."
  exit 2
fi

log "Inspecting UE routes."
docker compose exec -T ue sh -lc "ip route || true" | tee -a "$OUT"

if ! docker compose exec -T ue sh -lc "command -v ping >/dev/null 2>&1"; then
  log "ERROR: ping is not installed in the UE image."
  exit 3
fi

log "Running interface-bound ping over UE tunnel."
set +e
docker compose exec -T ue sh -lc "ping -I '$UE_TUNNEL' -c '$COUNT' '$TARGET'" | tee -a "$OUT"
ping_status=${PIPESTATUS[0]}
set -e

if [[ "$ping_status" -ne 0 ]]; then
  log "USER_PLANE_FAILURE: ping failed. Check UPF NAT/forwarding, UE route, and PDU session status."
  exit 4
fi

if docker compose exec -T ue sh -lc "command -v iperf3 >/dev/null 2>&1"; then
  log "iperf3 found. Run manually with an external/server-side iperf3 target when needed."
else
  log "iperf3 not installed in UE image; skipping throughput test."
fi

log "USER_PLANE_SUCCESS: traffic test completed successfully."
