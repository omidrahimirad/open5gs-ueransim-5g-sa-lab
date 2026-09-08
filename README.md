# 5G SA System Integration & Failure-Injection Validation Lab

![Python](https://img.shields.io/badge/Python-3.11+-3776AB)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Open5GS](https://img.shields.io/badge/Open5GS-2.8.0-2E7D32)
![UERANSIM](https://img.shields.io/badge/UERANSIM-3.3.0-F57C00)
![Status](https://img.shields.io/badge/Status-static%20%2B%20fixture%20validated%20%7C%20runtime%20pending-yellow)

Open5GS + UERANSIM lab for 5G SA system integration, deterministic configuration checks, protocol-aware evidence extraction, failure injection, and recovery validation.

This repository is a telecom validation project, not an AI demo and not a production network claim. It models a one-UE 5G SA lab with the 5GC functions required by the selected Open5GS 2.8.0 flow: NRF, AMF, AUSF, UDM, UDR, PCF, SMF, UPF, MongoDB, UERANSIM gNB/UE, and an internal DN test target.

Current claim level: **STATIC + FIXTURE VALIDATED / REAL LINUX RUNTIME PENDING**. Sample logs prove the parser and reports; they do not prove that this host completed real UE registration or PDU session establishment.

## Why It Exists

This lab is designed for portfolio review by telecom hiring managers evaluating candidates for:

- 5G/RAN Engineer
- 5G Core / Lab Engineer
- RF & Wireless Test Engineer
- Telecom Systems Engineer
- Network Integration Engineer
- Technical Support Engineer for wireless systems

It demonstrates the engineering loop a validation engineer is expected to own: check the configuration, start the system, prove baseline behavior, inject a scoped fault, capture evidence, verify recovery, and report exactly what was observed.

## Architecture

![5G SA lab architecture](diagrams/5g_sa_lab_architecture.svg)

Mermaid source: [diagrams/5g_sa_lab_architecture.md](diagrams/5g_sa_lab_architecture.md)

| Area | Components | Interfaces |
| --- | --- | --- |
| RAN/UE simulation | UERANSIM UE, UERANSIM gNB | N1 NAS via gNB, N2 NGAP/SCTP, N3 GTP-U |
| 5G Core control plane | NRF, AMF, AUSF, UDM, UDR, PCF, SMF | SBI, policy control, N11-style AMF/SMF service interaction |
| User plane | UPF, internal DN server | N4 PFCP, N6 data-network path |
| Evidence tooling | parser, scenarios, assertions, reports | logs, optional pcap metadata, JSON/Markdown results |

PCF is included because Open5GS 2.8.0 invokes AM and SM policy-control services during the selected registration/session paths. NSSF is intentionally omitted: the SMF advertises this lab's exact S-NSSAI and DNN to NRF, so AMF can select it directly; the validator fails if that direct-selection contract drifts. This is a version-specific topology decision, not a general claim that NSSF is unnecessary.

## Validation Layers

| Claim level | What it means | Current status |
| --- | --- | --- |
| STATIC VERIFIED | Compose renders, YAML/config consistency passes, scenario schemas validate, scripts parse. | Implemented |
| FIXTURE VERIFIED | Parser, scenario assertions, reporting, and safety logic pass using sample/synthetic evidence. | Implemented |
| RUNTIME VERIFIED | Real Open5GS/UERANSIM execution on Linux proves NG setup, registration, PDU session, UE tunnel, traffic, fault impact, and recovery. | Pending |

CI intentionally covers static and fixture validation only. It does not claim real 5G runtime success.

## Scenario Matrix

| ID | Fault domain | Expected registration | Expected PDU session | Expected user plane | Recovery expected | Runtime validated |
| --- | --- | --- | --- | --- | --- | --- |
| `baseline_e2e` | Healthy baseline | Accept | Accept | DN traffic succeeds through UE tunnel | N/A | No |
| `invalid_subscriber_key` | Authentication | Reject/fail | Not established | Unavailable | Restore key/OPc and baseline | No |
| `unknown_subscriber` | Subscriber | Reject/fail | Not established | Unavailable | Restore SUPI/DB record and baseline | No |
| `dnn_mismatch` | Session management | May accept | Reject/fail | Unavailable | Restore DNN and baseline | No |
| `snssai_mismatch` | Session management | Evidence-dependent | Reject/fail expected, must be proven | Unavailable | Restore S-NSSAI and baseline | No |
| `amf_restart` | Control plane | Impact/recovery observed | Rechecked after recovery | Rechecked after recovery | AMF restart plus baseline | No |
| `smf_unavailable` | Session management | May remain available | Reject/fail | Unavailable | Start SMF and baseline | No |
| `upf_unavailable` | User plane | May remain available | PFCP/session impact possible | Fails | Start UPF and baseline | No |
| `n2_impairment` | Transport | NGAP/SCTP impact observed | Interpreted after CP state | Interpreted after CP state | Remove scoped impairment and baseline | No |
| `n3_impairment` | Transport | May remain healthy | May remain established | Degrades/fails | Remove scoped impairment and baseline | No |

Fault scenarios are gated by `baseline_e2e`: a broken baseline blocks fault interpretation. The baseline result is accepted only when its commit, configuration hashes, resolved image values, and host/runtime identity match the current run.

## Quick Start

For static and fixture checks on any development host:

```bash
uv sync
make check
```

For a real runtime attempt, use Ubuntu/Linux with Docker Engine, SCTP, `/dev/net/tun`, and container networking privileges:

```bash
make preflight
make validate-config
make lab-up
make subscriber-add
docker compose --profile ran up -d gnb ue
./scripts/traffic_test.sh
make collect-evidence
```

Run the scenario control surface:

```bash
uv run 5g-lab scenario list
uv run 5g-lab scenario validate
uv run 5g-lab scenario run baseline_e2e
uv run 5g-lab scenario run upf_unavailable --baseline-result reports/runtime/<baseline_run>/scenario_result.json
```

On macOS/Docker Desktop, runtime scenarios are expected to be blocked or incomplete because SCTP and TUN behavior are host dependent.

## Engineering Workflow

```bash
make validate-config      # deterministic cross-file config checks
make preflight            # Linux host capability checks, no host mutation
make lab-up               # start core NFs and internal DN target
make subscriber-add       # idempotent subscriber provisioning path via pinned dbctl helper
make baseline-test        # run baseline scenario control surface
make scenario SCENARIO=upf_unavailable
make collect-evidence
make lab-down
```

Parser compatibility remains:

```bash
uv run python scripts/parse_attach_logs.py logs/*sample.txt -o /tmp/parsed_attach_events.csv
uv run python scripts/parse_attach_logs.py logs/*sample.txt -o /tmp/parsed_attach_events.json --json
```

## Failure Injection

Failure mechanisms are intentionally small and scoped:

- Docker Compose `restart`, `stop`, and `start` for AMF, SMF, UPF, gNB, and UE only.
- `tc flower` egress drops only inside the gNB container: SCTP/38412 to AMF for N2, and UDP/2152 to UPF for N3.
- Subscriber/key/DNN/S-NSSAI mutations are modeled as controlled lab faults, not arbitrary YAML execution.
- Every runtime fault must implement apply, verify, remove, and verify-removed behavior.

No scenario definition can execute arbitrary shell commands.

Runtime mutation faults for subscriber key, unknown subscriber, DNN mismatch, and S-NSSAI mismatch are defined and assertion-tested, but intentionally not automated yet because they modify subscriber/config state. Component and transport fault hooks use bounded Docker/`tc` operations, inspect real state after apply/removal, and require full post-rollback baseline recovery.

Runtime scenario exit codes are automation-safe: `PASS=0`, `FAIL=1`, `BLOCKED=2`, `ERROR=3`, and `SKIPPED=4`. A blocked Linux runtime attempt therefore cannot make `make baseline-test` appear successful.

## Evidence

Sample logs live under [logs](logs/) and are labeled sample. Real Linux runtime evidence must go under `evidence/real_runs/<run_id>/` or a dated real-run folder after sanitization.

Minimum real runtime evidence before changing this project status:

- environment/version manifest
- `docker compose ps`
- NG setup evidence
- UE registration/authentication/security evidence
- PDU session evidence
- UE tunnel and route evidence
- interface-bound DN traffic result
- parser CSV/JSON from real logs
- scenario JSON/Markdown result
- baseline runtime-context fingerprint
- recovery evidence for any claimed fault scenario

## CI vs Runtime

CI proves:

- Docker Compose renders
- shell scripts parse
- config validator passes
- scenario schemas validate
- Ruff lint and format checks pass
- MyPy passes for `src`, `scripts`, and `tests`
- pytest passes for deterministic non-runtime tests
- sample logs parse to CSV/JSON
- notebook JSON remains valid

CI does **not** prove real UE registration, PDU session establishment, SCTP behavior, TUN creation, GTP-U forwarding, or recovery.

## Skills Demonstrated

- 5G SA registration, authentication, PDU session, and user-plane validation flow
- AMF/AUSF/UDM/UDR/PCF/SMF/UPF role separation
- N2 NGAP/SCTP, N3 GTP-U, N4 PFCP, N6 routing, and SBI awareness
- Linux networking preflight and Docker Compose orchestration
- Deterministic scenario modeling and expected-vs-observed assertions
- Scoped failure injection with rollback discipline
- Python log parsing, fixture testing, and evidence reporting
- Honest technical documentation with clear claim boundaries

## Limitations

- UERANSIM is not RF validation and does not model real radio propagation.
- This is an open-source lab, not a commercial operator network or SLA claim.
- Runtime behavior depends on Linux kernel, SCTP, TUN, Docker privileges, and bridge routing.
- The current repository has no live operator validation and no real Linux runtime evidence committed.
- Packet capture support is a workflow hook; protocol decoding depends on real captures and optional `tshark`.
- Lab subscriber credentials are intentionally public demo values, not real SIM material.

## Repository Structure

```text
configs/        Open5GS, UERANSIM, and subscriber config
diagrams/       Architecture diagram source and SVG
docs/           Engineering workflow, protocol, runtime, and safety documentation
evidence/       Placeholder and rules for real Linux runtime evidence
logs/           Sample logs only
reports/        Sample/generated reports and future runtime summaries
scenarios/      Declarative validation and failure-injection scenarios
scripts/        Thin operational wrappers
src/fiveg_lab/  Deterministic validator/parser/scenario/fault tooling
tests/          Unit and fixture tests; runtime tests are opt-in only
```

## Next Step: Linux Runtime Evidence

Run and capture `baseline_e2e` on a real Ubuntu/Linux environment, then add curated evidence under `evidence/real_runs/<run_id>/`. Until that exists, keep the public status as **STATIC + FIXTURE VALIDATED / REAL LINUX RUNTIME PENDING**.

## References

- [Open5GS documentation](https://open5gs.org/open5gs/docs/)
- [Open5GS source](https://github.com/open5gs/open5gs)
- [UERANSIM source](https://github.com/aligungr/UERANSIM)
- [Gradiant Open5GS/UERANSIM chart demo](https://gradiant.github.io/5g-charts/open5gs-ueransim-gnb.html)

## License

This project is released under the [MIT License](LICENSE).
