# Session Establishment Analysis

## Procedure Summary

UE registration validates that the UE identity and subscription can be authenticated by the 5G Core. PDU session establishment validates that the UE can obtain user-plane connectivity for a DNN and network slice.

## Roles

| Component | Role |
|---|---|
| UE | Starts NAS registration, responds to authentication/security, requests PDU session |
| gNB | Carries NAS signaling over N2 and user-plane packets over N3 |
| AMF | Terminates N2, handles registration, authentication coordination, mobility/control plane |
| SMF | Allocates PDU session, selects/controls UPF, applies DNN/slice policy |
| UPF | Forwards user-plane traffic between N3 and N6 |
| NRF | Service registry for Open5GS network functions |

## Control Plane vs User Plane

The control plane includes NAS, NGAP, SBI, and PFCP signaling used to authenticate the UE and create session state. The user plane is the actual IP traffic path after session establishment: UE tunnel to gNB, N3 GTP-U to UPF, then N6 to the data network.

## Success Evidence

Successful attach/session is confirmed by these log events:

- NG setup succeeds between gNB and AMF.
- UE sends registration request.
- Authentication request/response succeeds.
- Security mode command/complete succeeds.
- AMF sends registration accept and receives registration complete.
- UE requests a PDU session for `internet`.
- SMF accepts the PDU session and assigns a UE IP.
- UE creates `uesimtun0` or equivalent tunnel interface.
- Ping or other user-plane traffic succeeds through the UE namespace.

## Common Failure Causes

| Failure | Typical evidence |
|---|---|
| Wrong IMSI/SUPI | AMF cannot find subscriber or rejects registration |
| Wrong key/OPc | Authentication failure in AMF/UE logs |
| Wrong MCC/MNC | gNB/UE PLMN mismatch or AMF rejects TAI/PLMN |
| AMF address mismatch | gNB SCTP connection fails |
| DNN mismatch | SMF rejects PDU session |
| Slice mismatch | Requested S-NSSAI not supported |
| SCTP/networking issue | No NG setup; AMF port 38412 unreachable |
| Missing TUN interface | UE registers but no `uesimtun0` is created |
| UPF route/NAT missing | UE gets IP but ping fails |
| Docker Desktop limitation | Works partially but fails around SCTP/TUN/user plane |
