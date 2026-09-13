# Scenario Report: n3_impairment

Run ID: `20260913T134948542881Z_n3_impairment`

Started: `2026-09-13T13:49:48.542881Z`

Status: **PASS**

## Runtime State

- Baseline ready: True
- Baseline context fingerprint: 77c083a3dd5f2aaa44c94ade87a4026a6d1fc58099ce07c9ba06b89a2b420636
- Fault applied: True
- Fault verified: True
- Expected failure observed: True
- Recovery attempted: True
- Recovery status: PASS
- Rollback verified: True
- Recovery verified: True

## Observed Events

error, ue_tunnel_created, unclassified_relevant, user_plane_failure

## Assertions

| Assertion | Status | Expected | Observed |
| --- | --- | --- | --- |
| expected_event:user_plane_failure | PASS | user_plane_failure observed | observed |

## Recovery Assertions

| Assertion | Status | Expected | Observed |
| --- | --- | --- | --- |
| recovery:required_lab_services_running | PASS | all required 5GC, RAN, UE, and DN services running | all running |
| recovery:n2_ready | PASS | UERANSIM gNB reports is-ngap-up: true | is-ngap-up: true |
| recovery:ue_registered | PASS | UERANSIM UE reports RM-REGISTERED | cm-state: CM-CONNECTED
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
 tmsi: 0xc00002da
has-emergency: false |
| recovery:pdu_session_active | PASS | UERANSIM UE reports a PS-ACTIVE PDU session | PDU Session1:
 state: PS-ACTIVE
 session-type: IPv4
 apn: internet
 s-nssai:
  sst: 0x01
  sd: 0x000001
 emergency: false
 address: 10.45.1.2
 ambr: up[1000000Kb/s] down[1000000Kb/s]
 data-pending: false |
| recovery:ue_tunnel_exists | PASS | uesimtun0 exists in the UE container | 3: uesimtun0: <POINTOPOINT,PROMISC,NOTRAILERS,UP,LOWER_UP> mtu 1400 qdisc fq_codel state UNKNOWN mode DEFAULT group default qlen 500
    link/none |
| recovery:user_plane_dn_traffic | PASS | interface-bound traffic reaches the lab DN target | success |
| recovery:final_core_ready | PASS | initialized core, MongoDB healthy, current associations, zero restarts for 30s | Core initialized, MongoDB healthy, NRF/PFCP associations ready, and no restarts for 30s; not baseline validation |
| recovery:final_gnb_status | PASS | is-ngap-up:\s*true(?:\s|$) | is-ngap-up: true |
| recovery:final_ue_status | PASS | rm-state:\s*RM-REGISTERED(?:\s|$) | cm-state: CM-CONNECTED
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
 tmsi: 0xc00002da
has-emergency: false |
| recovery:final_ue_ps-list | PASS | state:\s*PS-ACTIVE(?:\s|$) | PDU Session1:
 state: PS-ACTIVE
 session-type: IPv4
 apn: internet
 s-nssai:
  sst: 0x01
  sd: 0x000001
 emergency: false
 address: 10.45.1.2
 ambr: up[1000000Kb/s] down[1000000Kb/s]
 data-pending: false |
| recovery:final_ran_running_without_restarts | PASS | both RAN containers running with zero restarts | /ueransim-gnb|running|0
/ueransim-ue|running|0 |

## Evidence

| Type | Claim level | Path | Description |
| --- | --- | --- | --- |
| runtime_manifest | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/environment.json` | Environment metadata captured at scenario start. |
| runtime_versions | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/versions.json` | Pinned runtime image defaults and execution context. |
| runtime_context | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/runtime_context.json` | Context used to bind the baseline gate to this runtime. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_traffic_result.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_boundary.json` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/amf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/ausf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/bsf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/dn-server.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/gnb.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/log-init.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/mongodb.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/nrf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/pcf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/smf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/udm.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/udr.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/ue.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/fault_logs/upf.log` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/post_recovery_compose_ps.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/post_recovery_gnb_status.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/post_recovery_ue_status.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/post_recovery_pdu_sessions.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/post_recovery_ue_tunnel.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_traffic_result.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_assertions.json` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_final_core_readiness.json` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_final_gnb_status.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_final_ue_status.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_final_ue_ps-list.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_final_ran_containers.txt` | Runtime command output generated during scenario execution. |
| runtime_output | RUNTIME VERIFIED | `/home/omid_rahimirad/open5gs-ueransim-5g-sa-lab/reports/runtime/audit/20260913T134948542881Z_n3_impairment/recovery_final_health_timing.json` | Runtime command output generated during scenario execution. |

## Notes

- Command failed: ./scripts/traffic_test.sh
