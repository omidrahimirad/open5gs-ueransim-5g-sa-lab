# Real-Run Evidence Guide

Use this guide when validating the lab on Ubuntu. Until this evidence exists, the project should be described as configuration/parser validated with sample logs, not as fully executed.

## Recommended Host

- Ubuntu 22.04 or 24.04 LTS, bare metal or VM.
- Docker Engine 22+ and Docker Compose v2.
- Python 3.11+.
- `uv`.
- Kernel SCTP support.
- `/dev/net/tun` available.

## Pre-Run Folder

Create one evidence folder per real run:

```bash
RUN_ID="$(date -u +%Y%m%d)"
mkdir -p "evidence/real_run_${RUN_ID}"/{screenshots,logs,outputs,reports}
```

Commit the curated evidence folder only after removing secrets, huge logs, packet captures with sensitive data, and duplicate raw output. Keep large PCAPs or long raw logs outside git unless they are explicitly sanitized and small.

## Host Baseline Commands

Save these outputs:

```bash
uname -a | tee "evidence/real_run_${RUN_ID}/outputs/uname.txt"
uv --version | tee "evidence/real_run_${RUN_ID}/outputs/uv_version.txt"
docker version | tee "evidence/real_run_${RUN_ID}/outputs/docker_version.txt"
docker compose version | tee "evidence/real_run_${RUN_ID}/outputs/docker_compose_version.txt"
ls -l /dev/net/tun | tee "evidence/real_run_${RUN_ID}/outputs/tun_device.txt"
sudo modprobe sctp || true
lsmod | grep sctp | tee "evidence/real_run_${RUN_ID}/outputs/sctp_module.txt"
```

Screenshot to capture:

- Terminal showing host OS, Docker versions, `/dev/net/tun`, and SCTP module check.

## Start And Provision

```bash
chmod +x scripts/*.sh scripts/parse_attach_logs.py
./scripts/start_lab.sh | tee "evidence/real_run_${RUN_ID}/outputs/start_lab.txt"
docker compose ps | tee "evidence/real_run_${RUN_ID}/outputs/compose_ps_core.txt"
./scripts/add_subscriber.sh | tee "evidence/real_run_${RUN_ID}/outputs/add_subscriber.txt"
docker compose --profile ran up -d gnb ue
docker compose ps | tee "evidence/real_run_${RUN_ID}/outputs/compose_ps_all.txt"
```

Screenshot to capture:

- `docker compose ps` showing MongoDB, NRF, AMF, SMF, UPF, gNB, and UE containers.

## Runtime Logs

Collect logs after the UE has attempted registration:

```bash
./scripts/collect_logs.sh | tee "evidence/real_run_${RUN_ID}/outputs/collect_logs.txt"
LATEST_LOG_DIR="$(find logs -maxdepth 1 -type d -name '20*T*Z' | sort | tail -n 1)"
cp -R "${LATEST_LOG_DIR}" "evidence/real_run_${RUN_ID}/logs/"
```

Minimum log evidence:

- AMF log showing NG setup, registration request, authentication/security, and registration accept/complete.
- SMF log showing PDU session request and accept or a clear reject reason.
- gNB log showing SCTP/NG setup.
- UE log showing registration and tunnel/interface state.
- UPF log showing PFCP/session activity if available.

## Parser Evidence

```bash
uv run python scripts/parse_attach_logs.py \
  "evidence/real_run_${RUN_ID}"/logs/*/{ue,gnb,amf,smf,upf}.log \
  -o "evidence/real_run_${RUN_ID}/outputs/parsed_attach_events.csv" \
  | tee "evidence/real_run_${RUN_ID}/outputs/parser_summary.txt"

uv run python scripts/parse_attach_logs.py \
  "evidence/real_run_${RUN_ID}"/logs/*/{ue,gnb,amf,smf,upf}.log \
  --json \
  -o "evidence/real_run_${RUN_ID}/outputs/parsed_attach_events.json"
```

If shell brace expansion does not find files, pass the exact log paths from the timestamped log directory.

Paste into reports:

- Parser summary.
- Missing events list, if any.
- Registration duration.
- PDU session establishment duration.
- Any warnings/errors or unclassified relevant lines that need manual explanation.

## Traffic Evidence

```bash
./scripts/traffic_test.sh | tee "evidence/real_run_${RUN_ID}/outputs/traffic_test_console.txt"
cp logs/traffic_test_result.txt "evidence/real_run_${RUN_ID}/outputs/traffic_test_result.txt"
docker compose exec -T ue ip addr | tee "evidence/real_run_${RUN_ID}/outputs/ue_ip_addr.txt"
docker compose exec -T ue ip route | tee "evidence/real_run_${RUN_ID}/outputs/ue_ip_route.txt"
```

Screenshot to capture:

- UE tunnel interface output.
- Successful ping summary, or failure output with troubleshooting notes.

## Notebook And Reports

Copy or generate parser output at `logs/parsed_attach_events.csv`, then open:

```bash
cp "evidence/real_run_${RUN_ID}/outputs/parsed_attach_events.csv" logs/parsed_attach_events.csv
uv run jupyter lab notebooks/session_establishment_analysis.ipynb
```

Update:

- `reports/latency_report.md` with real ping results.
- `reports/session_establishment_analysis.md` with real parser timings.
- `README.md` Validation Status only after evidence is complete.

## What To Commit

Commit:

- Curated evidence summary files under `evidence/real_run_YYYYMMDD/outputs/`.
- Small sanitized logs needed to prove registration/PDU session behavior.
- Screenshots that are not sensitive and are reasonably sized.
- Updated reports and README validation status.

Do not commit:

- Huge raw logs.
- Private credentials, tokens, real SIM credentials, customer data, or private IP topology that should not be public.
- Unsanitized packet captures.
- Duplicate generated files that do not add evidence.

## Minimum Evidence Before Calling The Lab Validated

- `docker compose ps` showing all required services running.
- gNB NG setup evidence.
- UE registration accept/complete evidence.
- Authentication/security mode evidence.
- PDU session accept evidence or a clearly documented failure reason.
- UE tunnel/interface output.
- Traffic test result or a documented UPF/N6 limitation.
- Parser CSV/JSON and summary generated from real logs.
- Updated latency/session reports with real-run date and host details.
