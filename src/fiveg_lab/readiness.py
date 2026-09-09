"""Bounded, read-only checks of the running core; never a 5G baseline claim."""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fiveg_lab.config import OPEN5GS_NFS
from fiveg_lab.runtime_preflight import execute, output_text

CORE_SERVICES = ("mongodb", *OPEN5GS_NFS, "dn-server")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class ReadinessResult:
    passed: bool
    detail: str
    elapsed_seconds: float
    containers: dict[str, Any]
    logs: dict[str, str]

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")


def read_core(repo_root: Path, deadline: float) -> tuple[dict[str, Any], dict[str, str]]:
    def command(args: list[str]) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Core readiness deadline reached")
        result = execute(args, repo_root, timeout=max(1, min(10, math.ceil(remaining))))
        if result.returncode:
            raise RuntimeError(f"{' '.join(args)}: {output_text(result)}")
        return output_text(result)

    ids = command(["docker", "compose", "ps", "--all", "--quiet", "log-init", *CORE_SERVICES])
    if not ids:
        return {}, {}
    inspected = json.loads(command(["docker", "inspect", *ids.split()]))
    containers: dict[str, Any] = {}
    logs: dict[str, str] = {}
    for container in inspected:
        service = container["Config"]["Labels"]["com.docker.compose.service"]
        if service in containers:
            raise RuntimeError(f"Multiple containers for required service {service}")
        state = container["State"]
        # Keep only diagnostic runtime metadata, never environment/subscriber values.
        containers[service] = {
            "id": container["Id"],
            "image": container["Image"],
            "status": state["Status"],
            "started_at": state["StartedAt"],
            "exit_code": state["ExitCode"],
            "restart_count": container["RestartCount"],
            "health": state.get("Health", {}).get("Status"),
        }
        if service in OPEN5GS_NFS and state["Status"] != "created":
            logs[service] = ANSI.sub(
                "", command(["docker", "logs", "--since", state["StartedAt"], container["Id"]])
            )
    return containers, logs


def core_issues(containers: dict[str, Any], logs: dict[str, str]) -> tuple[list[str], list[str]]:
    fatal: list[str] = []
    pending: list[str] = []
    init = containers.get("log-init", {})
    if init.get("status") == "exited" and init.get("exit_code") != 0:
        fatal.append("log-init failed")
    elif init.get("status") != "exited" or init.get("exit_code") != 0:
        pending.append("log-init has not completed successfully")
    for service in CORE_SERVICES:
        state = containers.get(service, {})
        status = state.get("status", "missing")
        if state.get("restart_count", 0) != 0 or status in {"exited", "dead", "restarting"}:
            fatal.append(f"{service}: status={status}, restarts={state.get('restart_count')}")
            continue
        if status != "running":
            pending.append(f"{service}: {status}")
        if service == "mongodb" and state.get("health") != "healthy":
            pending.append("MongoDB is not healthy")
        if service in OPEN5GS_NFS:
            output = logs.get(service, "")
            if re.search(r"FATAL|Failed to initialize|unknown key `db_uri`", output):
                fatal.append(f"{service}: initialization error in current-process logs")
            if f"{service.upper()} initialize...done" not in output:
                pending.append(f"{service}: missing initialization success")
            if service not in {"nrf", "upf"} and "NF registered [Heartbeat:" not in output:
                pending.append(f"{service}: not registered with NRF")
            if service in {"smf", "upf"} and "PFCP associated" not in output:
                pending.append(f"{service}: PFCP association pending")
    return fatal, pending


def wait_core_ready(
    repo_root: Path, *, timeout: int = 120, stable_seconds: int = 30, interval: float = 2
) -> ReadinessResult:
    if timeout <= 0 or stable_seconds <= 0 or stable_seconds >= timeout or interval <= 0:
        raise ValueError("Require timeout > stable_seconds > 0 and interval > 0")
    started = time.monotonic()
    deadline = started + timeout
    stable_since: float | None = None
    identities: dict[str, tuple[str, str]] = {}
    containers: dict[str, Any] = {}
    logs: dict[str, str] = {}
    detail = "Core readiness timed out"
    passed = False
    try:
        while time.monotonic() < deadline:
            containers, logs = read_core(repo_root, deadline)
            fatal, pending = core_issues(containers, logs)
            for service in CORE_SERVICES:
                state = containers.get(service)
                if state and state["status"] == "running":
                    identity = (state["id"], state["started_at"])
                    if service in identities and identities[service] != identity:
                        fatal.append(f"{service}: container/process changed during readiness")
                    identities[service] = identity
            if fatal:
                detail = "; ".join(fatal)
                break
            now = time.monotonic()
            if pending:
                stable_since = None
                detail = "Core readiness timed out: " + "; ".join(pending)
            else:
                stable_since = now if stable_since is None else stable_since
                if now - stable_since >= stable_seconds and now < deadline:
                    passed = True
                    detail = (
                        f"Core initialized, MongoDB healthy, NRF/PFCP associations ready, "
                        f"and no restarts for {stable_seconds}s; not baseline validation"
                    )
                    break
                detail = "Core readiness timed out before the stability window completed"
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
    except (RuntimeError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
        detail = f"Core readiness failed: {error or 'interrupted'}"
    return ReadinessResult(passed, detail, round(time.monotonic() - started, 3), containers, logs)
