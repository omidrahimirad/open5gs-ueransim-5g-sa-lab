# Latency Report

This report template documents the method and expected evidence for the 5G SA lab. The sample values below are illustrative and must be replaced with measured values after running `scripts/traffic_test.sh` on a Linux host.

## Test Environment

| Item | Value |
|---|---|
| Host OS | Ubuntu 22.04/24.04 LTS recommended |
| Docker | Record with `docker version` |
| Docker Compose | Record with `docker compose version` |
| Open5GS image | `${OPEN5GS_IMAGE:-gradiant/open5gs:latest}` |
| UERANSIM image | `${UERANSIM_IMAGE:-gradiant/ueransim:latest}` |
| Core network | Open5GS AMF, SMF, UPF, NRF, MongoDB |
| RAN/UE | UERANSIM gNB and UE |
| DNN / slice | `internet`, SST `1`, SD `000001` |

## Method

1. Start Open5GS and UERANSIM on a Linux host with SCTP and `/dev/net/tun`.
2. Confirm gNB NG setup, UE registration, and PDU session establishment.
3. Run `./scripts/traffic_test.sh` from the repository root.
4. Save `logs/traffic_test_result.txt` and parse related logs.

## Sample Result Table

| Test case | Packets transmitted | Packets received | Packet loss | Min latency | Avg latency | Max latency | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| Sample ping to 8.8.8.8 via UE PDU session | 5 | 5 | 0% | 18.2 ms | 22.7 ms | 31.4 ms | Sample only; replace after real run |
| Failed-session example | 5 | 0 | 100% | n/a | n/a | n/a | Usually DNN/slice/UPF route issue |

## Interpretation

Latency in this lab validates that a simulated UE received a PDU session and that user-plane packets traverse the UE container, simulated gNB, UPF, and N6 network path. It is useful for connectivity and integration troubleshooting.

It is not equivalent to commercial RAN latency. UERANSIM does not model RF channel conditions, scheduler behavior, HARQ, MIMO layers, antenna patterns, real UE modem behavior, or gNB DU/CU split timing. Container scheduling, host CPU load, Docker bridge NAT, and Internet path variability may dominate measurements.

For a more realistic RF/RAN setup, use SDR or commercial gNB hardware, calibrated RF cabling or chamber conditions, real USIM/eSIM credentials, controlled packet core placement, PTP/GNSS timing where required, and traffic tools such as iperf3 with controlled endpoints.
