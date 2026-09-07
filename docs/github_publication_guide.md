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

5G SA system-integration validation lab using Open5GS and UERANSIM, with deterministic config checks, scenario assertions, protocol-aware evidence parsing, scoped failure injection, and recovery workflow. Runtime evidence is pending a real Linux run.

## Suggested LinkedIn Post

I upgraded my Open5GS + UERANSIM 5G Standalone lab into a system-integration validation project.

The repository now models a complete minimum 5GC lab architecture for one-UE validation: NRF, AMF, AUSF, UDM, UDR, SMF, UPF, MongoDB, UERANSIM gNB/UE, and an internal DN test target. It includes pinned runtime versions, deterministic config checks, Linux preflight, scenario definitions, expected-vs-observed assertions, protocol-aware log parsing, scoped failure-injection hooks, and a structured evidence/reporting workflow.

Current status is intentionally honest: static and fixture validation are implemented; real Linux runtime evidence is still pending and will only be claimed after actual Ubuntu execution proves NG setup, registration, PDU session, UE tunnel, DN traffic, and recovery behavior.

Relevant for 5G Core, RAN integration, telecom systems, wireless test, network integration, and DevOps-oriented lab engineering roles.

Repository: https://github.com/omidrahimirad/open5gs-ueransim-5g-sa-lab

## Suggested CV Bullet

Built a deterministic Open5GS/UERANSIM 5G SA system-integration lab with pinned Docker runtime, 5GC/RAN configuration validation, Linux preflight, protocol-aware log parsing, scenario assertions, scoped failure-injection hooks, and evidence-based recovery reporting; current status: static + fixture validated, Linux runtime evidence pending.

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

## Do Not Claim Before Real Linux Validation

Do not claim:

- runtime validated
- full E2E execution succeeded
- UE registration succeeded from real logs
- PDU session establishment succeeded from real logs
- packet captures prove NGAP/PFCP/GTP-U behavior
- recovery times or latency values were measured
- Docker Desktop validates SCTP/TUN/user-plane behavior
- UERANSIM represents RF or commercial RAN performance

Safe wording before real evidence:

- "Static and fixture validation are implemented."
- "Real Linux runtime validation is pending."
- "Designed for Ubuntu/Linux execution with SCTP and TUN support."
- "Sample logs demonstrate parser behavior only."
