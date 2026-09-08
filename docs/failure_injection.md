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
| `n2_impairment` | gNB egress SCTP to AMF `10.45.0.20:38412` | NGAP/SCTP impact | Delete only preference `38412`, handle `0x4e32` |
| `n3_impairment` | gNB egress UDP to UPF `10.45.0.30:2152` | GTP-U uplink impact | Delete only preference `2152`, handle `0x4e33` |

## Transport Isolation

N2 and N3 use separate `tc flower` egress filters on the gNB container's `eth0` interface. N2 matches IPv4 SCTP with destination AMF IP `10.45.0.20` and destination port `38412`. N3 matches IPv4 UDP with destination UPF IP `10.45.0.30` and destination port `2152`. Each matching flow is deterministically dropped while unrelated gNB traffic is left outside the filter.

The injector uses a `clsact` qdisc without replacing the interface root qdisc. It records whether `clsact` existed before the scenario. Rollback deletes the exact scenario preference/handle; it removes `clsact` only when that injector created it. A pre-existing `clsact` qdisc is preserved.

The pinned `gradiant/ueransim:3.3.0` OCI build history installs Ubuntu `iproute2`, which supplies `tc`. Actual `clsact`/flower rule installation is still checked at runtime; image metadata alone is not treated as proof that a host kernel accepted the filter.

## Runtime Verification

- `stop_service`: Docker inspection must report the target container not running after stop and running after start.
- `restart_service`: the container must have a changed `StartedAt` timestamp, be running, and not report an unhealthy health state. Removal verification confirms it remains running.
- `n2_impairment` and `n3_impairment`: `tc filter show` must contain the exact handle, protocol, peer IP, port, and drop action. Removal verification requires that exact filter to be absent and, when created by the run, the `clsact` qdisc to be absent.

All commands use argument arrays with bounded subprocess timeouts. Scenario orchestration enforces `apply -> verify applied -> execute -> remove -> verify removed`. Failed verification or rollback prevents `PASS`, and original scenario plus rollback errors are retained in the report.

Safety restrictions:

- no arbitrary command execution
- no host-wide network manipulation
- only known lab services can be targeted
- only known container interfaces can be impaired
- cleanup is attempted even after scenario errors, and cleanup failure is reported

Do not run fault scenarios until `baseline_e2e` has passed in the same runtime environment.

Subscriber/config mutation faults are modeled and assertion-tested, but runtime mutation is not automated in this version. Run those manually only on disposable lab state and commit evidence only after rollback is proven.
