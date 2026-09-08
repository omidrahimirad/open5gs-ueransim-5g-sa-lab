# Linux Bootstrap Findings

Real Linux runtime validation discovered these defects after static and fixture validation had passed.

## Evidence source and limits

The observations below were supplied by the user from an external Google Compute Engine VM. They were not re-executed by the repository-editing agent. This document records that report; it is not a substitute for original runtime artifacts.

| Reported environment | Value |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS |
| Kernel / architecture | Linux 7.0.0-1011-gcp / x86_64 (amd64) |
| Resources | 4 vCPU, 16 GB RAM |
| Docker / Compose | 29.8.0 / v5.5.1 |
| Host capabilities | `/dev/net/tun` present; SCTP loaded; IP forwarding enabled; `ip`, `tc`, `tcpdump`, and `tshark` available |
| Checks before lab startup | Host preflight and static config validation passed; 62 non-runtime tests passed, one runtime test deselected |

The user identified validated main as `d4227a44e68457e5e6ad510dbd9e9896728aeb8f`. The exact external executing checkout, resolved image digests, original command artifacts, and complete baseline evidence were not supplied. The report therefore supports the specific observations below, not a reproducible full runtime-validation claim.

## MongoDB startup

The pinned `mongo:8.3.8-noble` image reportedly exited with a message identifying an incompatibility with Linux kernel versions 6.19 and newer. An isolated container using the same image with `GLIBC_TUNABLES=glibc.pthread.rseq=1` returned `1` from `db.runCommand({ping:1}).ok` after 10 seconds.

Compose now sets that environment value for MongoDB and retains the pinned image. It is a Linux/kernel compatibility workaround observed on the reported host, not an application-level Open5GS requirement. The isolated ping establishes the reported MongoDB startup result only; startup through the patched Compose service still needs external validation.

## UPF TUN permissions

The user reported `ioctl(TUNSETIFF): Operation not permitted` while UPF attempted to create `ogstun`. The image default user was UID/GID 999 (`open5gs`); an isolated test with `privileged: true` still reported `CapEff: 0000000000000000` and failed the TUN operation.

Explicit root (`0:0`) with the TUN device succeeded in the user's privileged test. A second isolated test with root, `NET_ADMIN`, and `/dev/net/tun`, without privileged mode, created, displayed, and deleted a temporary TUN interface and printed `NET_ADMIN_TUN_PASS`.

Compose now runs UPF as `0:0`, retains `NET_ADMIN` and the TUN device mapping, and removes UPF's `privileged: true`. The tested operation requires effective networking capability inside this image/runtime arrangement; host TUN availability alone did not provide it. The least-privilege test supports removing broad privileged mode for that TUN operation. Full UPF startup, forwarding, and the 5G baseline still need validation using patched Compose.

## Remaining validation

Static contract tests and a mocked runtime-check test suite can prevent configuration and reporting regressions. They cannot reproduce either Linux observation. The explicit container runtime preflight checks temporary UPF TUN creation and cleanup without starting the 5G lab; optional `--mongodb` checks isolated MongoDB startup and ping using its configured image/environment. A successful probe is not a baseline result.

Follow the [runtime validation procedure](runtime_validation.md) on the external host, beginning with Compose teardown and both preflight checks. Capture the environment, versions, exact commit, resolved images, capabilities, commands, logs, and scenario metadata with sanitized evidence. Registration, authentication, security, PDU session establishment, user-plane traffic, protocol captures, fault impact, recovery, and real timing measurements remain unproven by this report.

Current claim level remains **STATIC + FIXTURE VALIDATED / REAL LINUX RUNTIME PENDING**.
