# Scenario Report: baseline_e2e

Run ID: `20260910T144212150699Z_baseline_e2e`

Started: `2026-09-10T14:42:12.150699Z`

Status: **PASS**

## Runtime State

- Baseline ready: True
- Baseline context fingerprint: 1990ed9e9dc61d7898d45bfaa5bc2e3685110c095363982b70f816f3c138a4c3
- Fault applied: False
- Fault verified: False
- Expected failure observed: False
- Recovery attempted: False
- Recovery status: SKIPPED
- Rollback verified: False
- Recovery verified: False

## Observed Events

authentication, component_failure, error, ng_setup, pdu_session_accept, pdu_session_request, registration_accept, registration_request, security_mode, ue_tunnel_created, unclassified_relevant, user_plane_success

## Assertions

| Assertion | Status | Expected | Observed |
| --- | --- | --- | --- |
| baseline:initial_ng_setup | PASS | gNB reports is-ngap-up: true | is-ngap-up: true |
| baseline:required_lab_services_running | PASS | all required 5GC, RAN, UE, and DN services running | all running |
| baseline:n2_ready | PASS | UERANSIM gNB reports is-ngap-up: true | is-ngap-up: true |
| baseline:ue_registered | PASS | UERANSIM UE reports RM-REGISTERED | cm-state: CM-CONNECTED
rm-state: RM-REGISTERED
mm-state: MM-REGISTERED/NORMAL-SERVICE
5u-state: 5U1-UPDATED
sim-inserted: true
selected-plmn: 001/01
current-cell: 1
current-plmn: 001/01
current-tac: 1
last-tai: PLMN[001/01] TAC[1]
stored-suci: no-identity
stored-guti:
 plmn: 001/01
 amf-region-id: 0x02
 amf-set-id: 1
 amf-pointer: 0
 tmsi: 0xc00005e3
has-emergency: false |
| baseline:pdu_session_active | PASS | UERANSIM UE reports a PS-ACTIVE PDU session | PDU Session1:
 state: PS-ACTIVE
 session-type: IPv4
 apn: internet
 s-nssai:
  sst: 0x01
  sd: 0x000001
 emergency: false
 address: 10.45.1.3
 ambr: up[1000000Kb/s] down[1000000Kb/s]
 data-pending: false |
| baseline:ue_tunnel_exists | PASS | uesimtun0 exists in the UE container | 3: uesimtun0: <POINTOPOINT,PROMISC,NOTRAILERS,UP,LOWER_UP> mtu 1400 qdisc fq_codel state UNKNOWN mode DEFAULT group default qlen 500
    link/none |
| baseline:user_plane_dn_traffic | PASS | interface-bound traffic reaches the lab DN target | success |
| expected_event:ng_setup | PASS | ng_setup observed | observed |
| expected_event:registration_request | PASS | registration_request observed | observed |
| expected_event:authentication | PASS | authentication observed | observed |
| expected_event:security_mode | PASS | security_mode observed | observed |
| expected_event:registration_accept | PASS | registration_accept observed | observed |
| expected_event:pdu_session_request | PASS | pdu_session_request observed | observed |
| expected_event:pdu_session_accept | PASS | pdu_session_accept observed | observed |
| expected_event:ue_tunnel_created | PASS | ue_tunnel_created observed | observed |
| expected_event:user_plane_success | PASS | user_plane_success observed | observed |
| forbidden_event:authentication_failure | PASS | authentication_failure absent | absent |
| forbidden_event:registration_reject | PASS | registration_reject absent | absent |
| forbidden_event:pdu_session_reject | PASS | pdu_session_reject absent | absent |
| forbidden_event:user_plane_failure | PASS | user_plane_failure absent | absent |

## Recovery Assertions

| Assertion | Status | Expected | Observed |
| --- | --- | --- | --- |


## Evidence

| Type | Claim level | Path | Description |
| --- | --- | --- | --- |
| runtime_manifest | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/environment.json` | Environment metadata captured at scenario start. |
| runtime_versions | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/versions.json` | Pinned runtime image defaults and execution context. |
| runtime_context | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/runtime_context.json` | Context used to bind the baseline gate to this runtime. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/commands.json` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_initial_ng_setup.json` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_compose_ps.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_gnb_status.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_ue_status.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_pdu_sessions.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_ue_tunnel.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_traffic_result.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/baseline_assertions.json` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/amf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/ausf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/bsf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/dn-server.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/gnb.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/log-init.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/mongodb.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/nrf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/pcf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/smf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/udm.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/udr.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/ue.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `reports/runtime/20260910T144212150699Z_baseline_e2e/logs/upf.log` | Runtime command output generated during scenario execution. |

## Notes

- None
