# System Validation Method

The system under test is a one-UE 5G SA lab using UERANSIM UE/gNB and Open5GS 5GC network functions. The validation harness checks configuration consistency, Linux host readiness, baseline behavior, scoped negative scenarios, evidence, assertions, and recovery.

## Claim Levels

- STATIC VERIFIED: source files, Compose rendering, YAML consistency, scripts, and schemas are checked.
- FIXTURE VERIFIED: parser/assertion/reporting logic is tested with sample or synthetic evidence.
- RUNTIME VERIFIED: actual Linux execution proves behavior with real logs, traffic results, and environment metadata.

## Baseline Gate

All fault scenarios depend on `baseline_e2e`. If baseline cannot prove NG setup, registration, authentication/security, PDU session, UE tunnel, and DN traffic, fault scenarios are blocked. A broken baseline makes later failure interpretation unreliable.

The CLI enforces this by requiring a passing baseline result before runtime fault scenarios run:

```bash
uv run 5g-lab scenario run upf_unavailable --baseline-result reports/runtime/<baseline_run>/scenario_result.json
```

## Expected vs Observed

Scenario YAML files define expected events and forbidden events. Runtime logs and test outputs produce observed events. The assertion engine compares them without inventing missing evidence.

## Recovery Checks

Component and transport faults must remove the fault, restore services, and rerun baseline assertions. A scenario is not PASS just because the injected failure appeared; cleanup and recovery also matter.

## Limitations

The current repository is static plus fixture validated. Real runtime validation requires a capable Linux host with Docker, SCTP, TUN, and container networking privileges.
