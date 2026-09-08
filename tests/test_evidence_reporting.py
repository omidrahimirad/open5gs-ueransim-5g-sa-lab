from __future__ import annotations

import json
from pathlib import Path

from fiveg_lab.evidence import write_result
from fiveg_lab.models import AssertionResult, ResultStatus, ScenarioResult


def test_scenario_result_writes_json_and_markdown(tmp_path: Path) -> None:
    result = ScenarioResult(
        scenario_id="fixture",
        run_id="20260621T000000Z_fixture",
        started_at="2026-06-21T00:00:00Z",
        status=ResultStatus.PASS,
        baseline_ready=True,
        fault_applied=False,
        expected_failure_observed=False,
        recovery_attempted=False,
        recovery_status=ResultStatus.SKIPPED,
        observed_events=["registration_accept"],
        assertions=[
            AssertionResult(
                name="expected_event:registration_accept",
                status=ResultStatus.PASS,
                expected="registration_accept observed",
                observed="observed",
                detail="ok",
            )
        ],
    )

    json_path, markdown_path = write_result(result, tmp_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["scenario_id"] == "fixture"
    assert "Scenario Report: fixture" in markdown_path.read_text(encoding="utf-8")
