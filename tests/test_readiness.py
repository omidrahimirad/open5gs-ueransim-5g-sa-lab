from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from fiveg_lab import readiness as rd


def healthy() -> tuple[dict[str, Any], dict[str, str]]:
    containers = {
        service: {
            "id": service,
            "started_at": "2026-09-09T00:00:00Z",
            "status": "running",
            "restart_count": 0,
            "health": "healthy" if service == "mongodb" else None,
        }
        for service in rd.CORE_SERVICES
    }
    containers["log-init"] = {"status": "exited", "exit_code": 0}
    logs = {
        service: f"{service.upper()} initialize...done\n"
        "NF registered [Heartbeat:10s]\nPFCP associated"
        for service in rd.OPEN5GS_NFS
    }
    return containers, logs


@pytest.mark.parametrize(
    "failure", ["restart", "exited", "fatal_log", "init", "initialization", "nrf", "pfcp", "mongo"]
)
def test_uptime_alone_cannot_pass(failure: str) -> None:
    containers, logs = healthy()
    match failure:
        case "restart":
            containers["pcf"]["restart_count"] = 1
        case "exited":
            containers["udr"]["status"] = "exited"
        case "fatal_log":
            logs["amf"] += "\nFATAL Open5GS initialization failed"
        case "init":
            containers["log-init"]["exit_code"] = 1
        case "initialization":
            logs["amf"] = ""
        case "nrf":
            logs["pcf"] = "PCF initialize...done"
        case "pfcp":
            logs["upf"] = "UPF initialize...done"
        case "mongo":
            containers["mongodb"]["health"] = "starting"
    fatal, pending = rd.core_issues(containers, logs)
    assert fatal or pending


@pytest.mark.parametrize(
    ("service", "loss", "recovery"),
    [
        ("pcf", "NF de-registered", "NF registered [Heartbeat:10s]"),
        ("udr", "Retry registration with NRF", "NF registered [Heartbeat:10s]"),
        ("smf", "PFCP de-associated", "PFCP associated"),
        ("upf", "No Heartbeat from SMF", "PFCP associated"),
    ],
)
def test_later_association_loss_invalidates_historical_success(
    service: str, loss: str, recovery: str
) -> None:
    containers, logs = healthy()
    logs[service] += "\n" + loss
    assert rd.core_issues(containers, logs)[1]
    logs[service] += "\n" + recovery
    assert rd.core_issues(containers, logs) == ([], [])


def clock(monkeypatch: MonkeyPatch) -> list[float]:
    now = [0.0]
    monkeypatch.setattr(rd.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(rd.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def test_ready_requires_full_stability_window(monkeypatch: MonkeyPatch) -> None:
    now = clock(monkeypatch)
    monkeypatch.setattr(rd, "read_core", lambda *_args: healthy())
    result = rd.wait_core_ready(Path(), timeout=10, stable_seconds=3, interval=1)
    assert result.passed and now[0] == 3
    assert "not baseline" in result.detail


def test_missing_services_timeout_without_pass(monkeypatch: MonkeyPatch) -> None:
    now = clock(monkeypatch)
    monkeypatch.setattr(rd, "read_core", lambda *_args: ({}, {}))
    result = rd.wait_core_ready(Path(), timeout=5, stable_seconds=3, interval=1)
    assert not result.passed and now[0] == 5
    assert "missing" in result.detail


def test_container_replacement_during_window_fails(monkeypatch: MonkeyPatch) -> None:
    now = clock(monkeypatch)

    def read(*_args: object) -> tuple[dict[str, Any], dict[str, str]]:
        containers, logs = healthy()
        containers["amf"]["id"] = "old" if now[0] == 0 else "replacement"
        return containers, logs

    monkeypatch.setattr(rd, "read_core", read)
    result = rd.wait_core_ready(Path(), timeout=10, stable_seconds=3, interval=1)
    assert not result.passed and "changed" in result.detail


def test_read_failure_cannot_reuse_healthy_snapshot(monkeypatch: MonkeyPatch) -> None:
    now = clock(monkeypatch)

    def read(*_args: object) -> tuple[dict[str, Any], dict[str, str]]:
        if now[0]:
            raise RuntimeError("Docker unavailable")
        return healthy()

    monkeypatch.setattr(rd, "read_core", read)
    result = rd.wait_core_ready(Path(), timeout=10, stable_seconds=3, interval=1)
    assert not result.passed and "Docker unavailable" in result.detail


def test_snapshot_uses_current_process_logs_without_recording_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    clock(monkeypatch)
    calls: list[list[str]] = []
    container: dict[str, Any] = {
        "Id": "current-id",
        "Image": "sha256:fixture",
        "RestartCount": 0,
        "Config": {"Labels": {"com.docker.compose.service": "amf"}, "Env": ["PRIVATE=hidden"]},
        "State": {"Status": "running", "StartedAt": "2026-09-09T00:00:00Z", "ExitCode": 0},
    }

    def execute(args: list[str], _root: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        assert 0 < timeout <= 10
        calls.append(args)
        if args[1] == "compose":
            value = "current-id"
        elif args[1] == "inspect":
            value = json.dumps([copy.deepcopy(container)])
        else:
            assert args == [
                "docker",
                "logs",
                "--since",
                container["State"]["StartedAt"],
                "current-id",
            ]
            value = "AMF initialize...done"
        return subprocess.CompletedProcess(args, 0, value, "")

    monkeypatch.setattr(rd, "execute", execute)
    containers, logs = rd.read_core(Path(), 10)
    assert logs["amf"] == "AMF initialize...done"
    assert "PRIVATE" not in json.dumps(containers)
    assert len(calls) == 3
