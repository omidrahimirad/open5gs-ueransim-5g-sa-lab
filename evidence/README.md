# Evidence Folder

This folder is reserved for real Linux runtime validation evidence.

Sample logs are stored under `logs/` and are clearly labeled as sample data. Do not treat sample logs as proof that the lab executed successfully.

Real outputs should be stored under a dated folder:

```text
evidence/real_run_YYYYMMDD/
├── logs/
├── outputs/
├── reports/
└── screenshots/
```

## Commit Rules

Commit:

- Small sanitized logs that prove NG setup, registration, authentication/security, and PDU session behavior.
- `docker compose ps` output.
- Parser CSV/JSON generated from real logs.
- Traffic test output.
- Screenshots that show useful validation evidence and contain no secrets.
- Updated reports that clearly state the run date and host environment.

Do not commit:

- Huge raw logs.
- Private credentials, tokens, real SIM data, customer data, or sensitive network information.
- Unsanitized packet captures.
- Duplicate generated files that do not add evidence.

## Minimum Files For A Validated Run

- `outputs/docker_version.txt`
- `outputs/docker_compose_version.txt`
- `outputs/compose_ps_all.txt`
- `outputs/parser_summary.txt`
- `outputs/parsed_attach_events.csv`
- `outputs/parsed_attach_events.json`
- `outputs/traffic_test_result.txt`
- AMF, SMF, gNB, UE, and UPF logs under `logs/`
- At least one screenshot showing container status or UE tunnel/traffic evidence
