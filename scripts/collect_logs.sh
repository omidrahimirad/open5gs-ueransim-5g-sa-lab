#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$ROOT_DIR/logs/$TS"
mkdir -p "$OUT_DIR"

services=(ue gnb amf smf upf nrf mongodb)

if ! docker compose ps >/dev/null 2>&1; then
  echo "ERROR: docker compose is not available or this is not the lab directory." >&2
  exit 1
fi

for svc in "${services[@]}"; do
  if docker compose ps "$svc" --format '{{.Name}}' 2>/dev/null | grep -q .; then
    docker compose logs --no-color --timestamps "$svc" > "$OUT_DIR/${svc}.log" || true
  else
    printf '[%s] Service %s not created; skipping.\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$svc" | tee "$OUT_DIR/${svc}.missing"
  fi
done

docker compose ps > "$OUT_DIR/docker_compose_ps.txt" || true
docker version > "$OUT_DIR/docker_version.txt" 2>&1 || true
docker compose version > "$OUT_DIR/docker_compose_version.txt" 2>&1 || true

printf 'Collected logs under %s\n' "$OUT_DIR"

