from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import tempfile
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any

from fiveg_lab.config import validate_container_runtime_contract
from fiveg_lab.models import CheckStatus, ResultStatus

# Copy the resolved service's process/capability settings, but never its lab
# networks, ports, dependencies, container name, or persistent/config volumes.
PROBE_SETTINGS = (
    "image",
    "platform",
    "user",
    "cap_add",
    "cap_drop",
    "devices",
    "privileged",
    "security_opt",
    "userns_mode",
    "group_add",
    "sysctls",
    "read_only",
    "environment",
)
TUN_SCRIPT = """set -eu
cleanup() { ip link del labchecktun 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 1' INT TERM
id
grep '^CapEff:' /proc/self/status
ip tuntap add dev labchecktun mode tun
ip link show labchecktun
ip link del labchecktun
if ip link show labchecktun >/dev/null 2>&1; then
    echo 'TUN cleanup failed' >&2
    exit 1
fi
trap - EXIT
echo NET_ADMIN_TUN_PASS
"""
MONGO_SCRIPT = """set -eu
docker-entrypoint.sh mongod --bind_ip 127.0.0.1 &
mongo_pid=$!
cleanup() { kill "$mongo_pid" 2>/dev/null || true; wait "$mongo_pid" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 1' INT TERM
attempt=0
while [ "$attempt" -lt 30 ]; do
    if ! kill -0 "$mongo_pid" 2>/dev/null; then
        echo 'MongoDB exited before readiness; inspect startup output above' >&2
        exit 1
    fi
    if mongosh --quiet --host 127.0.0.1 --eval \
        'quit(db.runCommand({ping:1}).ok === 1 ? 0 : 1)'; then
        echo MONGODB_PING_PASS
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 1
done
echo 'MongoDB did not become ready within the smoke-check window' >&2
exit 1
"""


@dataclass(frozen=True)
class CapabilityCheck:
    name: str
    status: ResultStatus
    detail: str


def execute(
    args: list[str], repo_root: Path, timeout: int = 15
) -> subprocess.CompletedProcess[str]:
    try:
        with subprocess.Popen(
            args,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                stop_process_group(process)
                stdout, stderr = process.communicate()
                return subprocess.CompletedProcess(
                    args, 124, stdout, f"{stderr}\nTimed out after {timeout}s"
                )
            except BaseException:
                stop_process_group(process)
                process.communicate()
                raise
            return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    except OSError as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


def stop_process_group(process: subprocess.Popen[str]) -> None:
    # Docker invokes the Compose plugin as a child. Stop both before inspecting
    # cleanup, otherwise the child could create a container after the check ends.
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)


def output_text(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout + "\n" + result.stderr).strip()


def capability_status(checks: list[CapabilityCheck]) -> ResultStatus:
    if any(check.status == ResultStatus.FAIL for check in checks):
        return ResultStatus.FAIL
    if any(check.status == ResultStatus.BLOCKED for check in checks):
        return ResultStatus.BLOCKED
    return ResultStatus.PASS


def runtime_tools(repo_root: Path) -> CapabilityCheck:
    if platform.system() != "Linux":
        return CapabilityCheck(
            "linux_runtime", ResultStatus.BLOCKED, "Run this check on the Linux lab host."
        )
    daemon = execute(["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"], repo_root)
    daemon_platform = daemon.stdout.strip().replace("x86_64", "amd64").replace("aarch64", "arm64")
    if daemon.returncode or not daemon_platform.startswith("linux/"):
        return CapabilityCheck("docker_runtime", ResultStatus.BLOCKED, output_text(daemon))
    compose = execute(["docker", "compose", "version"], repo_root)
    if compose.returncode:
        return CapabilityCheck("docker_compose", ResultStatus.BLOCKED, output_text(compose))
    return CapabilityCheck("docker_runtime", ResultStatus.PASS, daemon_platform)


def run_runtime_preflight(repo_root: Path, *, mongodb: bool = False) -> list[CapabilityCheck]:
    environment = runtime_tools(repo_root)
    if environment.status != ResultStatus.PASS:
        return [environment]
    daemon_platform = environment.detail
    resolved = execute(["docker", "compose", "config", "--format", "json"], repo_root)
    if resolved.returncode:
        return [CapabilityCheck("resolved_compose", ResultStatus.FAIL, output_text(resolved))]
    try:
        compose = json.loads(resolved.stdout)
        contract = validate_container_runtime_contract(compose)
        services = compose["services"]
    except (ValueError, KeyError, TypeError) as error:
        return [CapabilityCheck("resolved_compose", ResultStatus.FAIL, str(error))]
    failures = [
        CapabilityCheck(check.name, ResultStatus.FAIL, check.detail)
        for check in contract
        if check.status == CheckStatus.FAIL
    ]
    if failures:
        return failures
    names = ["upf", "mongodb"] if mongodb else ["upf"]
    checks = [environment]
    for name in names:
        image = str(services[name]["image"])
        inspected = execute(
            ["docker", "image", "inspect", "--format", "{{.Os}}/{{.Architecture}} {{.Id}}", image],
            repo_root,
        )
        detail = inspected.stdout.strip()
        if inspected.returncode or not detail.startswith(daemon_platform + " "):
            checks.append(
                CapabilityCheck(
                    f"{name}_image",
                    ResultStatus.BLOCKED,
                    f"Need a local native {daemon_platform} image: {image}. "
                    f"Pull the configured image explicitly, then retry. {output_text(inspected)}",
                )
            )
        else:
            checks.append(CapabilityCheck(f"{name}_image", ResultStatus.PASS, f"{image}: {detail}"))
    if capability_status(checks) == ResultStatus.PASS:
        for name in names:
            checks.extend(run_probe(repo_root, name, services[name]))
            if capability_status(checks) != ResultStatus.PASS:
                break
    return checks


def interrupt_probe(_signum: int, _frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def run_probe(repo_root: Path, service: str, settings: dict[str, Any]) -> list[CapabilityCheck]:
    name = f"open5gs-runtime-preflight-{uuid.uuid4().hex}"
    marker = "NET_ADMIN_TUN_PASS" if service == "upf" else "MONGODB_PING_PASS"
    script = TUN_SCRIPT if service == "upf" else MONGO_SCRIPT
    probe = {key: settings[key] for key in PROBE_SETTINGS if key in settings}
    probe.update({"network_mode": "none", "restart": "no", "healthcheck": {"disable": True}})
    checks: list[CapabilityCheck] = []
    with tempfile.TemporaryDirectory(prefix="5g-lab-runtime-preflight-") as directory:
        path = Path(directory) / "compose.json"
        path.write_text(json.dumps({"services": {"probe": probe}}), encoding="utf-8")
        previous = signal.signal(signal.SIGTERM, interrupt_probe)
        try:
            result = execute(
                [
                    "docker",
                    "compose",
                    "-p",
                    name,
                    "-f",
                    str(path),
                    "run",
                    "--rm",
                    "--no-deps",
                    "--pull",
                    "never",
                    "-T",
                    "--name",
                    name,
                    "--entrypoint",
                    "/bin/sh",
                    "probe",
                    "-ec",
                    script,
                ],
                repo_root,
                timeout=90 if service == "mongodb" else 30,
            )
            passed = result.returncode == 0 and marker in result.stdout.splitlines()
            checks.append(
                CapabilityCheck(
                    f"{service}_capability",
                    ResultStatus.PASS if passed else ResultStatus.FAIL,
                    f"container={name}; exit={result.returncode}\n{output_text(result)}",
                )
            )
        except KeyboardInterrupt:
            checks.append(
                CapabilityCheck(f"{service}_capability", ResultStatus.FAIL, "Interrupted")
            )
        finally:
            # A failed/timed-out Docker CLI can leave its container running.
            # Ignore repeat interrupts only while bounded cleanup is attempted.
            old_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            try:
                checks.append(cleanup_probe(repo_root, name))
            finally:
                signal.signal(signal.SIGINT, old_int)
                signal.signal(signal.SIGTERM, previous)
    return checks


def cleanup_probe(repo_root: Path, name: str) -> CapabilityCheck:
    removed = execute(["docker", "rm", "--force", "--volumes", name], repo_root)
    remaining = execute(
        ["docker", "ps", "--all", "--quiet", "--filter", f"name=^/{name}$"], repo_root
    )
    if remaining.returncode == 0 and not remaining.stdout.strip():
        return CapabilityCheck("probe_cleanup", ResultStatus.PASS, f"Container absent: {name}")
    return CapabilityCheck(
        "probe_cleanup",
        ResultStatus.FAIL,
        f"CLEANUP FAILED for {name}; retry docker rm --force --volumes {name}.\n"
        f"{output_text(removed)}\n{output_text(remaining)}",
    )
