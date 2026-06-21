# Setup Guide

This guide assumes an Ubuntu host or VM. Docker Desktop on macOS can be used for reading/editing the project, but SCTP and TUN behavior should be validated on Linux.

## Prerequisites

- Ubuntu 22.04 or 24.04 LTS
- Docker Engine 22+ and Docker Compose v2
- Python 3.10+
- Linux SCTP support
- `/dev/net/tun`
- Optional: JupyterLab for notebook execution

## Host Checks

```bash
uname -a
docker version
docker compose version
ls -l /dev/net/tun
sudo modprobe sctp || true
```

## Start Core

```bash
./scripts/start_lab.sh
docker compose ps
docker compose logs -f amf smf upf
```

## Provision Subscriber

```bash
./scripts/add_subscriber.sh
```

If the dbctl helper syntax differs from your image version, use the manual WebUI method printed by the script.

## Start gNB and UE

```bash
docker compose --profile ran up -d gnb ue
docker compose logs -f gnb ue amf smf
```

## Validate

```bash
./scripts/traffic_test.sh
./scripts/collect_logs.sh
python3 scripts/parse_attach_logs.py logs/*sample.txt -o logs/parsed_attach_events.csv
```

For a real run, parse timestamped logs from `logs/<timestamp>/`.
Follow `docs/real_run_evidence_guide.md` before updating reports or claiming runtime validation.

## Stop

```bash
./scripts/stop_lab.sh
```
