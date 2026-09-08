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

3. Tear down any prior lab containers/networks, then confirm Linux runtime prerequisites. This teardown preserves the MongoDB volume.

```bash
make lab-down
make preflight
docker compose pull upf mongodb
make runtime-preflight
```

If host preflight reports missing SCTP, load it with `sudo modprobe sctp` on the lab host and rerun preflight. Resolve other reported failures before proceeding. The probes require a reachable Linux Docker daemon and locally available configured images matching its native architecture; image pulls are explicit in the sequence above.

`make runtime-preflight` (equivalently `uv run 5g-lab runtime-preflight`) performs an isolated UPF container TUN check; it does not start the full lab. It uses the resolved Compose UPF image and runtime privilege settings to create and delete a temporary TUN interface. Optional `--mongodb` also starts the configured MongoDB image with its Compose environment and waits for a localhost `mongosh` ping. Each probe has a command timeout (30 seconds for UPF, 90 seconds for MongoDB), followed by bounded cleanup. The temporary containers use no lab networks, lab data volumes, or service dependencies.

The probes use [Compose one-off execution](https://docs.docker.com/reference/cli/docker/compose/run/) with `--no-deps --rm --pull never`. On timeout or interruption, the local Docker/Compose process group is stopped before cleanup. A separate cleanup step attempts [forced container and anonymous-volume removal](https://docs.docker.com/reference/cli/docker/container/rm/) and verifies that the uniquely named probe container is absent. A cleanup failure reports the exact container and removal command; resolve it before continuing.

To include the MongoDB smoke check, use `uv run 5g-lab runtime-preflight --mongodb` in place of `make runtime-preflight` above.

The direct CLI returns `PASS=0`, `FAIL=1`, or `BLOCKED=2`; use it when automation needs to distinguish exit codes, because `make` reports recipe failures with its own nonzero status. Missing execution prerequisites or native images produce `BLOCKED`; invalid runtime contracts, failed capability/startup probes, interruption, or cleanup failure produce `FAIL`. This explicit Linux runtime check is not part of normal static CI. A host preflight pass and a container preflight pass are prerequisites, not evidence of registration or a healthy user plane.

4. Start the core and verify it before provisioning or starting the RAN/UE.

```bash
make lab-up
docker compose ps
docker compose logs --tail 100 mongodb upf nrf amf smf
docker compose exec -T mongodb mongosh --quiet --eval 'db.runCommand({ping:1}).ok'
docker compose exec -T upf ip link show ogstun
```

Confirm MongoDB is healthy, UPF created `ogstun`, and the core functions remain running without startup errors. Continue only when these checks pass.

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

6. Parse real logs and save evidence.

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_baseline_e2e"
mkdir -p "evidence/real_runs/${RUN_ID}"/{logs,pcap}
uv run python scripts/parse_attach_logs.py logs/*/*.log -o "evidence/real_runs/${RUN_ID}/events.csv"
docker compose --profile ran --profile tools ps > "evidence/real_runs/${RUN_ID}/compose_ps.txt"
cp logs/traffic_test_result.txt "evidence/real_runs/${RUN_ID}/traffic_result.txt"
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

The [Linux bootstrap findings](runtime_findings.md) distinguish user-supplied external observations from repository-side static tests and runtime work still pending.

| Symptom | Check and correction |
| --- | --- |
| MongoDB exits with a kernel 6.19+ incompatibility message | Keep the pinned `mongo:8.3.8-noble` image and ensure resolved Compose includes `GLIBC_TUNABLES=glibc.pthread.rseq=1` for MongoDB. The user reported a successful isolated ping with this setting on kernel `7.0.0-1011-gcp`; validate Compose startup on the target host. This is a kernel/runtime compatibility setting, not an Open5GS application requirement. |
| UPF reports `ioctl(TUNSETIFF): Operation not permitted` | Check the effective user and capabilities inside the container. The intended UPF contract is `user: "0:0"`, `NET_ADMIN`, and `/dev/net/tun`, without `privileged: true`. The image's default UID 999 had no effective capabilities in the user's failing test. Run `make runtime-preflight` before retrying startup. |
| Host preflight passes but container startup fails | Host preflight checks prerequisites such as Linux, SCTP, tools, and TUN availability. It does not execute the UPF image's TUN operation. Container runtime preflight checks that specific operation with the configured image/user/capabilities; full core readiness and baseline validation remain separate steps. |

After applying a fix, repeat the clean teardown → host/runtime preflight → core/UPF verification → subscriber → gNB/NG Setup → UE/session/tunnel → DN traffic → `baseline_e2e` sequence. Preserve the failed attempt and new results as distinct, sanitized records. Do not proceed to fault interpretation until the baseline passes.
