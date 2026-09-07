from __future__ import annotations

from pathlib import Path

from fiveg_lab.assertions import evaluate_scenario_events, scenario_status
from fiveg_lab.models import ResultStatus
from fiveg_lab.scenarios import parse_scenario
from tests.helpers import valid_scenario_payload


def test_expected_event_observed_passes() -> None:
    scenario = parse_scenario(valid_scenario_payload(), Path(__file__))

    results = evaluate_scenario_events(scenario, {"authentication_failure"})

    assert scenario_status(results) == ResultStatus.PASS


def test_expected_event_missing_fails() -> None:
    scenario = parse_scenario(valid_scenario_payload(), Path(__file__))

    results = evaluate_scenario_events(scenario, set())

    assert scenario_status(results) == ResultStatus.FAIL


def test_forbidden_event_observed_fails() -> None:
    scenario = parse_scenario(valid_scenario_payload(), Path(__file__))

    results = evaluate_scenario_events(
        scenario,
        {"authentication_failure", "registration_accept"},
    )

    assert scenario_status(results) == ResultStatus.FAIL
