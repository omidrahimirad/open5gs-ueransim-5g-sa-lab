# 5G SA Lab Architecture

GitHub renders the Mermaid diagram below directly in Markdown.

```mermaid
flowchart LR
    subgraph RAN["UERANSIM RAN/UE"]
      UE["UE\nSUPI imsi-001010000000001"]
      GNB["gNB\nPLMN 001-01 / TAC 1"]
      UE -- "N1 NAS via gNB" --> GNB
    end

    subgraph CORE["Open5GS 5G Core"]
      NRF["NRF\nSBI discovery"]
      AMF["AMF\nN2 + access/mobility"]
      AUSF["AUSF\nauthentication"]
      UDM["UDM\nsubscriber/auth data"]
      UDR["UDR\nDB front end"]
      PCF["PCF\nAM/SM policy control"]
      SMF["SMF\nPDU session control"]
      UPF["UPF\nN3/N6 user plane"]
      DB[("MongoDB\nOpen5GS DB")]
    end

    subgraph DN["Data Network"]
      DNSRV["DN test server\n10.46.0.100"]
    end

    subgraph VALIDATION["Validation Harness"]
      RUNNER["Scenario runner"]
      FAULT["Fault injection"]
      EVIDENCE["Evidence collector"]
      ASSERT["Deterministic assertions"]
      REPORT["JSON/Markdown report"]
      RUNNER --> FAULT --> EVIDENCE --> ASSERT --> REPORT
    end

    GNB -- "N2 NGAP/SCTP 38412" --> AMF
    GNB -- "N3 GTP-U UDP/2152" --> UPF
    AMF -- "SBI/Nnrf" --> NRF
    AUSF -- "SBI/Nnrf" --> NRF
    UDM -- "SBI/Nnrf" --> NRF
    UDR -- "SBI/Nnrf" --> NRF
    PCF -- "SBI/Nnrf" --> NRF
    SMF -- "SBI/Nnrf" --> NRF
    AMF -- "SBI service interaction" --> AUSF
    AUSF -- "SBI service interaction" --> UDM
    UDM -- "SBI service interaction" --> UDR
    AMF -- "AM policy" --> PCF
    SMF -- "SM policy" --> PCF
    AMF -- "session request" --> SMF
    SMF -- "N4 PFCP UDP/8805" --> UPF
    UDR -. "subscriber data" .-> DB
    PCF -. "policy data" .-> DB
    UPF -- "N6 data network" --> DNSRV
    RUNNER -. "starts/checks" .-> CORE
    RUNNER -. "starts/checks" .-> RAN
```

Interface notes:

- N1: UE NAS signaling carried through the gNB; NAS terminates at AMF.
- N2: gNB to AMF control plane using NGAP over SCTP.
- N3: gNB to UPF user plane using GTP-U.
- N4: SMF to UPF control using PFCP.
- N6: UPF to internal data-network test target.
- SBI: Open5GS service-based interfaces for NF discovery and core service interaction.
- PCF/NSSF mode: PCF is present for Open5GS 2.8.0 policy associations; NSSF is omitted because matching `smf.info` enables direct NRF-based SMF selection.
