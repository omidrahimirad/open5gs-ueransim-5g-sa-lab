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

3. Confirm Linux runtime prerequisites.

```bash
make preflight
sudo modprobe sctp || true
make preflight
```

4. Start the lab and provision the subscriber.

```bash
make lab-up
make subscriber-add
docker compose --profile ran up -d gnb ue
docker compose --profile ran --profile tools ps
```

5. Run baseline user-plane validation.

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
