#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

printf '[%s] Stopping 5G SA lab containers.\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker compose --profile ran --profile tools down

cat <<'MSG'

Persistent MongoDB data is kept in the named Docker volume mongodb-data.
To remove it after exporting evidence, run:
  docker volume rm open5gs-ueransim-5g-sa-lab_mongodb-data
MSG
