# Real Linux baseline — 2026-09-10

**`baseline_e2e`: PASS, all 20 assertions.** Executed at `c94601398f1009008ff4b779b0c5a510253b9983` on `omid5g-sa-lab`, Ubuntu 24.04.4 LTS, Linux 7.0.0-1011-gcp x86_64, Docker 29.8.0, Compose 5.5.1. Access used the existing `omid_rahimirad` user through `gcloud compute ssh`, project `verdant-branch-466219-t6`, zone `europe-west3-a`.

This folder was collected from real containers over authorized SSH. No fixture logs were used. The later commit adding this evidence and documentation is not the executing commit; the preserved baseline fingerprint belongs to `c946013` and must not be reused to authorize faults at a different commit.

## Observed results

| Check | Evidence / result |
| --- | --- |
| Expanded runtime preflight | [PASS summary](runtime-preflight-summary.txt): all nine NF log-write probes, full UPF bootstrap/NAT/cleanup, MongoDB startup/ping |
| Config consistency | [validate-config.txt](validate-config.txt): PASS |
| Core startup | [core-readiness.json](core-readiness.json): nine initialized NFs, NRF/PFCP associations, healthy MongoDB, zero restarts over 30 stable seconds |
| Database contract | Core-readiness logs show PCF and UDR using `mongodb://mongodb/open5gs`; both initialize successfully |
| UPF addresses | [ogstun.txt](ogstun.txt): `10.45.1.1/24` and `cafe::1/64` |
| NG Setup | [gnb.log](logs/gnb.log): response received and procedure successful; [live status](baseline_gnb_status.txt): `is-ngap-up: true` |
| Registration | [ue.log](logs/ue.log): authentication, security mode, registration acceptance/success; [live status](baseline_ue_status.txt): `RM-REGISTERED` |
| PDU session | [live sessions](baseline_pdu_sessions.txt): exact `PS-ACTIVE`, IPv4 `10.45.1.3`, DNN `internet`, SST 1 / SD 000001 |
| Tunnel and DN traffic | [tunnel](baseline_ue_tunnel.txt) and [traffic](baseline_traffic_result.txt): `uesimtun0`; 5/5 replies from `10.46.0.100`, 0% loss, interface-bound ping |
| Baseline assertions | [scenario_result.json](scenario_result.json), [report](scenario_report.md): PASS; forbidden authentication failure, registration/PDU rejection, and user-plane failure absent |
| Final stability / privileges | [final readiness](core-ready-final.json) and [container state](container-state-final.json): zero restarts, MongoDB healthy, non-UPF NFs 999:999, UPF/UE root + NET_ADMIN + TUN, no privileged containers |

Before the scenario, the same commit passed a separate manual staged attempt with PDU address `10.45.1.2` and 5/5 DN replies. The scenario recreated gNB/UE after a fresh core check and received `10.45.1.3`. These are separate attempts, not conflicting addresses.

The parser's `component_failure` event comes from AMF's `gNB-N2 ... connection refused` at 14:42:20 UTC while the runner deliberately stops the prior gNB. The recreated gNB succeeds at 14:42:59 UTC. Endpoint `UnRef NF EndPoint(addr)` warnings remain in the logs. They did not prevent any baseline assertion or the final core stability check; this is not a claim of warning-free logs.

## Provenance and limits

- [environment.json](environment.json), [versions.json](versions.json), [runtime_context.json](runtime_context.json), and [capabilities.json](capabilities.json) retain environment, image, commit, scenario, SCTP/TUN, and forwarding metadata. The original environment generator's conditional pending-claim string is preserved; the actual result is the separate scenario PASS.
- [events.csv](events.csv) contains 108 events parsed from these real scenario logs and the traffic output. It reproduces the event-type set in the original result. No cumulative NF file logs or prior-attempt logs were used.
- Raw originals remain on the VM under `reports/runtime/20260910T144212150699Z_baseline_e2e/` and `runtime/validation/c946013/`. Original report paths retain that provenance; corresponding collected files are here. MongoDB/DN stdout, cumulative NF logs, and prior-attempt exports are omitted to keep the collection small.
- [commands.json](commands.json) redacts the subscriber provisioning command's output; its exit code is preserved. Private provisioning output is retained only on the VM. Subscriber material was not changed by this work.
- ANSI colors, trailing whitespace, and final newlines were normalized for review. [collection-sha256.json](collection-sha256.json) records the collected files before that normalization, after provisioning-output redaction. Scenario status, assertions, timestamps, and observed state were not rewritten.
- Packet capture was not enabled. No fault, recovery, throughput, IPv6 PDU session, RF behavior, or long-duration reliability claim is made. The lab was left running after validation. PR #11 remains open and unmerged.

The prior failed attempts are documented in [runtime findings](../../../docs/runtime_findings.md): `7ba0eb6` stopped at an invalid UE public-key length; `9427277` registered UE but PCF aborted because BSF was absent. Neither attempt passed a PDU/traffic baseline. Their exact diagnostics remain under the matching ignored VM validation directories.
