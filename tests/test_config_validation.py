from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from fiveg_lab.config import validate_repo
from fiveg_lab.models import CheckStatus

REPO_ROOT = Path(__file__).resolve().parents[1]


def copy_repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"
        ),
    )
    return target


def failed_names(repo: Path) -> set[str]:
    return {check.name for check in validate_repo(repo) if check.status == CheckStatus.FAIL}


def test_current_repository_configuration_passes_static_validation() -> None:
    assert not failed_names(REPO_ROOT)


def test_plmn_mismatch_is_detected(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    ue_path = repo / "configs/ueransim/ue.yaml"
    data = yaml.safe_load(ue_path.read_text(encoding="utf-8"))
    data["mcc"] = "999"
    ue_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    assert "mcc_consistent" in failed_names(repo)


def test_tac_mismatch_is_detected(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    gnb_path = repo / "configs/ueransim/gnb.yaml"
    data = yaml.safe_load(gnb_path.read_text(encoding="utf-8"))
    data["tac"] = 999
    gnb_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    assert "tac_consistent" in failed_names(repo)


def test_dnn_mismatch_is_detected(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    ue_path = repo / "configs/ueransim/ue.yaml"
    data = yaml.safe_load(ue_path.read_text(encoding="utf-8"))
    data["sessions"][0]["apn"] = "ims"
    ue_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    assert "dnn_consistent" in failed_names(repo)


def test_duplicate_ip_is_detected(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    compose_path = repo / "docker-compose.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    data["services"]["ue"]["networks"]["core"]["ipv4_address"] = "10.45.0.40"
    compose_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    assert "unique_static_container_ips" in failed_names(repo)


def test_invalid_subscriber_key_is_detected(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    subscriber_path = repo / "configs/subscriber_config.yaml"
    data = yaml.safe_load(subscriber_path.read_text(encoding="utf-8"))
    data["subscriber"]["key"] = "bad-key"
    subscriber_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    assert "subscriber_key_format" in failed_names(repo)


def test_open5gs_2_8_pcf_is_required_by_static_mode_check(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    compose_path = repo / "docker-compose.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    del data["services"]["pcf"]
    compose_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    failures = failed_names(repo)
    assert "required_network_functions" in failures
    assert "open5gs_2_8_pcf_required_mode" in failures


def test_nssf_omission_requires_matching_smf_discovery_metadata(tmp_path: Path) -> None:
    repo = copy_repo(tmp_path)
    smf_path = repo / "configs/open5gs/smf.yaml"
    data = yaml.safe_load(smf_path.read_text(encoding="utf-8"))
    data["smf"]["info"][0]["s_nssai"][0]["dnn"] = ["wrong-dnn"]
    smf_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    assert "open5gs_2_8_nssf_bypass_mode" in failed_names(repo)
