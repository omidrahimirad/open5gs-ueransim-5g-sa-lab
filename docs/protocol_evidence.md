# Protocol Evidence

This project extracts a unified event timeline from Open5GS, UERANSIM, and test logs.

| Interface | Protocol | Evidence source |
| --- | --- | --- |
| N1 | NAS | UE, gNB, AMF logs; NAS events carried via gNB |
| N2 | NGAP over SCTP, port 38412 | gNB/AMF logs and optional packet capture |
| N3 | GTP-U UDP/2152 | gNB/UPF logs, UE tunnel evidence, optional packet capture |
| N4 | PFCP UDP/8805 | SMF/UPF logs and optional packet capture |
| N6 | IP data network | Interface-bound ping from UE tunnel to DN server |
| SBI | HTTP/2 service communication | Open5GS NF logs and optional capture/metadata |

The parser classifies only evidence it can recognize from logs. Relevant NAS/NGAP/PFCP/GTP/DNN/NSSAI lines that cannot be safely classified remain `unclassified_relevant` for human review.

Optional pcap metadata extraction uses `tshark` when available. The project does not implement an ASN.1 NGAP decoder and does not claim full protocol decoding unless real captures and tool output prove it.
