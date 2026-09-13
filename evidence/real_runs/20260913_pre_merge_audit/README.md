# PR #11 audit: fresh Linux baseline and N3 fault validation

Executed at **`daca4542608f0bb20ca01441f5e584ce89890ad1`** on the existing `omid5g-sa-lab` VM, using `omid_rahimirad` through Google Cloud SSH in project `verdant-branch-466219-t6`, zone `europe-west3-a`. Linux 7.0.0-1011-gcp x86_64, glibc 2.39, Python 3.11.16, Docker 29.8.0, Compose 5.5.1. The later evidence/documentation commit is not the executing commit. Historical September 10 evidence remains unchanged.

## Results

| Run | Result | Observed evidence |
| --- | --- | --- |
| [Fresh baseline](20260913T134706899485Z_baseline_e2e/scenario_result.json) | PASS, all 25 assertions | Actual NG Setup preceded UE startup; registered UE, active IPv4 PDU session `10.45.1.2`, `uesimtun0`, 5/5 replies from DN `10.46.0.100`. |
| [Normal N3 fault](20260913T134948542881Z_n3_impairment/scenario_result.json) | PASS, recovery PASS | Real gNB egress UDP/2152 drop to UPF `10.45.0.30`; 5 transmitted, 0 received. Verified removal restored 5/5 replies and all 11 recovery checks. |
| [Stale-evidence negative test](20260913T135235685990Z_n3_impairment/scenario_result.json) | ERROR, as required; recovery PASS | Real N3 mutation/rollback, but deliberately simulated current probe exit 127 and collector exit 1. Old synthetic failure evidence was present. No observed events; `expected_failure_observed=false`; rollback verified and all 11 recovery checks passed. |

The baseline's [traffic output](20260913T134706899485Z_baseline_e2e/baseline_traffic_result.txt) ends at **13:48:51 UTC**. The mandatory [final health gate](20260913T134706899485Z_baseline_e2e/baseline_final_health_timing.json) then ran **13:48:51.972622–13:49:26.520443 UTC**. Its [core result](20260913T134706899485Z_baseline_e2e/baseline_final_core_readiness.json) requires initialized NFs, healthy MongoDB, current NRF/PFCP associations, and zero restarts for 30 stable seconds. Final live gNB/UE protocol state and container state also passed. PCF/UDR logs contain `mongodb://mongodb/open5gs`.

[Configuration validation](config.txt) and [expanded runtime preflight](preflight.txt), including isolated MongoDB and cleanup, passed after a clean lab teardown. Data/log volumes were preserved. [Capabilities](capabilities.txt) records SCTP/TUN and host tools; the port-7777 warning was collected with the lab already running. [Final container state](container-state-final.json) records zero restarts, non-UPF NF users `999:999`, scoped UPF/UE capabilities, and no privileged containers. [UPF addresses](ogstun.txt) remain `10.45.1.1/24` and `cafe::1/64`. Final [N3 filter](n3-filter-final.txt) is absent and [qdisc state](n3-qdisc-final.txt) has no residual clsact. The lab was left healthy and running at the executing commit.

## Negative-test method and claim limits

The [normal harness](fault_audit.py.txt) journals the actual tc commands without changing their execution. Its first attempt to set up the negative fixture failed because the parent directory did not exist, after the normal fault had already passed and recovered. No negative fault had been injected at that point. The [separate negative harness](negative_audit.py.txt) creates that parent and runs only the negative case. These are audit harness transcripts, not repository runtime-code changes.

The negative run's [method metadata](20260913T135235685990Z_n3_impairment/audit_method.json) identifies the old **synthetic** `USER_PLANE_FAILURE` fixture and the two injected tool failures. Its [command journal](20260913T135235685990Z_n3_impairment/fault_operations.json) proves actual scoped filter addition, verification, removal, and verified absence. Pre-fault and recovery traffic/health commands execute normally. Its ERROR is the expected rejection of missing current evidence, not a successful traffic-failure observation and not a spontaneous collector outage. No synthetic fixture is presented as real traffic evidence.

The normal run's [fault boundary](20260913T134948542881Z_n3_impairment/fault_boundary.json), current traffic artifact, filtered `fault_logs/`, and [tc journal](20260913T134948542881Z_n3_impairment/fault_operations.json) belong to that run only. A failed collector never selects the legacy log directory.

## Provenance, sanitization, and prior attempts

- Each run retains environment, versions, effective-Compose fingerprint, scenario result, and current state. The environment generator's conditional pending-claim text is preserved; the actual observed results are reported separately above. Fingerprints match across these three runs. Reusing these results with a different commit is intentionally blocked.
- Original full artifacts remain on the VM under `reports/runtime/audit/<run_id>/` and `runtime/audit/daca454-retry/`. The earlier `230c692` run at `20260913T085222412747Z_baseline_e2e` remains FAIL: it exposed the overly broad `Unknown UE` rejection parser. A subsequent morning attempt at `daca454` was interrupted by loss of SSH/VM reboot and has no completed result. Neither is rewritten or counted as PASS.
- Provisioning-command stdout/stderr is redacted in `commands.json`; exit codes are retained. Raw subscriber output stays only on the VM. No PCAP, private key, token, or subscriber provisioning dump is committed.
- ANSI sequences, trailing whitespace, and final newlines were normalized. [Collection hashes](collection-sha256.json) record selected source bytes after provisioning redaction and before formatting normalization. Final capability/container/address/filter snapshots were collected separately. Cumulative NF-file exports, prior-attempt logs, MongoDB/DN stdout, and duplicate pre-fault core snapshots are omitted. Original evidence paths still name their source locations on the VM.
- This establishes the baseline and the specific N3 fault/recovery path on this VM. Other fault paths have unit coverage but were not newly runtime validated. No throughput, IPv6 PDU session, packet-capture, RF/OTA, multi-host/multi-UE, or long-duration reliability claim is made.
