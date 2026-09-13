from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from fiveg_lab.config import LAB_DB_URI, load_yaml, validate_repo
from fiveg_lab.models import CheckStatus

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    target.mkdir()
    shutil.copy2(REPO_ROOT / "docker-compose.yml", target)
    shutil.copytree(REPO_ROOT / "configs", target / "configs")
    return target


def failed_names(repo: Path) -> set[str]:
    return {item.name for item in validate_repo(repo) if item.status == CheckStatus.FAIL}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.mark.parametrize("timer", [None, 0, -540, True, "540", 540.5, 541, 63, 64, 35712001])
def test_missing_or_unencodable_amf_periodic_timer_is_rejected(repo: Path, timer: Any) -> None:
    path = repo / "configs/open5gs/amf.yaml"
    data = load_yaml(path)
    if timer is None:
        data["amf"].pop("time", None)
    else:
        data["amf"]["time"] = {"t3512": {"value": timer}}
    write_yaml(path, data)

    assert "open5gs_2_8_amf_t3512" in failed_names(repo)


@pytest.mark.parametrize("timer", [2, 62, 90, 540, 1860, 18600, 111600, 1116000, 35712000])
def test_supported_amf_periodic_timer_is_accepted(repo: Path, timer: int) -> None:
    path = repo / "configs/open5gs/amf.yaml"
    data = load_yaml(path)
    data["amf"]["time"] = {"t3512": {"value": timer}}
    write_yaml(path, data)

    assert "open5gs_2_8_amf_t3512" not in failed_names(repo)


@pytest.mark.parametrize("name", ["pcf", "udr"])
@pytest.mark.parametrize("change", ["nested_only", "duplicate_nested", "missing", "wrong_host"])
def test_database_uri_must_use_supported_root_key(repo: Path, name: str, change: str) -> None:
    path = repo / f"configs/open5gs/{name}.yaml"
    data = load_yaml(path)
    if change in {"nested_only", "missing"}:
        data.pop("db_uri", None)
    if change in {"nested_only", "duplicate_nested"}:
        data[name]["db_uri"] = LAB_DB_URI
    if change == "wrong_host":
        data["db_uri"] = "mongodb://mongo/open5gs"
    write_yaml(path, data)

    assert f"open5gs_2_8_{name}_db_uri" in failed_names(repo)


@pytest.mark.parametrize("name", ["pcf", "udr"])
@pytest.mark.parametrize(
    "environment",
    [None, {}, {"DB_URI": "mongodb://mongo/open5gs"}, {"DB_URI": None}, ["DB_URI"]],
)
def test_correct_yaml_cannot_mask_inherited_wrong_database_environment(
    repo: Path, name: str, environment: Any
) -> None:
    path = repo / "docker-compose.yml"
    data = load_yaml(path)
    if environment is None:
        data["services"][name].pop("environment", None)
    else:
        data["services"][name]["environment"] = environment
    write_yaml(path, data)

    failures = failed_names(repo)
    assert f"open5gs_2_8_{name}_db_environment" in failures
    assert f"open5gs_2_8_{name}_db_uri" not in failures


def test_explicit_database_environment_list_syntax_is_accepted(repo: Path) -> None:
    path = repo / "docker-compose.yml"
    data = load_yaml(path)
    for name in ("pcf", "udr"):
        data["services"][name]["environment"] = [f"DB_URI={LAB_DB_URI}"]
    write_yaml(path, data)

    assert not failed_names(repo)
