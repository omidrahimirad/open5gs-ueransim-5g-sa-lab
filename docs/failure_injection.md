# Failure Injection

Failure injection is lab-scoped and reversible. Scenario YAML describes the fault; it cannot contain shell commands.

| Fault type | Scope | Expected impact | Rollback |
| --- | --- | --- | --- |
| `subscriber_key_mismatch` | Lab subscriber/UE credentials | Authentication failure or registration reject | Restore known-good K/OPc and reprovision |
| `unknown_subscriber` | Lab UE SUPI and subscriber DB | Subscriber/authentication failure | Restore known-good SUPI and DB record |
| `dnn_mismatch` | Lab DNN/APN fields | PDU session reject/failure | Restore `internet` DNN everywhere |
| `snssai_mismatch` | Lab SST/SD fields | Behavior must be proven from Open5GS/UERANSIM logs | Restore SST `1`, SD `000001` |
| `restart_service` | AMF/SMF/UPF/gNB/UE only | Service interruption and recovery | Docker Compose restart completion plus baseline recheck |
| `stop_service` | AMF/SMF/UPF/gNB/UE only | Component unavailable | Docker Compose start plus baseline recheck |
| `n2_impairment` | Known gNB container interface | NGAP/SCTP impact | Remove container `tc` qdisc |
| `n3_impairment` | Known gNB container interface | GTP-U/user-plane impact | Remove container `tc` qdisc |

Safety restrictions:

- no arbitrary command execution
- no host-wide network manipulation
- only known lab services can be targeted
- only known container interfaces can be impaired
- cleanup is attempted even after scenario errors

Do not run fault scenarios until `baseline_e2e` has passed in the same runtime environment.

Subscriber/config mutation faults are modeled and assertion-tested, but runtime mutation is not automated in this version. Run those manually only on disposable lab state and commit evidence only after rollback is proven.
