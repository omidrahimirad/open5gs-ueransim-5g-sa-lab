# Setup Guide

This guide assumes an Ubuntu host or VM. Docker Desktop on macOS can be used for reading/editing the project, but SCTP and TUN behavior should be validated on Linux.

## Prerequisites

- Ubuntu 22.04 or 24.04 LTS
- Docker Engine 22+ and Docker Compose v2
- Python 3.11+
- `uv`
- Linux SCTP support
- `/dev/net/tun`
- Optional: JupyterLab for notebook execution

## Host Checks

```bash
uname -a
uv --version
docker version
docker compose version
ls -l /dev/net/tun
sudo modprobe sctp || true
```

## Development Setup

```bash
uv sync
make check
```

Raw quality commands:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts tests
uv run pytest -m "not runtime" -v
uv run pre-commit run --all-files
```

## Start Core

```bash
./scripts/start_lab.sh
docker compose ps
docker compose logs -f nrf ausf udm udr amf smf upf
```

## Provision Subscriber

```bash
./scripts/add_subscriber.sh
```

The helper is pinned and uses `open5gs-dbctl add_ue_with_slice <imsi> <key> <opc> <apn> <sst> <sd>`.

## Start gNB and UE

```bash
docker compose --profile ran up -d gnb ue
docker compose logs -f gnb ue amf smf
```

## Validate

```bash
./scripts/traffic_test.sh
./scripts/collect_logs.sh
uv run python scripts/parse_attach_logs.py logs/*sample.txt -o logs/parsed_attach_events.csv
```

For a real run, parse timestamped logs from `logs/<timestamp>/`.
Follow `docs/real_run_evidence_guide.md` before updating reports or claiming runtime validation.

Scenario tooling:

```bash
make validate-config
make scenario-list
make scenario-validate
make baseline-test
```

## Stop

```bash
./scripts/stop_lab.sh
```
