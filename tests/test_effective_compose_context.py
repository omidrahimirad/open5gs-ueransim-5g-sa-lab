from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from fiveg_lab.orchestration import (
    CommandOutcome,
    effective_compose_state,
    scenario_traffic_environment,
)


def test_effective_overrides_change_hash_but_mapping_order_does_not(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    value = {"services": {"amf": {"image": "example:1", "environment": {"A": "1", "B": "2"}}}}

    def command(args: list[str], _cwd: Path, _timeout: int) -> CommandOutcome:
        assert args == [
            "docker",
            "compose",
            "--profile",
            "ran",
            "--profile",
            "tools",
            "config",
            "--format",
            "json",
        ]
        return CommandOutcome(args, 0, json.dumps(value), "")

    monkeypatch.setattr("fiveg_lab.orchestration.run_command", command)
    first = effective_compose_state(tmp_path)
    assert effective_compose_state(tmp_path) == first
    value = {"services": {"amf": {"environment": {"B": "2", "A": "1"}, "image": "example:1"}}}
    assert effective_compose_state(tmp_path) == first
    value["services"]["amf"]["environment"] = {"A": "changed by Compose override"}
    changed = effective_compose_state(tmp_path)
    assert changed["sha256"] != first["sha256"]
    assert "changed by Compose override" not in json.dumps(changed)


def test_failed_compose_resolution_has_no_reusable_hash(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "fiveg_lab.orchestration.run_command",
        lambda *_args: CommandOutcome([], 1, "", "private environment error"),
    )
    assert effective_compose_state(tmp_path) == {"available": False}


def test_scenario_traffic_cannot_inherit_a_loopback_target(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TARGET", "127.0.0.1")
    monkeypatch.setenv("UE_TUNNEL", "lo")
    monkeypatch.setenv("COUNT", "1")
    assert scenario_traffic_environment(tmp_path / "traffic.txt") == {
        "OUT": str(tmp_path / "traffic.txt"),
        "TARGET": "10.46.0.100",
        "UE_TUNNEL": "uesimtun0",
        "COUNT": "5",
    }
