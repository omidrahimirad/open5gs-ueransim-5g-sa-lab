# Evidence Folder

This folder is reserved for **real Linux runtime validation evidence only**.

Sample logs are stored under [../logs](../logs/) and are clearly labeled as sample data. Do not treat sample logs, fixture reports, or generated parser tests as proof that Open5GS/UERANSIM completed a real runtime attach.

Use this structure for real runs:

```text
evidence/real_runs/<run_id>/
├── environment.json
├── versions.json
├── compose_ps.txt
├── scenario_result.json
├── events.csv
├── traffic_result.txt
├── logs/
└── pcap/
```

Legacy dated folders such as `evidence/real_run_YYYYMMDD/` are acceptable if they contain the same minimum evidence and are clearly labeled real.

Do not commit:

- huge raw logs
- private tokens, real SIM credentials, customer data, or commercial network details
- unsanitized packet captures
- duplicate generated files that do not add evidence

Minimum files before calling a run validated:

- `environment.json` with OS, kernel, Docker, Compose, Python, git commit, and SCTP/TUN status
- `versions.json` with Open5GS, UERANSIM, MongoDB, dbctl, and DN image tags
- `compose_ps.txt`
- `scenario_result.json`
- `events.csv` or parser JSON generated from real logs
- `traffic_result.txt` for baseline/user-plane scenarios
- AMF, AUSF/UDM/UDR where relevant, SMF, UPF, gNB, and UE logs
- pcap files or pcap metadata when packet capture was enabled
