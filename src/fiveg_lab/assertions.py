from __future__ import annotations

from fiveg_lab.models import AssertionResult, ResultStatus
from fiveg_lab.scenarios import Scenario


def evaluate_scenario_events(
    scenario: Scenario, observed_events: set[str]
) -> list[AssertionResult]:
    results: list[AssertionResult] = []
    for event in scenario.expected_events:
        present = event in observed_events
        results.append(
            AssertionResult(
                name=f"expected_event:{event}",
                status=ResultStatus.PASS if present else ResultStatus.FAIL,
                expected=f"{event} observed",
                observed="observed" if present else "missing",
                detail="Expected event evidence was present."
                if present
                else "Expected event was absent.",
            )
        )
    for event in scenario.forbidden_events:
        present = event in observed_events
        results.append(
            AssertionResult(
                name=f"forbidden_event:{event}",
                status=ResultStatus.FAIL if present else ResultStatus.PASS,
                expected=f"{event} absent",
                observed="observed" if present else "absent",
                detail="Forbidden event was observed."
                if present
                else "Forbidden event was not observed.",
            )
        )
    return results


def scenario_status(assertions: list[AssertionResult]) -> ResultStatus:
    if any(result.status == ResultStatus.ERROR for result in assertions):
        return ResultStatus.ERROR
    if any(result.status == ResultStatus.FAIL for result in assertions):
        return ResultStatus.FAIL
    return ResultStatus.PASS
