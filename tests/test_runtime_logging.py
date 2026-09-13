from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fiveg_lab.config import (
    LOG_VOLUME,
    OPEN5GS_NFS,
    load_yaml,
    validate_container_runtime_contract,
    validate_upf_address_alignment,
)
from fiveg_lab.models import CheckStatus
from fiveg_lab.orchestration import parse_runtime_events

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "regression",
    [
        "bind_mount",
        "root_nf",
        "missing_dependency",
        "init_root",
        "init_script",
        "world_privileged_init",
        "sysctl",
        "entrypoint",
        "script_mount",
        "nat_setting",
    ],
)
def test_logging_and_full_bootstrap_contract_reject_regressions(regression: str) -> None:
    compose = load_yaml(REPO_ROOT / "docker-compose.yml")
    amf, upf, init = (compose["services"][name] for name in ("amf", "upf", "log-init"))
    match regression:
        case "bind_mount":
            amf["volumes"][-1] = "./logs:/var/log/open5gs"
        case "root_nf":
            amf["user"] = "0:0"
        case "missing_dependency":
            del amf["depends_on"]["log-init"]
        case "init_root":
            init["user"] = "999:999"
        case "init_script":
            init["entrypoint"] = ["true"]
        case "world_privileged_init":
            init["privileged"] = True
        case "sysctl":
            del upf["sysctls"]["net.ipv6.conf.all.disable_ipv6"]
        case "entrypoint":
            upf["entrypoint"] = ["/entrypoint.sh"]
        case "script_mount":
            upf["volumes"] = [item for item in upf["volumes"] if "/lab/" not in item]
        case "nat_setting":
            del upf["environment"]["ENABLE_NAT"]
    assert any(
        check.status == CheckStatus.FAIL for check in validate_container_runtime_contract(compose)
    )


def test_compose_keeps_fixture_logs_unmounted_and_non_root_nfs() -> None:
    compose = load_yaml(REPO_ROOT / "docker-compose.yml")
    assert LOG_VOLUME in compose["volumes"]
    for name, service in compose["services"].items():
        assert all(not mount.startswith("./logs:") for mount in service.get("volumes", []))
        if name in OPEN5GS_NFS and name != "upf":
            assert service["user"] == "999:999"


def test_log_initializer_preserves_content_and_never_changes_checkout(tmp_path: Path) -> None:
    volume = tmp_path / "volume"
    volume.mkdir(mode=0o755)
    existing = volume / "amf.log"
    existing.write_text("retain failed runtime observations\n")
    fixture = tmp_path / "sample.txt"
    fixture.write_text("immutable fixture")
    ownership_calls = tmp_path / "chown.jsonl"
    fake_chown = tmp_path / "chown"
    fake_chown.write_text(
        f"#!{sys.executable}\nimport json, sys\n"
        f"with open({str(ownership_calls)!r}, 'a') as out: "
        "out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
    )
    fake_chown.chmod(0o755)
    # Only the test copy substitutes an isolated directory. chown is mocked;
    # this exercises file preparation, not real container UID mapping.
    script = (
        (REPO_ROOT / "scripts/prepare_runtime_logs.sh")
        .read_text()
        .replace("/var/log/open5gs", str(volume))
    )
    result = subprocess.run(
        ["sh"],
        input=script,
        text=True,
        capture_output=True,
        env=os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert existing.read_text() == "retain failed runtime observations\n"
    assert fixture.read_text() == "immutable fixture"
    assert volume.stat().st_mode & 0o777 == 0o775
    calls = [json.loads(line) for line in ownership_calls.read_text().splitlines()]
    assert len(calls) == 1 + len(OPEN5GS_NFS)
    assert all(args[0] == "999:999" and Path(args[1]).is_relative_to(volume) for args in calls)
    assert all((volume / f"{nf}.log").stat().st_mode & 0o777 == 0o644 for nf in OPEN5GS_NFS)


def test_runtime_parser_ignores_fixtures_and_persistent_nf_history(
    tmp_path: Path,
) -> None:
    fixtures = tmp_path / "logs"
    fixtures.mkdir()
    (fixtures / "fake.log").write_text("2026-06-21T10:00:01Z [amf] INFO Registration Accept\n")
    assert parse_runtime_events(tmp_path) == []
    runtime = tmp_path / "runtime/logs/20260909T010000Z"
    (runtime / "nf-files").mkdir(parents=True)
    line = "2026-06-21T10:00:01Z [amf] INFO Registration Accept\n"
    (runtime / "nf-files/amf.log").write_text(line)
    assert parse_runtime_events(tmp_path) == []
    (runtime / "amf.log").write_text(line)
    assert parse_runtime_events(tmp_path).count("registration_accept") == 1


@pytest.mark.parametrize("key", ["IPV4_TUN_ADDR", "IPV4_TUN_SUBNET", "IPV6_TUN_ADDR"])
def test_upf_address_contract_rejects_mismatched_pool_or_invalid_ipv6(key: str) -> None:
    compose = load_yaml(REPO_ROOT / "docker-compose.yml")
    compose["services"]["upf"]["environment"][key] = "10.45.0.1/16"
    config = load_yaml(REPO_ROOT / "configs/open5gs/upf.yaml")
    assert any(
        check.status == CheckStatus.FAIL
        for check in validate_upf_address_alignment(compose, config)
    )


def test_log_initializer_refuses_symlink_without_touching_target(tmp_path: Path) -> None:
    volume = tmp_path / "volume"
    volume.mkdir()
    target = tmp_path / "private.txt"
    target.write_text("unchanged")
    (volume / "nrf.log").symlink_to(target)
    # Ownership behavior is covered by the scoped-call test, not exercised here.
    script = (
        (REPO_ROOT / "scripts/prepare_runtime_logs.sh")
        .read_text()
        .replace("/var/log/open5gs", str(volume))
        .replace('chown 999:999 "$log_dir"', ":")
    )
    result = subprocess.run(["sh"], input=script, text=True, capture_output=True, check=False)
    assert result.returncode != 0 and "LOG_DIRECTORY_READY" not in result.stdout
    assert "Refusing symlink" in result.stderr
    assert target.read_text() == "unchanged"
