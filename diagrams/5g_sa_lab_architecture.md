# 5G SA Lab Architecture

GitHub renders the Mermaid diagram below directly in Markdown.

```mermaid
flowchart LR
    UE["UERANSIM UE\nSUPI imsi-001010000000001"] -- "N1 NAS via gNB" --> GNB["UERANSIM gNB\nTAC 1 / PLMN 001-01"]
    GNB -- "N2 NGAP over SCTP" --> AMF["Open5GS AMF"]
    GNB -- "N3 GTP-U" --> UPF["Open5GS UPF"]
    AMF -- "SBI/Nnrf" --> NRF["Open5GS NRF"]
    SMF["Open5GS SMF"] -- "SBI/Nnrf" --> NRF
    AMF -- "N11 SBI" --> SMF
    SMF -- "N4 PFCP" --> UPF
    UPF -- "N6 IP forwarding/NAT" --> DN["Data Network / Internet"]
    AMF -. "subscriber lookup" .-> DB[("MongoDB\nOpen5GS subscriber DB")]
    SMF -. "session state" .-> DB
```

Interface notes:

- N1: UE NAS signaling carried through the gNB.
- N2: gNB to AMF control plane using NGAP over SCTP.
- N3: gNB to UPF user plane using GTP-U.
- N4: SMF to UPF control using PFCP.
- N6: UPF to data network.

