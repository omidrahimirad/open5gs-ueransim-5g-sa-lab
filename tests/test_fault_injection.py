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


def test_n2_and_n3_filters_are_protocol_scoped_and_distinct() -> None:
    n2 = FaultInjector(FaultSpec(type="n2_impairment", target="gnb", value="eth0"), ok_runner([]))
    n3 = FaultInjector(FaultSpec(type="n3_impairment", target="gnb", value="eth0"), ok_runner([]))

    n2_filter = n2.apply_commands()[-1]
    n3_filter = n3.apply_commands()[-1]

    assert n2_filter != n3_filter
    assert "sctp" in n2_filter
    assert "38412" in n2_filter
    assert "10.45.0.20" in n2_filter
    assert "udp" in n3_filter
    assert "2152" in n3_filter
    assert "10.45.0.30" in n3_filter


def test_impairment_rollback_deletes_only_exact_filter() -> None:
    injector = FaultInjector(
        FaultSpec(type="n2_impairment", target="gnb", value="eth0"), ok_runner([])
    )

    rollback = injector.rollback_commands()

    assert len(rollback) == 1
    assert rollback[0][5:9] == ("tc", "filter", "del", "dev")
    assert "38412" in rollback[0]
    assert "0x4e32" in rollback[0]
    assert "root" not in rollback[0]


def test_stop_service_verification_reads_docker_state() -> None:
    inspect_states = iter(
        [
            "false|exited|2026-01-01T00:00:00Z|none",
            "true|running|2026-01-01T00:01:00Z|none",
        ]
    )

    def runner(command: tuple[str, ...], _timeout: int) -> subprocess.CompletedProcess[str]:
        if command[:4] == ("docker", "compose", "ps", "--all"):
            return subprocess.CompletedProcess(command, 0, "container-id\n", "")
        if command[:2] == ("docker", "inspect"):
            return subprocess.CompletedProcess(command, 0, next(inspect_states), "")
        return subprocess.CompletedProcess(command, 0, "", "")

    injector = FaultInjector(FaultSpec(type="stop_service", target="smf"), runner)
    injector.apply()

    assert injector.verify_applied()
    injector.remove()
    assert injector.verify_removed()


def test_restart_verification_requires_new_running_instance_start_time() -> None:
    inspect_states = iter(
        [
            "true|running|2026-01-01T00:00:00Z|none",
            "true|running|2026-01-01T00:01:00Z|none",
            "true|running|2026-01-01T00:01:00Z|none",
        ]
    )

    def runner(command: tuple[str, ...], _timeout: int) -> subprocess.CompletedProcess[str]:
        if command[:4] == ("docker", "compose", "ps", "--all"):
            return subprocess.CompletedProcess(command, 0, "container-id\n", "")
        if command[:2] == ("docker", "inspect"):
            return subprocess.CompletedProcess(command, 0, next(inspect_states), "")
        return subprocess.CompletedProcess(command, 0, "", "")

    injector = FaultInjector(FaultSpec(type="restart_service", target="amf"), runner)
    injector.apply()

    assert injector.verify_applied()
    injector.remove()
    assert injector.verify_removed()


def test_impairment_verification_checks_installed_and_removed_rule() -> None:
    filter_outputs = iter(
        [
            "filter protocol ip pref 2152 flower chain 0 handle 0x4e33\n"
            "  ip_proto udp\n  dst_ip 10.45.0.30\n  dst_port 2152\n"
            "  action order 1: gact action drop",
            "",
        ]
    )
    qdisc_outputs = iter(["qdisc noqueue 0: root", "qdisc noqueue 0: root"])

    def runner(command: tuple[str, ...], _timeout: int) -> subprocess.CompletedProcess[str]:
        if command[6:8] == ("qdisc", "show"):
            return subprocess.CompletedProcess(command, 0, next(qdisc_outputs), "")
        if command[6:8] == ("filter", "show"):
            return subprocess.CompletedProcess(command, 0, next(filter_outputs), "")
        return subprocess.CompletedProcess(command, 0, "", "")

    injector = FaultInjector(FaultSpec(type="n3_impairment", target="gnb", value="eth0"), runner)
    injector.apply()

    assert injector.verify_applied()
    injector.remove()
    assert injector.verify_removed()


def test_cleanup_runs_after_scenario_exception() -> None:
    history: list[tuple[str, ...]] = []
    injector = FaultInjector(FaultSpec(type="stop_service", target="smf"), ok_runner(history))

    with pytest.raises(RuntimeError, match="scenario failed"):
        run_with_fault_cleanup(injector, failing_body)

    assert history[-1] == ("docker", "compose", "start", "smf")


def failing_body() -> None:
    raise RuntimeError("scenario failed")


def test_cleanup_reports_scenario_and_rollback_failures() -> None:
    def runner(command: tuple[str, ...], _timeout: int) -> subprocess.CompletedProcess[str]:
        if command == ("docker", "compose", "start", "smf"):
            return subprocess.CompletedProcess(command, 1, "", "start failed")
        return subprocess.CompletedProcess(command, 0, "", "")

    injector = FaultInjector(FaultSpec(type="stop_service", target="smf"), runner)

    with pytest.raises(
        RuntimeError, match="scenario failed: scenario failed; rollback failed: start failed"
    ):
        run_with_fault_cleanup(injector, failing_body)
