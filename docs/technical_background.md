# Technical Background

## 5G SA vs NSA

5G Standalone uses a 5G Core and 5G NR access end to end. The UE registers to the AMF and establishes PDU sessions through the 5GC. 5G Non-Standalone anchors signaling through LTE/EPC and uses NR mainly as an additional radio bearer. This lab focuses on SA because it exercises 5GC registration, slicing fields, DNN selection, SMF/UPF behavior, and N2/N3 integration.

## Open5GS Role

Open5GS is the 5G Core implementation in this lab. The AMF handles UE registration and mobility control, the SMF manages PDU sessions, the UPF forwards user-plane packets, the NRF provides service discovery, and MongoDB stores subscriber/session data.

## UERANSIM Role

UERANSIM simulates the gNB and UE. It is useful for validating core integration without RF hardware. The gNB connects to the AMF over N2/NGAP/SCTP and carries user-plane packets to the UPF over N3/GTP-U. The UE performs NAS registration and asks for a PDU session.

## UE Registration

Registration starts with a NAS Registration Request. The AMF identifies the subscriber, triggers authentication, negotiates security, and accepts registration if subscription, PLMN, and policy checks pass.

## PDU Session

A PDU session gives the UE IP connectivity for a DNN such as `internet`. The SMF selects the session parameters and controls the UPF using PFCP. The UE receives an IP address and UERANSIM creates a tunnel interface for user-plane traffic.

## Control Plane vs User Plane

The control plane is signaling: NAS, NGAP, SBI, and PFCP. The user plane is packet forwarding after setup: UE traffic through the simulated gNB to UPF and onward to the data network.

## Where This Lab Is Useful

- Understanding 5G SA attach and session establishment.
- Practicing Open5GS and UERANSIM configuration.
- Debugging PLMN, DNN, slice, SCTP, and TUN issues.
- Building repeatable evidence for telecom lab and integration roles.
- Creating log-analysis workflows with Python.

## Where This Lab Is Limited

This lab does not model RF propagation, real scheduler behavior, commercial gNB DU/CU timing, MIMO, HARQ, field KPIs, handovers, or vendor-specific counters. It complements RAN KPI work; it does not replace RF testing or live network operations.

