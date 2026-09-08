# Runtime validation attempt: blocked at host preflight

**PROJECT NOT YET COMPLETE. No Open5GS/UERANSIM runtime scenario was executed.**

On 2026-09-08, the unmodified merged system failed host preflight on macOS.
Runtime execution stopped before lab startup, provisioning, traffic, or fault
injection. The static and fixture checks passed. This report records that
blocked attempt; it is not real Linux runtime evidence.

## A. Environment and starting state

Latest `main` was checked out and updated with `git pull --ff-only` before
creating `feat/runtime-validation-evidence`.

| Field | Observed value |
| --- | --- |
| Validated source commit | `d4227a44e68457e5e6ad510dbd9e9896728aeb8f` |
| Attempt host OS | macOS 27.0, build 26A5425a |
| Kernel / architecture | Darwin 27.0.0 / arm64 |
| Docker client | 29.4.3, context `desktop-linux` |
| Docker Engine | Unreachable; Docker Desktop socket missing |
| Compose | v5.1.4 |
| Shell Python / project Python | 3.12.10 / 3.11.15 |
| uv | 0.11.16 |

`make preflight` failed (make exit code 2; underlying check exit code 1):

- Host is Darwin rather than Linux.
- `ip` / iproute2 is missing.
- `/dev/net/tun` is missing.
- Linux SCTP support is unavailable.

The preflight additionally reported missing `ss`, `tc`, and `tshark`, and an
unavailable Linux forwarding sysctl. `docker version` and `docker info` separately
confirmed the daemon was unreachable. Container NET_ADMIN permissions, UERANSIM
TUN privileges, and Docker bridge operation were **not verified**. Merely finding
the Docker client and Compose CLI does not establish those capabilities.

See [preflight output](preflight.txt), [command records](commands.json), and
[manifest](manifest.json). The manifest records configuration hashes and the
original scenario matrix. Command records retain exact arguments, UTC start
times, exit codes, and sanitized stdout/stderr, including failed host probes.

Resolved Compose image tags (including `ran` and `tools` profiles):

| Component | Configured tag |
| --- | --- |
| Open5GS | `gradiant/open5gs:2.8.0` |
| UERANSIM | `gradiant/ueransim:3.3.0` |
| MongoDB | `mongo:8.3.8-noble` |
| dbctl | `gradiant/open5gs-dbctl:0.10.3` |
| DN target | `busybox:1.37.0` |

These are configuration-resolved tags, not inspected image digests or proof of
image availability, startup, or execution. No images were pulled for this attempt.

## B. Baseline

| Required proof | Observed status |
| --- | --- |
| Core: MongoDB, NRF, AUSF, UDM, UDR, PCF, AMF, SMF, UPF, DN | NOT EXECUTED |
| gNB SCTP association / NG Setup / N2 up | NOT EXECUTED |
| UE registration / RM-REGISTERED | NOT EXECUTED |
| Authentication | NOT EXECUTED |
| NAS Security Mode | NOT EXECUTED |
| PDU session / PFCP / PS-ACTIVE | NOT EXECUTED |
| `uesimtun0`, UE IP, and route | NOT EXECUTED |
| Interface-bound traffic to internal DN | NOT EXECUTED |

Baseline status is **BLOCKED BEFORE EXECUTION**, never PASS or a measured runtime
failure. Fault scenarios cannot be interpreted without a healthy baseline.

## C. Runtime defects

No runtime integration defects were discovered because the environment gate
prevented a first real runtime attempt. The observed failure class is
**ENVIRONMENT**. No code/config changes, root-cause claims about Open5GS/UERANSIM,
runtime fixes, or successful runtime retests are reported.

## D. Evidence

At the starting commit, `evidence/` contained only `.gitkeep` and `README.md`.
It remains unchanged. No `evidence/real_runs/` directory or runtime summary was
created, because there are no actual runtime scenario results to summarize.

The committed records in this directory are host-preflight/static records:

- `README.md`: human-readable blocked-attempt report.
- `preflight.txt`: sanitized failed preflight output.
- `commands.json`: captured command outputs and their exit codes.
- `manifest.json`: source/configuration inventory, capability status, check
  results, and the unexecuted scenario matrix.

Local username, home path, repository path, and hostname were replaced with
explicit placeholders. No Docker auth files, SSH material, raw runtime logs,
subscriber key material, or packet captures were collected. This directory is
outside `evidence/`, which the repository reserves for real Linux runtime data.

## E. Runtime scenarios

All ten retain `runtime_validated: false` and README status `No`. Counts:
**0 executed, 0 passed, 0 failed, 10 blocked before execution**. Those ten blocks
are scheduling outcomes from the shared environment gate, not ten scenario runs.

| Scenario | Executed? | Result | Observed impact | Recovery | Runtime evidence |
| --- | --- | --- | --- | --- | --- |
| `baseline_e2e` | No | BLOCKED | None observed | Not executed | None |
| `amf_restart` | No | BLOCKED | None observed | Not executed | None |
| `smf_unavailable` | No | BLOCKED | None observed | Not executed | None |
| `upf_unavailable` | No | BLOCKED | None observed | Not executed | None |
| `n2_impairment` | No | BLOCKED | None observed | Not executed | None |
| `n3_impairment` | No | BLOCKED | None observed | Not executed | None |
| `invalid_subscriber_key` | No | BLOCKED | None observed | Not executed | None |
| `unknown_subscriber` | No | BLOCKED | None observed | Not executed | None |
| `dnn_mismatch` | No | BLOCKED | None observed | Not executed | None |
| `snssai_mismatch` | No | BLOCKED | None observed | Not executed | None |

## F. Protocol evidence

N2/SCTP, N3/GTP-U, N4/PFCP, and SBI: **none captured**. No actual tc rule
installation, traffic isolation, filter removal, or recovery was observed.

## G. Negative scenarios

None of the four subscriber/configuration mutation tests was runtime validated.
The merged implementation explicitly blocks their execution because transactional
mutation is not yet automated. Per the requested ordering, implementation remains
deferred until the baseline and infrastructure fault scenarios work on Linux.

## H. Timing metrics

No real registration, authentication, PDU-session, traffic, or recovery timings
exist. `make check` parses sample logs and prints sample timing values; those
values are retained only within its explicitly classified static/fixture command
record. `duration_seconds` measures command wall time, not a 5G procedure.

## I. Static and fixture checks

All checks below ran on the unmodified source commit above, on macOS.

| Check | Result |
| --- | --- |
| `uv sync --frozen` | PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS, 28 files |
| `uv run mypy src scripts tests` | PASS, 27 source files |
| Non-runtime pytest, verbose, with coverage | 62 passed; 1 runtime test deselected; 63 collected |
| Coverage: `src/fiveg_lab` and `scripts` | 79% (rounded by pytest-cov) |
| `uv run pre-commit run --all-files` | PASS |
| `docker compose config` | PASS (static resolution only) |
| `make validate-config` | PASS |
| `make check` | PASS, including the exact requested non-runtime pytest command |

Coverage and fixture assertions do not prove runtime behavior. The existing
GitHub CI workflow also covers static/fixture checks only.

## J. Fresh clone

A fresh-clone runtime baseline was not attempted. There is no validated Ubuntu
host or successful baseline to reproduce yet.

## K. README status

The root README claim remains exactly:

> STATIC + FIXTURE VALIDATED / REAL LINUX RUNTIME PENDING

No runtime results table, Linux success badge, timing claim, or scenario status
was promoted.

## L. Git

Branch: `feat/runtime-validation-evidence`, based on
`d4227a44e68457e5e6ad510dbd9e9896728aeb8f`. This change contains only this
blocked-attempt report and its captured records. Commit/PR identifiers and CI
outcomes belong to the resulting Git history and PR checks; they are not claims
of Linux runtime success. The PR must remain unmerged during this task.

## M. Limitations and cleanup

UERANSIM is not an RF simulator. This open-source lab is not an operator network;
no production SLA, commercial latency, coverage, or 5G throughput claim is made.

This attempt started no lab containers, applied no tc rules, and changed no
subscriber/config state. No runtime cleanup was needed or invoked. This says
nothing about unrelated workloads on the host, which were not inspected.

## N. Completion verdict

**PROJECT NOT YET COMPLETE**

Remaining blocking step: provide access to a suitable Ubuntu/Linux host that
passes the complete runtime prerequisites, so the requested baseline-first
validation can execute.
