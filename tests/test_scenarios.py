from __future__ import annotations

from pathlib import Path

import pytest

from fiveg_lab.scenarios import load_scenarios, parse_scenario
from tests.helpers import valid_scenario_payload

REPO_ROOT = Path(__file__).resolve().parents[1]


def valid_payload() -> dict[str, object]:
    return valid_scenario_payload()


def test_all_repository_scenarios_are_valid() -> None:
    scenarios = load_scenarios(REPO_ROOT / "scenarios")

    assert {scenario.id for scenario in scenarios} >= {
        "baseline_e2e",
        "invalid_subscriber_key",
        "upf_unavailable",
    }


def test_missing_id_is_rejected(tmp_path: Path) -> None:
    payload = valid_payload()
    payload.pop("id")

    with pytest.raises(ValueError, match="missing required"):
        parse_scenario(payload, tmp_path / "scenario.yaml")


def test_invalid_fault_type_is_rejected(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["fault"] = {"type": "run_anything"}

    with pytest.raises(ValueError, match="invalid fault type"):
        parse_scenario(payload, tmp_path / "scenario.yaml")


def test_unknown_expected_event_is_rejected(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["expected_events"] = ["magic_event"]

    with pytest.raises(ValueError, match="unknown event"):
        parse_scenario(payload, tmp_path / "scenario.yaml")


def test_arbitrary_command_key_is_rejected(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["fault"] = {"type": "subscriber_key_mismatch", "command": "rm -rf /"}

    with pytest.raises(ValueError, match="Unsafe scenario key"):
        parse_scenario(payload, tmp_path / "scenario.yaml")


def test_invalid_timeout_is_rejected(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["timeout_seconds"] = 0

    with pytest.raises(ValueError, match="timeout_seconds"):
        parse_scenario(payload, tmp_path / "scenario.yaml")
