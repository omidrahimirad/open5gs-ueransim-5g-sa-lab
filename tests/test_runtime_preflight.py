from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from pytest import CaptureFixture, MonkeyPatch

from fiveg_lab import runtime_preflight as rp
from fiveg_lab.cli import main
from fiveg_lab.config import load_yaml
from fiveg_lab.models import ResultStatus

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeDocker:
    """Fixture-only command responses; never executes Docker or a container."""

    def __init__(self) -> None:
        self.compose = load_yaml(REPO_ROOT / "docker-compose.yml")
        self.compose["services"]["upf"]["image"] = "example/open5gs:configured"
        self.compose["services"]["mongodb"]["image"] = "mongo:8.3.8-noble"
        self.calls: list[list[str]] = []
        self.probes: list[dict[str, Any]] = []
        self.paths: list[Path] = []
        self.upf_result = (0, "NET_ADMIN_TUN_PASS\n", "")
        self.mongo_result = (0, "MONGODB_PING_PASS\n", "")
        self.daemon_ok = True
        self.compose_ok = True
        self.config_ok = True
        self.image_ok = True
        self.image_platform = "linux/amd64"
        self.interrupt = False
        self.cleanup_state = "absent"

    def __call__(
        self, args: list[str], repo_root: Path, timeout: int = 15
    ) -> subprocess.CompletedProcess[str]:
        assert repo_root == REPO_ROOT
        assert 0 < timeout <= 90
        self.calls.append(args)
        result = (0, "", "")
        if args[1] == "info":
            result = (0, "linux/x86_64\n", "") if self.daemon_ok else (1, "", "daemon unavailable")
        elif args[1:3] == ["compose", "version"]:
            result = (0, "Docker Compose version fixture", "")
            if not self.compose_ok:
                result = (1, "", "compose plugin missing")
        elif args[1:4] == ["compose", "config", "--format"]:
            result = (0, json.dumps(self.compose), "")
            if not self.config_ok:
                result = (1, "", "services.upf.devices must be a list")
        elif args[1:3] == ["image", "inspect"]:
            result = (0, f"{self.image_platform} sha256:fixture-only\n", "")
            if not self.image_ok:
                result = (1, "", "No such image")
        elif args[1] == "compose" and "run" in args:
            path = Path(args[args.index("-f") + 1])
            self.paths.append(path)
            probe = json.loads(path.read_text())["services"]["probe"]
            self.probes.append(probe)
            if self.interrupt:
                raise KeyboardInterrupt
            result = self.mongo_result if probe["image"].startswith("mongo:") else self.upf_result
        elif args[1] == "rm":
            result = (1, "", "No such container")
        elif args[1] == "ps":
            result = {
                "present": (0, "fixture-container-id\n", ""),
                "unknown": (1, "", "daemon unavailable during cleanup"),
                "absent": (0, "", ""),
            }[self.cleanup_state]
        else:
            pytest.fail(f"Unexpected command: {args}")
        return subprocess.CompletedProcess(args, *result)


@pytest.fixture
def docker(monkeypatch: MonkeyPatch) -> FakeDocker:
    fake = FakeDocker()
    monkeypatch.setattr(rp.platform, "system", lambda: "Linux")
    monkeypatch.setattr(rp, "execute", fake)
    return fake


def test_non_linux_is_blocked_without_docker_access(
    docker: FakeDocker, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(rp.platform, "system", lambda: "Darwin")
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.BLOCKED
    assert not docker.calls


@pytest.mark.parametrize("missing", ["daemon", "compose", "image", "native_architecture"])
def test_missing_runtime_prerequisites_block_without_startup(
    docker: FakeDocker, missing: str
) -> None:
    if missing == "daemon":
        docker.daemon_ok = False
    elif missing == "compose":
        docker.compose_ok = False
    elif missing == "image":
        docker.image_ok = False
    else:
        docker.image_platform = "linux/arm64"
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.BLOCKED
    assert not docker.probes


def test_invalid_compose_reports_fail_instead_of_missing_prerequisite(docker: FakeDocker) -> None:
    docker.config_ok = False
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.FAIL
    assert "devices must be a list" in checks[0].detail
    assert not docker.probes


def test_resolved_override_cannot_remove_root_contract(docker: FakeDocker) -> None:
    docker.compose["services"]["upf"]["user"] = "999:999"
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.FAIL
    assert any(check.name == "upf_explicit_root_user" for check in checks)
    assert not docker.probes


def test_tun_probe_preserves_privileges_without_lab_resources(docker: FakeDocker) -> None:
    upf = docker.compose["services"]["upf"]
    upf["cap_drop"] = ["SYS_ADMIN"]
    upf["security_opt"] = ["no-new-privileges:true"]
    original_handlers = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.PASS
    probe = docker.probes[0]
    for field in ("image", "user", "cap_add", "cap_drop", "devices", "security_opt", "sysctls"):
        assert probe[field] == upf[field]
    assert probe["network_mode"] == "none"
    assert not set(probe) & {"volumes", "ports", "networks", "depends_on", "container_name"}
    assert not probe.get("privileged", False)
    run = next(command for command in docker.calls if "run" in command)
    assert "--rm" in run and "--no-deps" in run
    assert run[run.index("--pull") + 1] == "never"
    name = run[run.index("--name") + 1]
    assert ["docker", "rm", "--force", "--volumes", name] in docker.calls
    assert docker.calls[-1][-1] == f"name=^/{name}$"
    assert all(not path.exists() for path in docker.paths)
    assert original_handlers == (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))


@pytest.mark.parametrize(
    "outcome",
    [
        (1, "CapEff: 0000000000000000", "ioctl(TUNSETIFF): Operation not permitted"),
        (0, "interface creation did not report success", ""),
        (124, "", "Timed out after 30s"),
    ],
)
def test_tun_failure_is_reported_and_cleanup_runs(
    docker: FakeDocker, outcome: tuple[int, str, str]
) -> None:
    docker.upf_result = outcome
    checks = rp.run_runtime_preflight(REPO_ROOT, mongodb=True)
    assert rp.capability_status(checks) == ResultStatus.FAIL
    capability = next(check for check in checks if check.name == "upf_capability")
    assert capability.status == ResultStatus.FAIL
    assert (outcome[2] or outcome[1]) in capability.detail
    assert checks[-1].name == "probe_cleanup"
    assert checks[-1].status == ResultStatus.PASS
    assert len(docker.probes) == 1  # Stop before MongoDB after a failed UPF check.


@pytest.mark.parametrize("state", ["present", "unknown"])
def test_cleanup_failure_overrides_success(docker: FakeDocker, state: str) -> None:
    docker.cleanup_state = state
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.FAIL
    assert "CLEANUP FAILED" in checks[-1].detail
    assert "docker rm --force --volumes open5gs-runtime-preflight-" in checks[-1].detail


def test_interrupted_probe_cleans_up_and_restores_handlers(docker: FakeDocker) -> None:
    docker.interrupt = True
    handler = signal.getsignal(signal.SIGTERM)
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.FAIL
    assert checks[-1].name == "probe_cleanup"
    assert checks[-1].status == ResultStatus.PASS
    assert signal.getsignal(signal.SIGTERM) == handler
    assert all(not path.exists() for path in docker.paths)


@pytest.mark.parametrize("healthy", [True, False])
def test_optional_mongodb_smoke_uses_configured_environment_and_isolated_data(
    docker: FakeDocker, healthy: bool
) -> None:
    if not healthy:
        docker.mongo_result = (1, "", "MongoDB exited before readiness")
    checks = rp.run_runtime_preflight(REPO_ROOT, mongodb=True)
    assert rp.capability_status(checks) == (ResultStatus.PASS if healthy else ResultStatus.FAIL)
    mongo = docker.probes[1]
    assert mongo["environment"] == docker.compose["services"]["mongodb"]["environment"]
    assert mongo["image"] == "mongo:8.3.8-noble"
    assert "volumes" not in mongo and "networks" not in mongo and "ports" not in mongo
    assert checks[-1].name == "probe_cleanup"
    assert checks[-1].status == ResultStatus.PASS


def test_cli_reports_capability_failure_without_claiming_baseline(
    docker: FakeDocker, capsys: CaptureFixture[str]
) -> None:
    docker.upf_result = (1, "", "ioctl(TUNSETIFF): Operation not permitted")
    status = main(["--repo-root", str(REPO_ROOT), "runtime-preflight"])
    assert status == 1
    output = capsys.readouterr().out
    assert "Operation not permitted" in output
    assert "not baseline validation" in output


def test_timeout_stops_child_process_before_cleanup_and_preserves_output(tmp_path: Path) -> None:
    # Real local process-control test, not Docker/Linux-runtime evidence. A child
    # models the Compose plugin creating resources after its parent times out.
    marker = tmp_path / "orphan-created-resource"
    child = (
        "import time; from pathlib import Path; time.sleep(2); "
        f"Path({str(marker)!r}).write_text('unexpected orphan')"
    )
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "print('partial output', flush=True); print('failure', file=sys.stderr, flush=True); "
        "time.sleep(30)"
    )
    result = rp.execute([sys.executable, "-c", parent], REPO_ROOT, timeout=1)
    assert result.returncode == 124
    assert "partial output" in result.stdout
    assert "failure" in result.stderr and "Timed out after 1s" in result.stderr
    time.sleep(1.5)
    assert not marker.exists()
