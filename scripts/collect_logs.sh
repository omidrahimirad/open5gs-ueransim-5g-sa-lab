#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/runtime/logs/$TS}"
mkdir -p "$OUT_DIR"
mkdir -p "$OUT_DIR/nf-files"

services=(log-init ue gnb amf ausf udm udr pcf smf upf nrf mongodb dn-server)
log_options=(--no-color --timestamps)
if [[ -n "${SINCE:-}" ]]; then log_options+=(--since "$SINCE"); fi
collection_failed=0

if ! docker compose ps >/dev/null 2>&1; then
  echo "ERROR: docker compose is not available or this is not the lab directory." >&2
  exit 1
fi

for svc in "${services[@]}"; do
  if docker compose ps --all "$svc" --format '{{.Name}}' 2>/dev/null | grep -q .; then
    if ! docker compose logs "${log_options[@]}" "$svc" > "$OUT_DIR/${svc}.log"; then
      collection_failed=1
    fi
  else
    printf '[%s] Service %s not created; skipping.\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$svc" | tee "$OUT_DIR/${svc}.missing"
  fi
done

# Persistent application files can contain earlier attempts; export them only
# for diagnosis, separately from the stdout used for automated parser events.
for svc in nrf ausf udm udr pcf amf smf upf; do
  if ! docker compose exec -T "$svc" cat "/var/log/open5gs/$svc.log" \
      > "$OUT_DIR/nf-files/$svc.log" 2> "$OUT_DIR/nf-files/$svc.error"; then
    echo "WARNING: unable to export $svc file log; see nf-files/$svc.error" >&2
  else
    rm "$OUT_DIR/nf-files/$svc.error"
  fi
done

docker compose ps > "$OUT_DIR/docker_compose_ps.txt" || true
docker version > "$OUT_DIR/docker_version.txt" 2>&1 || true
docker compose version > "$OUT_DIR/docker_compose_version.txt" 2>&1 || true

printf 'Collected logs under %s\n' "$OUT_DIR"
exit "$collection_failed"
