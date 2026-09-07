from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from fiveg_lab.models import ResultStatus
from fiveg_lab.orchestration import (
    CommandOutcome,
    baseline_result_passed,
    command_notes,
    latest_log_dir,
    run_runtime_scenario,
    version_manifest,
)
from fiveg_lab.scenarios import FaultSpec, Scenario


def test_baseline_result_gate_requires_pass(tmp_path: Path) -> None:
    result_path = tmp_path / "scenario_result.json"
    result_path.write_text(
        json.dumps({"scenario_id": "baseline_e2e", "status": "PASS"}),
        encoding="utf-8",
    )

    assert baseline_result_passed(result_path)


def test_baseline_result_gate_rejects_missing_or_failed(tmp_path: Path) -> None:
    assert not baseline_result_passed(tmp_path / "missing.json")
    failed = tmp_path / "failed.json"
    failed.write_text(
        json.dumps({"scenario_id": "baseline_e2e", "status": ResultStatus.FAIL}),
        encoding="utf-8",
    )

    assert not baseline_result_passed(failed)


def test_latest_log_dir_selects_newest_timestamp(tmp_path: Path) -> None:
    older = tmp_path / "20260621T000000Z"
    newer = tmp_path / "20260622T000000Z"
    older.mkdir()
    newer.mkdir()

    assert latest_log_dir(tmp_path) == newer


def test_command_notes_include_failed_commands() -> None:
    notes = command_notes(
        [
            CommandOutcome(
                args=["docker", "compose", "ps"],
                returncode=1,
                stdout="",
                stderr="compose failed",
            )
        ]
    )

    assert notes == ["Command failed: docker compose ps", "compose failed"]


def test_version_manifest_records_pinned_defaults(tmp_path: Path) -> None:
    manifest = version_manifest(tmp_path)

    assert manifest["open5gs_image_default"] == "gradiant/open5gs:2.8.0"
    assert manifest["ueransim_image_default"] == "gradiant/ueransim:3.3.0"


def test_runtime_scenario_returns_blocked_result(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("fiveg_lab.orchestration.blocking_reason", lambda _root: ["no linux"])
    scenario = Scenario(
        id="baseline_e2e",
        title="Baseline",
        category="USER_PLANE",
        description="Fixture",
        preconditions=[],
        fault=FaultSpec(type="none"),
        expected_control_plane="ok",
        expected_user_plane="ok",
        expected_events=[],
        forbidden_events=[],
        recovery_action="none",
        recovery_expectation="none",
        timeout_seconds=1,
        runtime_validated=False,
    )

    result = run_runtime_scenario(tmp_path, scenario, tmp_path / "out", None, settle_seconds=0)

    assert result.status == ResultStatus.BLOCKED
    assert (tmp_path / "out" / result.run_id / "scenario_result.json").exists()
