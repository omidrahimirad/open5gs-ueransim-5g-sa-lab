# Runtime Validation Procedure

Use Ubuntu 22.04/24.04 or another capable Linux host. Docker Desktop on macOS is not enough to claim real SCTP/TUN runtime validation.

1. Clone and checkout the target commit.

```bash
git clone https://github.com/omidrahimirad/open5gs-ueransim-5g-sa-lab.git
cd open5gs-ueransim-5g-sa-lab
git checkout <commit-or-branch>
```

2. Install dependencies and validate static state.

```bash
uv sync
make check
```

3. Tear down any prior lab containers/networks, then confirm Linux runtime prerequisites. This teardown preserves the MongoDB and application-log volumes; save failed-run evidence first.

```bash
make lab-down
make preflight
docker compose pull upf mongodb
make runtime-preflight
```

If host preflight reports missing SCTP, load it with `sudo modprobe sctp` on the lab host and rerun preflight. Resolve other reported failures before proceeding. The probes require a reachable Linux Docker daemon and locally available configured images matching its native architecture; image pulls are explicit in the sequence above.

`make runtime-preflight` (equivalently `uv run 5g-lab runtime-preflight`) prepares the actual Docker-managed runtime log volume and verifies temporary file writes using each Open5GS NF's effective user and mount. It then runs the same UPF bootstrap entrypoint used by Compose in an isolated container: sysctl values, IPv4/IPv6 TUN addresses, link state, and optional NAT must all succeed and clean up. It does not launch the UPF daemon or full lab. Optional `--mongodb` also performs isolated MongoDB startup and localhost ping.

The check requires Linux, a reachable Docker daemon, and local images matching its native architecture. Probe containers have no lab networks, ports, service dependencies, or database/subscriber volumes. They share only the configured application-log volume and necessary read-only bootstrap script. Each probe has a bounded runtime (30 seconds; 90 seconds for MongoDB), timeout/interrupt handling, uniquely scoped container removal, and file cleanup after removal. A cleanup failure returns FAIL. The prepared application-log volume and NF logs intentionally persist for lab startup/evidence; probe containers, interfaces, NAT rules, and temporary files must not remain. See the [bootstrap findings](runtime_findings.md) for source evidence and limitations.

To include the MongoDB smoke check, use `uv run 5g-lab runtime-preflight --mongodb` in place of `make runtime-preflight` above.

The direct CLI returns `PASS=0`, `FAIL=1`, or `BLOCKED=2`; use it when automation needs to distinguish exit codes, because `make` reports recipe failures with its own nonzero status. Missing execution prerequisites or native images produce `BLOCKED`; invalid runtime contracts, failed capability/startup probes, interruption, or cleanup failure produce `FAIL`. This explicit Linux runtime check is not part of normal static CI. A host preflight pass and a container preflight pass are prerequisites, not evidence of registration or a healthy user plane.

4. Start the core and verify it before provisioning or starting the RAN/UE.

```bash
make lab-up
docker compose ps
docker compose logs --tail 100 log-init mongodb upf nrf amf smf
docker compose exec -T mongodb mongosh --quiet --eval 'db.runCommand({ping:1}).ok'
docker compose exec -T upf ip link show ogstun
```

Confirm `log-init` exited successfully, non-UPF NFs remain UID/GID 999, MongoDB is healthy, UPF created `ogstun`, and the core functions remain running without startup errors. Continue only when these checks pass.

`make lab-up` now includes `uv run 5g-lab core-ready --output runtime/core-readiness.json`. It waits at most 120 seconds for initialization, MongoDB health, NRF/PFCP associations, and a 30-second window with zero restarts and unchanged process identities. It fails on restart loops or initialization errors; `up -d` alone is never the readiness result. Run the same CLI to recheck an existing core. The JSON retains state and current-process logs for diagnosis.

```bash
make subscriber-add
docker compose --profile ran up -d gnb
docker compose logs --tail 100 gnb amf
```

Verify actual NG Setup success in the gNB/AMF logs before starting the UE.

```bash
docker compose --profile ran up -d ue
docker compose --profile ran --profile tools ps
docker compose logs --tail 100 ue amf ausf smf upf
docker compose exec -T ue ip link show uesimtun0
docker compose exec -T ue ip route
```

Verify UE registration, authentication, Security Mode, and PDU session establishment from real logs/state, followed by `uesimtun0` and its route. Container uptime or a TUN interface alone does not establish these results.

5. Verify DN traffic, then run the baseline scenario.

```bash
./scripts/traffic_test.sh
uv run 5g-lab scenario run baseline_e2e --output-dir reports/runtime
make collect-evidence
```

Runtime scenario exit codes are `PASS=0`, `FAIL=1`, `BLOCKED=2`, `ERROR=3`, and `SKIPPED=4`. In particular, `make baseline-test` returns nonzero when host preflight blocks execution.

The baseline runner preserves prior logs, stops the lab UE/gNB, checks core readiness and subscriber provisioning, and recreates gNB and UE sequentially. It requires live NGAP readiness before UE startup, then current registered/session/tunnel/traffic state plus successful protocol events. Current-run stdout is saved in the scenario's own `logs/` directory with a run-start filter. Previous attempts and cumulative application-file diagnostics are excluded from assertions. Keep the complete scenario folder when curating evidence.

6. Parse real logs and save evidence.

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_baseline_e2e"
mkdir -p "evidence/real_runs/${RUN_ID}"/{logs,pcap}
LATEST_LOG_DIR="$(find runtime/logs -maxdepth 1 -type d -name '20*T*Z' | sort | tail -n 1)"
uv run python scripts/parse_attach_logs.py "${LATEST_LOG_DIR}"/*.log -o "evidence/real_runs/${RUN_ID}/events.csv"
docker compose --profile ran --profile tools ps > "evidence/real_runs/${RUN_ID}/compose_ps.txt"
cp runtime/traffic_test_result.txt "evidence/real_runs/${RUN_ID}/traffic_result.txt"
```

7. Run one fault scenario only after baseline passes.

```bash
uv run 5g-lab scenario run upf_unavailable \
  --baseline-result reports/runtime/<baseline_run>/scenario_result.json
```

The baseline result is valid only on the same git commit, configuration fingerprint, resolved image set, and host/runtime identity. Re-run `baseline_e2e` after any relevant change instead of reusing a stale result.

After rollback, component and transport scenarios write `post_recovery_compose_ps.txt`, gNB/UE CLI state, PDU-session state, UE-tunnel state, `recovery_traffic_result.txt`, and `recovery_assertions.json`. Recovery requires all checks; ping alone is insufficient.

8. Stop the lab.

```bash
make lab-down
```

Do not update the repository status to runtime validated until the committed evidence includes environment metadata, real logs, parser output, traffic output, and scenario results.

## Bootstrap troubleshooting

The [Linux bootstrap findings](runtime_findings.md) distinguish initial user-supplied observations, static tests, failed VM attempts, and the subsequent successful Linux baseline. See the [curated baseline evidence](../evidence/real_runs/20260910T144212150699Z_baseline_e2e/README.md) for the exact executing commit and remaining limits.

| Symptom | Check and correction |
| --- | --- |
| MongoDB exits with a kernel 6.19+ incompatibility message | Keep the pinned `mongo:8.3.8-noble` image and ensure resolved Compose includes `GLIBC_TUNABLES=glibc.pthread.rseq=1` for MongoDB. The user reported a successful isolated ping and healthy Compose MongoDB with this setting on kernel `7.0.0-1011-gcp`; the same-host `rseq=0` control failed. Recheck readiness on the target commit. This is a kernel/runtime compatibility setting, not an Open5GS application requirement. |
| UPF reports `ioctl(TUNSETIFF): Operation not permitted` | Check the effective user and capabilities inside the container. The intended UPF contract is `user: "0:0"`, `NET_ADMIN`, `/dev/net/tun`, Compose-managed sysctls, and the repository bootstrap, without `privileged: true`. The image's default UID 999 had no effective capabilities in the user's failing test. Run `make runtime-preflight` before retrying startup. |
| NF cannot open `/var/log/open5gs/<nf>.log` | Inspect `docker compose logs log-init` and the NF effective user. Keep the initialized named-volume mount; do not restore `./logs` bind mounts or run all NFs as root. Runtime preflight tests the actual log volume with each NF user. |
| AMF reports missing `amf.time.t3512.value` | Use the pinned upstream timer default of 540 seconds and rerun config validation. |
| PCF/UDR connects to `mongodb://mongo/open5gs` | Open5GS gives the image's `DB_URI` environment variable precedence over YAML. Both services must explicitly set `DB_URI=mongodb://mongodb/open5gs`; both YAML files use root-level `db_uri`. Do not add a DNS alias to hide the override. |
| gNB/UE exits attempting to execute `-c` | The pinned image wrapper expects `gnb` or `ue`. Keep the declared direct binary entrypoints and existing read-only config mounts. |
| UE rejects `homeNetworkPublicKey` or `integrityMaxRate` | The pinned parser requires a 64-hex public key when present and both integrity rate fields. Use the checked-in versioned example values and rerun config validation. |
| UPF cannot write `net.ipv6.conf.all.disable_ipv6` | Ensure the resolved Compose uses `/lab/upf-entrypoint.sh` and all three required sysctls. The image entrypoint writes protected sysctls even if their values are already correct; the repository wrapper verifies Docker-configured values instead. |
| Host preflight passes but container startup fails | Host preflight checks prerequisites such as Linux, SCTP, tools, and TUN availability. It does not exercise NF log mounts or the full UPF bootstrap. Expanded runtime preflight checks log writability and the configured bootstrap with its real user/capabilities; full core readiness and baseline validation remain separate steps. |

After applying a fix, repeat the clean teardown → host/runtime preflight → core/UPF verification → subscriber → gNB/NG Setup → UE/session/tunnel → DN traffic → `baseline_e2e` sequence. Preserve the failed attempt and new results as distinct, sanitized records. Do not proceed to fault interpretation until the baseline passes.

`make collect-evidence` writes mutable exports to `runtime/logs/<UTC>/`, with NF file logs in `nf-files/`. The scenario parser uses container stdout. Persistent NF files can include earlier attempts and are diagnostic exports only; inspect timestamps before citing them. Sample fixtures in `logs/` are never mounted into containers. The previous `logs/<UTC>/` exports are not deleted, but are no longer selected automatically.
