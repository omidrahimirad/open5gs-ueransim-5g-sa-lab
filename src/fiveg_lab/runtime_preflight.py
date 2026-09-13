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

from fiveg_lab.config import (
    LOG_TARGET,
    LOG_VOLUME,
    OPEN5GS_NFS,
    load_yaml,
    mount_at,
    validate_container_runtime_contract,
    validate_upf_address_alignment,
)
from fiveg_lab.models import CheckStatus, ResultStatus

# Copy the resolved service's process/capability settings, but never its lab
# networks, ports, dependencies, container name, or subscriber/config volumes.
# The actual runtime log volume is attached explicitly below.
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
LOG_SCRIPT = """set -eu
probe_file="/var/log/open5gs/$PROBE_FILE"
trap 'rm -f -- "$probe_file"' EXIT
trap 'exit 1' INT TERM
id
[ -w "/var/log/open5gs/$NF_LOG_FILE" ]
(umask 077; set -C; : > "$probe_file")
printf '%s\\n' runtime-write-check > "$probe_file"
rm -- "$probe_file"
[ ! -e "$probe_file" ]
trap - EXIT
echo RUNTIME_LOG_WRITE_PASS
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
        contract += validate_upf_address_alignment(
            compose, load_yaml(repo_root / "configs/open5gs/upf.yaml")
        )
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
    names = ["log-init", *OPEN5GS_NFS]
    if mongodb:
        names.append("mongodb")
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
    if capability_status(checks) != ResultStatus.PASS:
        return checks
    volume_name = compose["volumes"][LOG_VOLUME]["name"]
    prepared = execute(
        [
            "docker",
            "volume",
            "create",
            "--label",
            f"com.docker.compose.project={compose['name']}",
            "--label",
            f"com.docker.compose.volume={LOG_VOLUME}",
            volume_name,
        ],
        repo_root,
    )
    checks.append(
        CapabilityCheck(
            "runtime_log_volume",
            ResultStatus.PASS if prepared.returncode == 0 else ResultStatus.FAIL,
            f"Persistent lab log volume (retained): {volume_name}\n{output_text(prepared)}",
        )
    )
    plan = [("log-init", "init"), *((name, "logs") for name in OPEN5GS_NFS), ("upf", "bootstrap")]
    if mongodb:
        plan.append(("mongodb", "mongo"))
    for name, role in plan:
        if capability_status(checks) != ResultStatus.PASS:
            break
        checks.extend(run_probe(repo_root, name, services[name], role, volume_name))
    return checks


def interrupt_probe(_signum: int, _frame: FrameType | None) -> None:
    raise KeyboardInterrupt


def probe_service(
    settings: dict[str, Any], role: str, service: str, name: str
) -> tuple[dict[str, Any], str]:
    probe = {key: settings[key] for key in PROBE_SETTINGS if key in settings}
    probe.update({"network_mode": "none", "restart": "no", "healthcheck": {"disable": True}})
    if role == "mongo":
        probe.update({"entrypoint": ["/bin/sh"], "command": ["-ec", MONGO_SCRIPT]})
        return probe, "MONGODB_PING_PASS"
    # Reuse only the actual log volume and the exact read-only bootstrap script.
    # No subscriber/config volumes, service ports, or lab networks enter a probe.
    mounts = [mount_at(settings, LOG_TARGET)]
    if role in {"init", "bootstrap"}:
        target = settings["entrypoint"][1]
        mounts.append(mount_at(settings, target))
        probe["entrypoint"] = settings["entrypoint"]
        probe["command"] = [] if role == "init" else ["--check"]
        marker = "LOG_DIRECTORY_READY" if role == "init" else "UPF_BOOTSTRAP_PASS"
    else:
        probe["entrypoint"] = ["/bin/sh"]
        probe["command"] = ["-ec", LOG_SCRIPT]
        probe["environment"] = dict(probe.get("environment", {})) | {
            "PROBE_FILE": name,
            "NF_LOG_FILE": f"{service}.log",
        }
        marker = "RUNTIME_LOG_WRITE_PASS"
    probe["volumes"] = mounts
    return probe, marker


def run_probe(
    repo_root: Path, service: str, settings: dict[str, Any], role: str, volume_name: str
) -> list[CapabilityCheck]:
    name = f"open5gs-runtime-preflight-{uuid.uuid4().hex}"
    probe, marker = probe_service(settings, role, service, name)
    checks: list[CapabilityCheck] = []
    with tempfile.TemporaryDirectory(prefix="5g-lab-runtime-preflight-") as directory:
        path = Path(directory) / "compose.json"
        document = {"services": {"probe": probe}}
        if role != "mongo":
            document["volumes"] = {LOG_VOLUME: {"external": True, "name": volume_name}}
        # Resolved Compose values must not undergo a second environment expansion.
        path.write_text(json.dumps(document).replace("$", "$$"), encoding="utf-8")
        prefix = [
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
        ]
        previous = signal.signal(signal.SIGTERM, interrupt_probe)
        try:
            result = execute(
                prefix + ["--name", name, "probe"], repo_root, timeout=90 if role == "mongo" else 30
            )
            passed = result.returncode == 0 and marker in result.stdout.splitlines()
            checks.append(
                CapabilityCheck(
                    f"{service}_{role}",
                    ResultStatus.PASS if passed else ResultStatus.FAIL,
                    f"container={name}; exit={result.returncode}\n{output_text(result)}",
                )
            )
        except KeyboardInterrupt:
            checks.append(CapabilityCheck(f"{service}_{role}", ResultStatus.FAIL, "Interrupted"))
        finally:
            old_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            try:
                checks.append(cleanup_probe(repo_root, name))
                if role == "logs":
                    checks.extend(cleanup_log_file(repo_root, prefix, name))
            finally:
                signal.signal(signal.SIGINT, old_int)
                signal.signal(signal.SIGTERM, previous)
    return checks


def cleanup_log_file(repo_root: Path, prefix: list[str], name: str) -> list[CapabilityCheck]:
    # SIGKILL cannot run the container shell trap. Use the same effective user
    # and log mount to remove only this probe's unique file after container removal.
    cleanup_name = name + "-cleanup"
    filename = f"{LOG_TARGET}/{name}"
    result = execute(
        prefix
        + [
            "--name",
            cleanup_name,
            "--entrypoint",
            "/bin/sh",
            "probe",
            "-ec",
            f"rm -f -- {filename} && test ! -e {filename} && test ! -L {filename}",
        ],
        repo_root,
    )
    return [
        CapabilityCheck(
            "probe_file_cleanup",
            ResultStatus.PASS if result.returncode == 0 else ResultStatus.FAIL,
            f"file={filename}; exit={result.returncode}\n{output_text(result)}",
        ),
        cleanup_probe(repo_root, cleanup_name),
    ]


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
