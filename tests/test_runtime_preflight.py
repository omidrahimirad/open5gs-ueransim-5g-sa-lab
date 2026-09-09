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
from fiveg_lab.config import LOG_VOLUME, OPEN5GS_NFS, UPF_ENTRYPOINT, load_yaml
from fiveg_lab.models import ResultStatus

REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeDocker:
    """Fixture-only command responses; never executes Docker or a container."""

    def __init__(self) -> None:
        self.compose = load_yaml(REPO_ROOT / "docker-compose.yml")
        for name in ("log-init", *OPEN5GS_NFS):
            self.compose["services"][name]["image"] = "example/open5gs:configured"
        self.compose["volumes"][LOG_VOLUME] = {"name": f"{self.compose['name']}_{LOG_VOLUME}"}
        self.compose["services"]["mongodb"]["image"] = "mongo:8.3.8-noble"
        self.calls: list[list[str]] = []
        self.probes: list[dict[str, Any]] = []
        self.paths: list[Path] = []
        self.upf_result = (0, "UPF_BOOTSTRAP_PASS\n", "")
        self.log_result = (0, "RUNTIME_LOG_WRITE_PASS\n", "")
        self.init_result = (0, "LOG_DIRECTORY_READY\n", "")
        self.file_cleanup_ok = True
        self.interrupt_logs = False
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
            result = self.probe_result(args)
        elif args[1:3] == ["volume", "create"]:
            result = (0, args[-1], "")
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

    def probe_result(self, args: list[str]) -> tuple[int, str, str]:
        path = Path(args[args.index("-f") + 1])
        self.paths.append(path)
        probe = json.loads(path.read_text().replace("$$", "$"))["services"]["probe"]
        if args[args.index("--name") + 1].endswith("-cleanup"):
            return (0, "", "") if self.file_cleanup_ok else (1, "", "file unlink denied")
        self.probes.append(probe)
        if self.interrupt:
            raise KeyboardInterrupt
        if self.interrupt_logs and probe.get("environment", {}).get("PROBE_FILE"):
            raise KeyboardInterrupt
        if probe["command"] == []:
            return self.init_result
        if probe["command"] == ["--check"]:
            return self.upf_result
        if probe["image"].startswith("mongo:"):
            return self.mongo_result
        return self.log_result


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
    probe = next(item for item in docker.probes if item["command"] == ["--check"])
    for field in ("image", "user", "cap_add", "cap_drop", "devices", "security_opt", "sysctls"):
        assert probe[field] == upf[field]
    assert probe["network_mode"] == "none"
    assert not set(probe) & {"ports", "networks", "depends_on", "container_name"}
    assert probe["entrypoint"] == UPF_ENTRYPOINT
    assert {item["target"] for item in probe["volumes"]} == {
        "/var/log/open5gs",
        "/lab/upf-entrypoint.sh",
    }
    assert not probe.get("privileged", False)
    run = next(command for command in docker.calls if "run" in command)
    assert "--rm" in run and "--no-deps" in run
    assert run[run.index("--pull") + 1] == "never"
    name = run[run.index("--name") + 1]
    assert ["docker", "rm", "--force", "--volumes", name] in docker.calls
    assert any(command[-1] == f"name=^/{name}$" for command in docker.calls)
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
    capability = next(check for check in checks if check.name == "upf_bootstrap")
    assert capability.status == ResultStatus.FAIL
    assert (outcome[2] or outcome[1]) in capability.detail
    assert checks[-1].name == "probe_cleanup"
    assert checks[-1].status == ResultStatus.PASS
    assert not any(probe["image"].startswith("mongo:") for probe in docker.probes)


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
    mongo = docker.probes[-1]
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


@pytest.mark.parametrize("failure", ["write", "cleanup", "interrupt", "init"])
def test_runtime_log_probe_failure_blocks_bootstrap_and_checks_file_cleanup(
    docker: FakeDocker, failure: str
) -> None:
    if failure == "write":
        docker.log_result = (1, "uid=999(open5gs)", "touch: Permission denied")
    elif failure == "cleanup":
        docker.file_cleanup_ok = False
    elif failure == "interrupt":
        docker.interrupt_logs = True
    else:
        docker.init_result = (1, "", "chown: Operation not permitted")
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.FAIL
    assert not any(probe["command"] == ["--check"] for probe in docker.probes)
    if failure != "init":
        assert any(check.name == "probe_file_cleanup" for check in checks)
        assert any(
            "--name" in args and args[args.index("--name") + 1].endswith("-cleanup")
            for args in docker.calls
        )


def test_logging_probe_uses_actual_mount_and_effective_user_for_every_nf(
    docker: FakeDocker,
) -> None:
    assert rp.capability_status(rp.run_runtime_preflight(REPO_ROOT)) == ResultStatus.PASS
    logs = [probe for probe in docker.probes if probe.get("environment", {}).get("PROBE_FILE")]
    assert len(logs) == len(OPEN5GS_NFS)
    for probe in logs:
        name = probe["environment"]["NF_LOG_FILE"].removesuffix(".log")
        assert probe["user"] == docker.compose["services"][name]["user"]
        assert probe["volumes"] == [
            {
                "source": LOG_VOLUME,
                "target": "/var/log/open5gs",
                "type": "volume",
                "read_only": False,
            }
        ]


def test_old_tun_only_success_marker_cannot_satisfy_bootstrap(docker: FakeDocker) -> None:
    docker.upf_result = (0, "NET_ADMIN_TUN_PASS\n", "")
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.FAIL


def test_original_sysctl_permission_error_is_preserved(docker: FakeDocker) -> None:
    docker.upf_result = (
        255,
        "Creating ogstun device",
        "sysctl: permission denied on key net.ipv6.conf.all.disable_ipv6",
    )
    checks = rp.run_runtime_preflight(REPO_ROOT)
    assert rp.capability_status(checks) == ResultStatus.FAIL
    assert any("sysctl: permission denied" in check.detail for check in checks)


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
