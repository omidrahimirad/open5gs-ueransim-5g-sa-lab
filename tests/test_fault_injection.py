from __future__ import annotations

import subprocess

import pytest

from fiveg_lab.fault_injection import CommandRunner, FaultInjector, run_with_fault_cleanup
from fiveg_lab.scenarios import FaultSpec


def ok_runner(
    history: list[tuple[str, ...]],
) -> CommandRunner:
    def run(command: tuple[str, ...], _timeout: int) -> subprocess.CompletedProcess[str]:
        history.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    return run


def test_stop_service_generates_apply_and_rollback_commands() -> None:
    history: list[tuple[str, ...]] = []
    injector = FaultInjector(FaultSpec(type="stop_service", target="upf"), ok_runner(history))

    injector.apply()
    injector.remove()

    assert history == [
        ("docker", "compose", "stop", "upf"),
        ("docker", "compose", "start", "upf"),
    ]


def test_wrong_service_target_is_rejected() -> None:
    injector = FaultInjector(FaultSpec(type="stop_service", target="mongodb"), ok_runner([]))

    with pytest.raises(ValueError, match="fault target"):
        injector.apply_commands()


def test_arbitrary_interface_is_rejected() -> None:
    injector = FaultInjector(
        FaultSpec(type="n3_impairment", target="gnb", value="en0"),
        ok_runner([]),
    )

    with pytest.raises(ValueError, match="interface"):
        injector.apply_commands()


def test_cleanup_runs_after_scenario_exception() -> None:
    history: list[tuple[str, ...]] = []
    injector = FaultInjector(FaultSpec(type="stop_service", target="smf"), ok_runner(history))

    with pytest.raises(RuntimeError, match="scenario failed"):
        run_with_fault_cleanup(injector, failing_body)

    assert history[-1] == ("docker", "compose", "start", "smf")


def failing_body() -> None:
    raise RuntimeError("scenario failed")
