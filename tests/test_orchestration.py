from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from fiveg_lab.models import AssertionResult, ResultStatus
from fiveg_lab.orchestration import (
    CommandOutcome,
    RecoveryValidation,
    baseline_result_passed,
    command_notes,
    context_fingerprint,
    execute_fault_scenario,
    latest_log_dir,
    run_runtime_scenario,
    validate_baseline_result,
    validate_recovered_baseline,
    version_manifest,
)
from fiveg_lab.scenarios import FaultSpec, Scenario


def context() -> dict[str, object]:
    return {
        "schema_version": 1,
        "git_commit": "a" * 40,
        "config_sha256": {"docker-compose.yml": "b" * 64},
        "runtime_images": {"amf": "gradiant/open5gs:2.8.0"},
        "host": {"node": "lab-host", "kernel": "6.8.0", "docker_engine": "28.0"},
    }


def write_baseline(path: Path, fingerprint: str) -> None:
    path.write_text(
        json.dumps(
            {
                "scenario_id": "baseline_e2e",
                "status": "PASS",
                "baseline_ready": True,
                "baseline_context_fingerprint": fingerprint,
            }
        ),
        encoding="utf-8",
    )


def scenario(fault_type: str = "stop_service", target: str = "upf") -> Scenario:
    return Scenario(
        id="upf_unavailable",
        title="UPF unavailable",
        category="USER_PLANE",
        description="Fixture",
        preconditions=[],
        fault=FaultSpec(type=fault_type, target=target),
        expected_control_plane="ok",
        expected_user_plane="failure",
        expected_events=[],
        forbidden_events=[],
        recovery_action="restore",
        recovery_expectation="baseline",
        timeout_seconds=1,
        runtime_validated=False,
    )


def outcome(args: list[str] | None = None, stdout: str = "", returncode: int = 0) -> CommandOutcome:
    return CommandOutcome(args=args or ["fixture"], returncode=returncode, stdout=stdout, stderr="")


def test_matching_baseline_context_is_accepted(tmp_path: Path) -> None:
    fingerprint = context_fingerprint(context())
    result_path = tmp_path / "scenario_result.json"
    write_baseline(result_path, fingerprint)

    assert baseline_result_passed(result_path, fingerprint)
    assert validate_baseline_result(result_path, fingerprint).passed


@pytest.mark.parametrize("changed_field", ["git_commit", "config_sha256", "runtime_images"])
def test_stale_baseline_context_is_rejected(tmp_path: Path, changed_field: str) -> None:
    baseline_context = context()
    result_path = tmp_path / "scenario_result.json"
    write_baseline(result_path, context_fingerprint(baseline_context))
    current_context = context()
    if changed_field == "git_commit":
        current_context[changed_field] = "c" * 40
    elif changed_field == "config_sha256":
        current_context[changed_field] = {"docker-compose.yml": "d" * 64}
    else:
        current_context[changed_field] = {"amf": "gradiant/open5gs:2.8.1"}

    gate = validate_baseline_result(result_path, context_fingerprint(current_context))

    assert not gate.passed
    assert gate.reason == "baseline result does not match current runtime context."


def test_malformed_baseline_result_is_rejected(tmp_path: Path) -> None:
    result_path = tmp_path / "scenario_result.json"
    result_path.write_text('{"scenario_id":', encoding="utf-8")

    gate = validate_baseline_result(result_path, context_fingerprint(context()))

    assert not gate.passed
    assert "malformed baseline result" in gate.reason


def test_baseline_gate_rejects_missing_or_failed(tmp_path: Path) -> None:
    fingerprint = context_fingerprint(context())
    assert not baseline_result_passed(tmp_path / "missing.json", fingerprint)
    failed = tmp_path / "failed.json"
    failed.write_text(
        json.dumps(
            {
                "scenario_id": "baseline_e2e",
                "status": ResultStatus.FAIL,
                "baseline_ready": False,
                "baseline_context_fingerprint": fingerprint,
            }
        ),
        encoding="utf-8",
    )

    assert not baseline_result_passed(failed, fingerprint)


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
    assert manifest["policy_control_mode"] == "PCF enabled for Open5GS 2.8.0"


def test_runtime_scenario_returns_blocked_result(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("fiveg_lab.orchestration.blocking_reason", lambda _root: ["no linux"])
    monkeypatch.setattr("fiveg_lab.orchestration.runtime_context_manifest", lambda _root: context())
    baseline = scenario("none", "upf")
    baseline = Scenario(**{**baseline.__dict__, "id": "baseline_e2e"})

    result = run_runtime_scenario(tmp_path, baseline, tmp_path / "out", None, settle_seconds=0)

    assert result.status == ResultStatus.BLOCKED
    assert (tmp_path / "out" / result.run_id / "scenario_result.json").exists()


def fake_recovery_command(
    args: list[str],
    _cwd: Path,
    _timeout: int,
    env: dict[str, str] | None = None,
) -> CommandOutcome:
    if args == ["./scripts/traffic_test.sh"]:
        assert env is not None
        Path(env["OUT"]).write_text("USER_PLANE_SUCCESS\n", encoding="utf-8")
        return outcome(args, "traffic passed")
    if "--status" in args:
        return outcome(args, "container-id\n")
    if args[-4:] == ["ip", "link", "show", "uesimtun0"]:
        return outcome(args, "9: uesimtun0: <POINTOPOINT,UP,LOWER_UP>")
    return outcome(args, "all services")


def test_ping_success_alone_is_not_sufficient_for_recovery(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("fiveg_lab.orchestration.run_command", fake_recovery_command)

    def bad_cli(
        _root: Path, service: str, subcommand: str, _timeout: int
    ) -> tuple[CommandOutcome, CommandOutcome]:
        if service == "gnb":
            status = "is-ngap-up: false"
        elif subcommand == "status":
            status = "rm-state: RM-DEREGISTERED"
        else:
            status = "state: PS-INACTIVE"
        return outcome(stdout="node"), outcome(stdout=status)

    monkeypatch.setattr("fiveg_lab.orchestration.run_ueransim_cli", bad_cli)

    recovery = validate_recovered_baseline(tmp_path, tmp_path, 1)

    assert recovery.status == ResultStatus.FAIL
    statuses = {item.name: item.status for item in recovery.assertions}
    assert statuses["recovery:user_plane_dn_traffic"] == ResultStatus.PASS
    assert statuses["recovery:n2_ready"] == ResultStatus.FAIL
    assert statuses["recovery:ue_registered"] == ResultStatus.FAIL
    assert statuses["recovery:pdu_session_active"] == ResultStatus.FAIL


def test_full_recovery_state_passes(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("fiveg_lab.orchestration.run_command", fake_recovery_command)

    def good_cli(
        _root: Path, service: str, subcommand: str, _timeout: int
    ) -> tuple[CommandOutcome, CommandOutcome]:
        if service == "gnb":
            status = "is-ngap-up: true"
        elif subcommand == "status":
            status = "rm-state: RM-REGISTERED"
        else:
            status = "PDU Session1:\n  state: PS-ACTIVE\n  address: 10.45.1.2"
        return outcome(stdout="node"), outcome(stdout=status)

    monkeypatch.setattr("fiveg_lab.orchestration.run_ueransim_cli", good_cli)

    recovery = validate_recovered_baseline(tmp_path, tmp_path, 1)

    assert recovery.status == ResultStatus.PASS
    assert all(item.status == ResultStatus.PASS for item in recovery.assertions)


class VerifiedInjector:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.applied = False
        self.cleanup_required = False
        self.last_verification_error = None

    def apply(self) -> None:
        self.applied = True

    def verify_applied(self) -> bool:
        return True

    def remove(self) -> None:
        self.applied = False

    def verify_removed(self) -> bool:
        return True


def test_failed_fault_verification_prevents_pass(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    class UnverifiedInjector(VerifiedInjector):
        def verify_applied(self) -> bool:
            return False

    monkeypatch.setattr("fiveg_lab.orchestration.FaultInjector", UnverifiedInjector)

    result = execute_fault_scenario(
        tmp_path, scenario(), tmp_path, "run", "2026-01-01T00:00:00Z", "f" * 64, 0
    )

    assert result.status == ResultStatus.ERROR
    assert not result.fault_verified
    assert not result.recovery_verified


def test_recovery_failure_forces_overall_scenario_failure(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("fiveg_lab.orchestration.FaultInjector", VerifiedInjector)
    monkeypatch.setattr(
        "fiveg_lab.orchestration.run_command",
        lambda args, _cwd, _timeout, env=None: outcome(args, stdout=str(env or "")),
    )
    failed_assertion = AssertionResult(
        name="recovery:n2_ready",
        status=ResultStatus.FAIL,
        expected="ready",
        observed="down",
        detail="fixture",
    )
    monkeypatch.setattr(
        "fiveg_lab.orchestration.validate_recovered_baseline",
        lambda *_args: RecoveryValidation(ResultStatus.FAIL, [failed_assertion], [], []),
    )

    result = execute_fault_scenario(
        tmp_path, scenario(), tmp_path, "run", "2026-01-01T00:00:00Z", "f" * 64, 0
    )

    assert result.status == ResultStatus.FAIL
    assert result.rollback_verified
    assert not result.recovery_verified


def test_rollback_command_failure_is_reported_and_prevents_pass(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    class RollbackFailureInjector(VerifiedInjector):
        def remove(self) -> None:
            raise RuntimeError("rollback command failed")

    monkeypatch.setattr("fiveg_lab.orchestration.FaultInjector", RollbackFailureInjector)
    monkeypatch.setattr(
        "fiveg_lab.orchestration.run_command",
        lambda args, _cwd, _timeout, env=None: outcome(args, stdout=str(env or "")),
    )

    result = execute_fault_scenario(
        tmp_path, scenario(), tmp_path, "run", "2026-01-01T00:00:00Z", "f" * 64, 0
    )

    assert result.status == ResultStatus.FAIL
    assert not result.rollback_verified
    assert any("rollback command failed" in note for note in result.notes)
