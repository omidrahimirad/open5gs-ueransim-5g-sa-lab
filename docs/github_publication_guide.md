# GitHub Publication Guide

## Repository Description

Open5GS + UERANSIM 5G SA integration lab with pinned Docker runtime, config preflight, scenario assertions, protocol-aware log evidence, failure-injection hooks, and honest Linux runtime evidence workflow.

## Suggested Topics

```text
5g
5g-sa
open5gs
ueransim
5g-core
ran
telecom
system-integration
failure-injection
network-validation
linux-networking
docker-compose
pfcp
gtpu
ngap
sctp
python
pytest
devops
```

## Suggested Pinned-Repo Description

5G SA system-integration validation lab using Open5GS and UERANSIM, with deterministic config checks, scenario assertions, protocol-aware evidence parsing, scoped failure injection, and recovery workflow. Committed Linux evidence validates the one-UE baseline and scoped N3 impairment/recovery; other fault scenarios lack fresh Linux validation.

## Suggested LinkedIn Post

I upgraded my Open5GS + UERANSIM 5G Standalone lab into a system-integration validation project.

The repository now models the Open5GS 2.8.0 functions required for one-UE validation: NRF, AMF, AUSF, UDM, UDR, PCF, BSF, SMF, UPF, MongoDB, UERANSIM gNB/UE, and an internal DN test target. It includes pinned runtime versions, deterministic config checks, Linux preflight, scenario definitions, expected-vs-observed assertions, protocol-aware log parsing, protocol-scoped failure-injection hooks, and a structured evidence/reporting workflow.

Static and fixture checks pass. The [September 13 Linux audit](../evidence/real_runs/20260913_pre_merge_audit/README.md), executed at `daca4542608f0bb20ca01441f5e584ce89890ad1`, records a 25/25 baseline with NG Setup, registration, active IPv4 PDU session, UE tunnel, 5/5 DN replies, and final core/RAN health with zero restarts. A scoped N3 UDP/2152 drop caused 100% loss; verified rollback restored 5/5 replies and passed all 11 recovery checks. Other fault scenarios have not received fresh Linux runtime validation. UERANSIM does not validate RF/OTA behavior or production readiness.

Relevant for 5G Core, RAN integration, telecom systems, wireless test, network integration, and DevOps-oriented lab engineering roles.

Repository: https://github.com/omidrahimirad/open5gs-ueransim-5g-sa-lab

## Suggested CV Bullet

Built a deterministic Open5GS/UERANSIM 5G SA system-integration lab with pinned Docker runtime, 5GC/RAN configuration validation, Linux preflight, protocol-aware log parsing, scenario assertions, scoped failure-injection hooks, and evidence-based recovery reporting; validated the one-UE Linux baseline (25/25 assertions) and scoped N3 impairment/recovery, with committed evidence and explicit limits on untested scenarios.

## Suggested Commit Sequence

```text
chore: pin reproducible 5g lab runtime
feat: complete 5g core integration architecture
feat: add configuration and linux preflight validation
feat: add deterministic validation scenario framework
feat: add protocol evidence collection and assertions
feat: add failure injection and recovery checks
test: add validation and safety coverage
docs: document 5g sa system validation workflow
```

## Suggested Branch And Push Commands

```bash
git checkout main
git pull origin main
git checkout -b feat/v2-system-integration-validation
git add .
git commit -m "feat: add 5g sa system validation framework"
git push -u origin feat/v2-system-integration-validation
```

Open a pull request and do not merge until CI is green and the diff has been reviewed.

## Local Quality Gate Before Publication

```bash
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts tests
uv run pytest -m "not runtime" -v
uv run pre-commit run --all-files
docker compose config
make check
```

## Evidence-Based Claim Boundaries

The committed [Linux audit evidence](../evidence/real_runs/20260913_pre_merge_audit/README.md) supports the one-UE baseline and N3 fault/recovery at the recorded executing commit. The stale-evidence negative audit correctly returned ERROR when current collection was deliberately unavailable; it is not a successful traffic-failure observation.

Do not extend these results to other fault scenarios, throughput, IPv6 PDU sessions, PCAP-based protocol validation, multi-host/multi-UE operation, the full fault matrix, or long-duration reliability. Do not claim RF/OTA validation, carrier-grade behavior, or production readiness. Docker Desktop and sample logs do not prove Linux SCTP/TUN/user-plane behavior.
