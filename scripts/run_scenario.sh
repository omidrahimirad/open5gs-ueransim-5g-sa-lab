#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SCENARIO="${SCENARIO:-${1:-baseline_e2e}}"
uv run 5g-lab scenario run "$SCENARIO"
