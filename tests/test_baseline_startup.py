from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from fiveg_lab.models import ResultStatus
from fiveg_lab.orchestration import (
    CommandOutcome,
    execute_baseline,
    wait_for_ng_setup,
)
from fiveg_lab.readiness import ReadinessResult
from fiveg_lab.scenarios import load_scenario


@pytest.fixture(autouse=True)
def healthy_core_stub(monkeypatch: MonkeyPatch) -> None:
    # Unit-only readiness result; real readiness is exercised separately on Linux.
    monkeypatch.setattr(
        "fiveg_lab.orchestration.wait_core_ready",
        lambda _root: ReadinessResult(True, "unit core ready", 30, {}, {}),
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
EVENT_LOG = "\n".join(
    f"2026-09-09T10:00:01Z [ue] INFO {message}"
    for message in (
        "NG Setup completed",
        "Registration request",
        "Authentication response",
        "Security mode complete",
        "Registration accept",
        "PDU Session Establishment Request",
        "PDU Session Establishment Accept",
        "uesimtun0 created",
        "USER_PLANE_SUCCESS",
    )
)


class BaselineCommands:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.failed_stage = ""
        self.failed_state = ""
        self.current_events = True

    def command(
        self, args: list[str], _cwd: Path, _timeout: int, env: dict[str, str] | None = None
    ) -> CommandOutcome:
        self.calls.append(args)
        returncode = 0
        stdout = "container-id"
        if args[:2] == ["docker", "inspect"]:
            stdout = "/ueransim-gnb|running|0\n/ueransim-ue|running|0\n"
        if args == ["./scripts/collect_logs.sh"]:
            assert env is not None
            output = Path(env["OUT_DIR"])
            output.mkdir(parents=True, exist_ok=True)
            if output.name == "pre_start_logs" or self.current_events:
                (output / "ue.log").write_text(EVENT_LOG)
            if output.name == "logs":
                assert env["SINCE"] == "2026-09-09T10:00:00Z"
        elif args == ["./scripts/traffic_test.sh"]:
            assert env is not None
            returncode = int(self.failed_state == "traffic")
            Path(env["OUT"]).write_text(
                "USER_PLANE_FAILURE" if returncode else "USER_PLANE_SUCCESS"
            )
        elif args[-4:] == ["ip", "link", "show", "uesimtun0"]:
            returncode = int(self.failed_state == "tunnel")
            stdout = "" if returncode else "7: uesimtun0: <UP>"
        elif "--status" in args and self.failed_state == "service" and args[-1] == "amf":
            stdout = ""
        if self.failed_stage and self.failed_stage in args:
            returncode = 1
        return CommandOutcome(args, returncode, stdout, "failed" if returncode else "")

    def cli(
        self, _root: Path, service: str, subcommand: str, _timeout: int
    ) -> tuple[CommandOutcome, CommandOutcome]:
        args = ["nr-cli", service, subcommand]
        self.calls.append(args)
        if service == "gnb":
            status = "is-ngap-up: true"
        elif subcommand == "status":
            state = "RM-DEREGISTERED" if self.failed_state == "registration" else "RM-REGISTERED"
            status = f"rm-state: {state}"
        else:
            state = "PS-INACTIVE" if self.failed_state == "pdu" else "PS-ACTIVE"
            status = f"state: {state}"
        return CommandOutcome(args, 0, "node", ""), CommandOutcome(args, 0, status, "")


def execute(monkeypatch: MonkeyPatch, tmp_path: Path, runner: BaselineCommands):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("fiveg_lab.orchestration.run_command", runner.command)
    monkeypatch.setattr("fiveg_lab.orchestration.run_ueransim_cli", runner.cli)
    scenario = load_scenario(REPO_ROOT / "scenarios/baseline_e2e.yaml")
    return execute_baseline(
        tmp_path, scenario, tmp_path, "run", "2026-09-09T10:00:00Z", "f" * 64, 0
    )


@pytest.mark.parametrize("stage", ["stop", "./scripts/start_lab.sh", "./scripts/add_subscriber.sh"])
def test_failed_prerequisite_stops_all_ran_starts_and_saves_outputs(
    monkeypatch: MonkeyPatch, tmp_path: Path, stage: str
) -> None:
    runner = BaselineCommands()
    runner.failed_stage = stage
    result = execute(monkeypatch, tmp_path, runner)
    assert result.status == ResultStatus.ERROR
    assert not result.baseline_ready
    assert not any("up" in args for args in runner.calls)
    assert not any(args == ["./scripts/traffic_test.sh"] for args in runner.calls)
    commands = json.loads((tmp_path / "commands.json").read_text())
    assert any(item["returncode"] == 1 for item in commands)
    assert (tmp_path / "pre_start_logs/ue.log").exists()
    assert (tmp_path / "logs/ue.log").exists()


def test_ng_setup_failure_prevents_ue_start_even_with_positive_logs(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    runner = BaselineCommands()
    # A zero wait budget provides deterministic timeout without runtime sleeps.
    monkeypatch.setattr(
        "fiveg_lab.orchestration.wait_for_ng_setup",
        lambda root, _timeout: wait_for_ng_setup(root, 0),
    )
    result = execute(monkeypatch, tmp_path, runner)
    assert result.status == ResultStatus.FAIL
    assert not result.baseline_ready
    assert not any("up" in args and args[-1] == "ue" for args in runner.calls)
    assert (tmp_path / "baseline_initial_ng_setup.json").exists()


@pytest.mark.parametrize("state", ["service", "registration", "pdu", "tunnel", "traffic"])
def test_positive_protocol_logs_cannot_replace_current_baseline_state(
    monkeypatch: MonkeyPatch, tmp_path: Path, state: str
) -> None:
    runner = BaselineCommands()
    runner.failed_state = state
    result = execute(monkeypatch, tmp_path, runner)
    assert result.status == ResultStatus.FAIL
    assert not result.baseline_ready
    assert any(item.status == ResultStatus.FAIL for item in result.assertions)
    assert not result.recovery_attempted
    assert result.recovery_status == ResultStatus.SKIPPED


def test_baseline_recreates_ran_sequentially_and_labels_current_state_without_recovery(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    runner = BaselineCommands()
    result = execute(monkeypatch, tmp_path, runner)
    assert result.status == ResultStatus.PASS  # Mocked unit evidence only.
    assert result.baseline_ready
    gnb_start = next(i for i, args in enumerate(runner.calls) if "up" in args and args[-1] == "gnb")
    ue_start = next(i for i, args in enumerate(runner.calls) if "up" in args and args[-1] == "ue")
    ng_check = runner.calls.index(["nr-cli", "gnb", "status"])
    assert gnb_start < ng_check < ue_start
    for index in (gnb_start, ue_start):
        assert {"--no-deps", "--force-recreate"} <= set(runner.calls[index])
    assert (tmp_path / "baseline_assertions.json").exists()
    assert not list(tmp_path.glob("*recovery*"))
    assert not result.recovery_attempted
    assert not result.recovery_verified
    assert result.recovery_status == ResultStatus.SKIPPED


def test_baseline_rejects_old_runtime_logs_and_prior_attempt_snapshot(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    runner = BaselineCommands()
    runner.current_events = False
    old_logs = tmp_path / "runtime/logs/20260909T235959Z"
    old_logs.mkdir(parents=True)
    (old_logs / "ue.log").write_text(EVENT_LOG)
    result = execute(monkeypatch, tmp_path, runner)
    assert result.status == ResultStatus.FAIL
    assert "registration_accept" not in result.observed_events


def test_ng_setup_wait_retries_transient_failure_with_bounded_commands(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    now = [0.0]
    calls: list[int] = []

    def cli(
        _root: Path, _service: str, _subcommand: str, timeout: int
    ) -> tuple[CommandOutcome, CommandOutcome]:
        calls.append(timeout)
        success = len(calls) == 2
        result = CommandOutcome(
            ["nr-cli"], 0 if success else 1, "is-ngap-up: true" if success else "", ""
        )
        return result, result

    def sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr("fiveg_lab.orchestration.time.monotonic", lambda: now[0])
    monkeypatch.setattr("fiveg_lab.orchestration.time.sleep", sleep)
    monkeypatch.setattr("fiveg_lab.orchestration.run_ueransim_cli", cli)
    outcomes, assertion = wait_for_ng_setup(tmp_path, 5)
    assert assertion.status == ResultStatus.PASS
    assert len(outcomes) == 4
    assert all(timeout <= 3 for timeout in calls)
    assert now[0] < 5


@pytest.mark.parametrize(
    "failure", ["PCF exited after traffic", "AMF restarts=1", "deadline reached"]
)
def test_final_core_failure_overrides_successful_traffic(
    monkeypatch: MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    runner = BaselineCommands()

    def final_core(_root: Path) -> ReadinessResult:
        assert ["./scripts/traffic_test.sh"] in runner.calls
        return ReadinessResult(False, failure, 120, {}, {})

    monkeypatch.setattr("fiveg_lab.orchestration.wait_core_ready", final_core)
    result = execute(monkeypatch, tmp_path, runner)
    assert result.status == ResultStatus.FAIL
    assert not result.baseline_ready
    assert any(
        a.name == "baseline:final_core_ready" and a.status == ResultStatus.FAIL
        for a in result.assertions
    )
    assert (tmp_path / "baseline_final_core_readiness.json").exists()


def test_late_ran_restart_cannot_pass(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    runner = BaselineCommands()
    original = runner.command

    def command(
        args: list[str], cwd: Path, timeout: int, env: dict[str, str] | None = None
    ) -> CommandOutcome:
        result = original(args, cwd, timeout, env)
        if args[:2] == ["docker", "inspect"]:
            return CommandOutcome(args, 0, "/ueransim-gnb|running|0\n/ueransim-ue|running|1", "")
        return result

    monkeypatch.setattr(runner, "command", command)
    assert execute(monkeypatch, tmp_path, runner).status == ResultStatus.FAIL
