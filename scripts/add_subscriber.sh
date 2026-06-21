#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMSI="${IMSI:-001010000000001}"
KEY="${KEY:-465B5CE8B199B49FAA5F0A2EE238A6BC}"
OPC="${OPC:-E8ED289DEBA952E4283B54E88E6183CA}"
AMF="${AMF:-8000}"
DNN="${DNN:-internet}"
SST="${SST:-1}"
SD="${SD:-000001}"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

cat <<MSG
Subscriber to provision:
  IMSI/SUPI: imsi-${IMSI}
  K:         ${KEY}
  OPc:       ${OPC}
  AMF:       ${AMF}
  DNN:       ${DNN}
  S-NSSAI:   SST=${SST}, SD=${SD}

MSG

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required." >&2
  exit 1
fi

if ! docker compose ps mongodb --format '{{.State}}' 2>/dev/null | grep -qi running; then
  echo "ERROR: MongoDB is not running. Run ./scripts/start_lab.sh first." >&2
  exit 1
fi

log "Trying gradiant/open5gs-dbctl helper. This command is image/version dependent."
set +e
docker compose --profile tools up -d open5gs-dbctl >/dev/null 2>&1
docker compose exec -T open5gs-dbctl sh -lc "command -v open5gs-dbctl >/dev/null 2>&1 && open5gs-dbctl add_ue_with_slice '$IMSI' '$KEY' '$OPC' '$AMF' '$DNN' '$SST' '$SD'"
status=$?
set -e

if [[ "$status" -eq 0 ]]; then
  log "Subscriber add command completed. Verify with AMF/SMF logs after UE attach."
  exit 0
fi

cat <<'MSG'

Automatic subscriber provisioning did not complete. This is common when the
dbctl image command syntax changes between Open5GS packaging variants.

Manual WebUI method:
  1. Start an Open5GS WebUI compatible with your Open5GS version, or use an
     existing WebUI if your container image includes it.
  2. Create a subscriber with:
       IMSI: 001010000000001
       K:    465B5CE8B199B49FAA5F0A2EE238A6BC
       OPc:  E8ED289DEBA952E4283B54E88E6183CA
       AMF:  8000
       DNN:  internet
       Slice: SST 1, SD 000001
  3. Confirm the DNN and slice match configs/ueransim/ue.yaml.

Alternative CLI approach:
  docker compose --profile tools exec open5gs-dbctl sh
  open5gs-dbctl --help

Then adapt the command for the installed helper version.
MSG

exit 2
