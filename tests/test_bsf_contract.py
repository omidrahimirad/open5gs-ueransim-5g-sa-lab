from pathlib import Path

import pytest

from fiveg_lab.config import OPEN5GS_NFS, load_yaml, validate_bsf_contract
from fiveg_lab.models import CheckStatus
from fiveg_lab.readiness import CORE_SERVICES

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "regression", ["missing", "address", "nrf", "command", "dependency", "mount"]
)
def test_required_bsf_binding_service_contract(regression: str) -> None:
    compose = load_yaml(ROOT / "docker-compose.yml")
    config = load_yaml(ROOT / "configs/open5gs/bsf.yaml")
    assert validate_bsf_contract(compose, config)[0].status == CheckStatus.PASS
    match regression:
        case "missing":
            del compose["services"]["bsf"]
        case "address":
            config["bsf"]["sbi"]["server"][0]["address"] = "127.0.0.15"
        case "nrf":
            config["bsf"]["sbi"]["client"]["nrf"][0]["uri"] = "http://127.0.0.10:7777"
        case "command":
            compose["services"]["bsf"]["command"] = ["true"]
        case "dependency":
            del compose["services"]["pcf"]["depends_on"]["bsf"]
        case "mount":
            compose["services"]["bsf"]["volumes"] = []
    assert validate_bsf_contract(compose, config)[0].status == CheckStatus.FAIL


def test_bsf_is_included_in_log_probes_and_core_readiness() -> None:
    assert "bsf" in OPEN5GS_NFS and "bsf" in CORE_SERVICES
    service = load_yaml(ROOT / "docker-compose.yml")["services"]["bsf"]
    assert service["user"] == "999:999"
    assert not service.get("privileged", False)
