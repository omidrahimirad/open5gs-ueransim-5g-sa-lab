# Linux Bootstrap Findings

Real Linux runtime validation discovered these defects after static and fixture validation had passed.

## Evidence source and limits

The runtime observations below were supplied by the user from an external Google Compute Engine VM. They were not re-executed by the repository-editing agent. Registry inspection and local static/fixture tests are identified separately. This document is not a substitute for original runtime artifacts.

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

Compose now sets that environment value for MongoDB and retains the pinned image. It is a Linux/kernel compatibility workaround observed on the reported host, not an application-level Open5GS requirement. The subsequent user-supplied report confirms MongoDB also became healthy in the actual Compose lab. A same-host A/B test with `glibc.pthread.rseq=0` exited with the original kernel incompatibility message. Keep `rseq=1`; an informational warning does not supersede these observed outcomes.

## UPF TUN permissions

The user reported `ioctl(TUNSETIFF): Operation not permitted` while UPF attempted to create `ogstun`. The image default user was UID/GID 999 (`open5gs`); an isolated test with `privileged: true` still reported `CapEff: 0000000000000000` and failed the TUN operation.

Explicit root (`0:0`) with the TUN device succeeded in the user's privileged test. A second isolated test with root, `NET_ADMIN`, and `/dev/net/tun`, without privileged mode, created, displayed, and deleted a temporary TUN interface and printed `NET_ADMIN_TUN_PASS`.

Compose now runs UPF as `0:0`, retains `NET_ADMIN` and the TUN device mapping, and removes UPF's `privileged: true`. The tested operation requires effective networking capability inside this image/runtime arrangement; host TUN availability alone did not provide it. The least-privilege test supports removing broad privileged mode for that TUN operation. Full UPF startup, forwarding, and the 5G baseline still need validation using patched Compose.

## Runtime log bind-mount failure

**Supplied external evidence:** AMF reported `FATAL: cannot open log file : /var/log/open5gs/amf.log`. The host `./logs` directory was UID/GID 1001:1002, mode 775; the image ran as 999:999. An isolated container using that same mount failed to create a file with `Permission denied` (exit 1), while the root control created and removed its file and printed `LOG_WRITE_PASS`. The reported lab had MongoDB healthy and NRF up, with the other listed NFs restarting with exit 255.

**Fix awaiting external validation:** all Open5GS NFs mount a Docker-managed `open5gs-logs` volume. A network-isolated, read-only-root-filesystem initializer changes only that volume directory and the eight named NF log files to UID/GID 999:999 (directory 0775, files 0644). It preserves existing log contents and refuses symlinks. Non-UPF NFs explicitly remain UID/GID 999; UPF retains its separately justified root user. Each NF depends on successful initialization. Host checkout ownership is irrelevant because no checkout directory is used as the writable application-log mount. No world-writable directory or recursive host chown is introduced.

Fixtures remain in `logs/` and are never mounted in a container. Mutable exports now go to ignored `runtime/logs/<UTC>/`: Docker stdout at the top level and NF file logs under `nf-files/`. Traffic output goes to `runtime/traffic_test_result.txt`. The canonical runtime parser uses container stdout and never falls back to sample fixtures. Persistent NF file logs can span earlier containers/attempts, so they are diagnostic exports and are excluded from automatic assertions; inspect their timestamps before citing them. Existing legacy exports under `logs/<UTC>/` are preserved but must be moved/recollected explicitly for the new runtime parser.

## UPF entrypoint sysctl failure

**Supplied external evidence:** the old runtime preflight passed its isolated TUN test, but full UPF startup then failed writing `net.ipv6.conf.all.disable_ipv6`. A root + NET_ADMIN container reported effective capabilities `00000000a80435fb`; reading the sysctl returned 0, but rewriting that same value failed with exit 255. TUN creation alone did not cover the pinned entrypoint's bootstrap requirements.

**Independent registry inspection, not execution:** the exact `gradiant/open5gs:2.8.0` image was inspected through registry manifests and its small entrypoint layer. The digest-verified `/entrypoint.sh` creates `ogstun`, assigns IPv4/IPv6 addresses, rewrites IPv6 and IPv4-forwarding sysctls, brings the link up, optionally adds IPv4 masquerading, and delays UPF launch by 10 seconds.

- Index: `sha256:1942954babfe6dd5094c8047d8dec26009c67168471115136cd0195a3dc11187`
- amd64 manifest: `sha256:37fb289ccda10f198cbb4079dac15ab3be17d8bf180e2af5fb5860d6c0557ad9`
- Entrypoint layer: `sha256:f5c76ec2e61800ac130e8c7ffb96230a399e7baad2c886b2d44d89017041d73a`
- Entrypoint file SHA-256: `f77cc3e519958c6d71176f2a433aeda6f48fcddfbc440cbc54c8bafb088ae59c`

**Fix awaiting external validation:** Compose configures namespaced `net.ipv4.ip_forward=1`, `net.ipv6.conf.all.disable_ipv6=0`, and `net.ipv6.conf.default.disable_ipv6=0`. A read-only mounted repository entrypoint verifies these values and the new tunnel's IPv6 state without writing `/proc/sys`. It creates/configures `ogstun`, verifies both addresses and administrative UP state, and installs/verifies the existing optional NAT behavior. Startup retains the image's 10-second delay and executes the actual UPF command.

Compose explicitly sets IPv4 address `10.45.1.1/24` and NAT source `10.45.1.0/24`, matching the configured UE gateway/pool instead of inheriting the image's broader `10.45.0.1/16` / `10.45.0.0/16` defaults. IPv6 address `cafe::1/64` is preserved; this does not add or claim IPv6 PDU-session validation. NAT remains enabled and scoped to the UE pool; the DN return route remains unchanged. UPF retains root + NET_ADMIN + TUN access, without `privileged: true` or broader capabilities. Actual kernel acceptance, NAT operation, full UPF startup, and forwarding remain external checks.

Docker documents [namespaced service sysctls](https://docs.docker.com/reference/compose-file/services/#sysctls) and [volume ownership/persistence](https://docs.docker.com/engine/storage/volumes/). These mechanisms motivate the patch; documentation is not runtime proof.

## Expanded runtime preflight and remaining validation

The explicit runtime preflight prepares the **actual configured lab log volume**, tests temporary file creation/removal for all eight NFs with their effective image/user/mount, then invokes the **same configured UPF entrypoint** with `--check`. That path checks sysctls, IPv4/IPv6 address assignment, link state, NAT installation/verification, and cleanup. The old `NET_ADMIN_TUN_PASS` marker cannot satisfy the new bootstrap check. Optional `--mongodb` still checks the configured image/environment via isolated startup and ping.

Unique probe containers use no lab networks, service dependencies, or subscriber/database volumes. Their interfaces and NAT rules live only in their disposable network namespace. Probe files are removed by a shell trap and a separate scoped cleanup helper after container removal, including interruption cases where SIGKILL prevents traps from running. Cleanup errors cannot yield PASS. The prepared runtime log volume and real NF logs intentionally persist; `make lab-down` preserves it together with MongoDB data. Do not delete it before collecting failed-run evidence.

Local regression tests use command stubs, temporary filesystem fixtures, and local process-control checks. They protect failure reporting and initialization logic but do not prove Docker/Linux capability. Normal static CI does not run lab containers. The new log preparation and full UPF bootstrap probe must be executed on the external VM before the complete core/RAN baseline retry.

Follow the [runtime validation procedure](runtime_validation.md): clean teardown → host/expanded runtime preflight → MongoDB/core/UPF → subscriber → gNB/NG Setup → UE registration/authentication/security/PDU session → tunnel/DN traffic → `baseline_e2e` → sanitized evidence capture. The user-reported MongoDB and isolated TUN successes do not establish that baseline.

Current claim level remains **STATIC + FIXTURE VALIDATED / REAL LINUX RUNTIME PENDING**.

## Direct VM validation and additional pinned startup contracts

On 2026-09-09 the agent gained authorized SSH access to the Linux lab. Before changes, commit `b1212cd8a9c11ead1f08f233d2599671dc01fa9c` reproduced AMF's missing `amf.time.t3512.value`, PCF/UDR attempts to connect to `mongodb://mongo/open5gs`, UDR's unknown nested `db_uri`, and the incompatible gNB invocation. Original diagnostic output is retained on the VM under ignored `runtime/validation/b1212cd-before-fixes/`.

The following contracts were inspected before implementation:

- [Open5GS v2.8.0 initialization](https://github.com/open5gs/open5gs/blob/v2.8.0/lib/app/ogs-init.c) reads root-level `db_uri`, then gives the `DB_URI` environment variable precedence. The actual pinned image inherits `DB_URI=mongodb://mongo/open5gs`. PCF and UDR therefore both explicitly override `DB_URI=mongodb://mongodb/open5gs` in Compose and use matching root-level YAML. No `mongo` DNS alias is added.
- The [v2.8.0 AMF template](https://github.com/open5gs/open5gs/blob/v2.8.0/configs/open5gs/amf.yaml.in) supplies `time.t3512.value: 540`; the AMF parser requires a nonzero value encodable as GPRS Timer 3. Static validation now protects that requirement.
- The digest-verified `gradiant/ueransim:3.3.0` entrypoint expects `gnb` or `ue`, shifts that token, and prepares environment-based template files. Passing `nr-gnb` made it attempt to execute `-c`. Compose invokes the verified `/usr/local/bin/nr-gnb` and `/usr/local/bin/nr-ue` binaries directly with the existing read-only config paths. The amd64 image manifest is `sha256:a4a72b01edefa52690e4c9c0d1e75a6625bb6b2aa1c68d23ef1250cc12cf8857`; entrypoint file SHA-256 is `abc03b3aa42d552b02b63937451c7c52d39b7e08b41a874aea55a6b986962bbb`.
- The [UERANSIM TUN setup](https://github.com/aligungr/UERANSIM/blob/6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156/src/ue/tun/config.cpp) uses TUN and interface/route administration without a nested namespace in this lab. UE now explicitly uses root + NET_ADMIN + TUN, with no privileged container. Subscriber keys and provisioning remain unchanged.

`start_lab.sh` now runs `5g-lab core-ready`: within 120 seconds the named core containers must initialize, MongoDB must become healthy, NRF/PFCP association evidence must exist, and a 30-second stability window must complete with zero restarts and unchanged container/process identities. Later logged association losses invalidate earlier success. Failure returns nonzero and retains diagnostic output in `runtime/core-readiness.json`; container uptime alone does not pass.

The baseline runner saves the previous attempt, stops only the lab gNB/UE, checks core startup and subscriber provisioning sequentially, recreates gNB, requires current `is-ngap-up: true`, and only then recreates UE. It requires current registration, active session, tunnel, and interface-bound DN traffic in addition to protocol events. It collects stdout into the exact scenario folder with a run-start time filter. Transport connectivity, NF registration, negative messages, and persistent historical logs cannot substitute for successful protocol events. Command timeouts and interrupts stop descendant processes as well as the immediate shell.

At `7ba0eb628e18bc60231a001b58df1221fa49200e`, actual VM validation obtained expanded runtime-preflight PASS, static config PASS, all eight initialized NFs with zero restarts through the stability window, healthy MongoDB, successful PCF/UDR MongoDB URI logs, both configured ogstun addresses, subscriber provisioning success, and actual NG Setup Response/success plus `is-ngap-up: true`. The initial readiness rejection correctly identified 46 restarts each for the prior AMF/PCF/UDR containers.

UE then failed before registration with `ERROR: Field 'homeNetworkPublicKey' is too large.` The failed attempt and UE state are retained under `runtime/validation/7ba0eb6/`; no UE/session/traffic or baseline success is attributed to that attempt. Follow-up validation results are recorded with their exact executing commit in the curated evidence summary.

The follow-up [v3.3.0 UE parser inspection](https://github.com/aligungr/UERANSIM/blob/6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156/src/ue.cpp) found a 65-character public key (the parser requires exactly 64 when present, including with null protection) and a missing mandatory `integrityMaxRate` object. The fix uses the exact public example key and `uplink: full` / `downlink: full` from the [same version's Open5GS UE example](https://github.com/aligungr/UERANSIM/blob/6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156/config/open5gs-ue.yaml). Null protection and subscriber authentication material are unchanged; static regression checks protect both parser requirements.

### PCF binding-service dependency found during the PDU attempt

At `94272774f25fcda4298fcddbdbd4937c073e1d06`, the corrected UE registered, but PDU establishment did not complete. PCF logged `Try to discover [nbsf-management]`, then `No [nbsf-management:PCF]` and aborted. SMF received an empty SBI reply; UE retransmitted and reported `PAYLOAD_NOT_FORWARDED`. The initial ad hoc state probe mistakenly matched `PS-ACTIVE-PENDING` by substring; the subsequent exact-state probe rejected it. No PDU, tunnel, traffic, or baseline PASS is claimed for this failed attempt. The repository's baseline assertion already requires the exact `PS-ACTIVE` token.

The [pinned PCF SM-data handler](https://github.com/open5gs/open5gs/blob/v2.8.0/src/pcf/nudr-handler.c) unconditionally initiates BSF binding registration after retrieving policy data. The [BSF template](https://github.com/open5gs/open5gs/blob/v2.8.0/configs/open5gs/bsf.yaml.in) supports direct NRF communication. The same deployed image contains `open5gs-bsfd`, verified on the VM. The minimal dependency fix adds that BSF at `10.45.0.26:7777` on the existing core network, with UID/GID 999, the initialized log volume, and no additional privilege or new image. BSF is included in config validation, log initialization/collection/preflight, core startup, and readiness. There are now nine Open5GS NFs; the earlier eight-NF results above describe the earlier commits only.
