from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fiveg_lab.config import (
    checks_pass,
    load_yaml,
    validate_repo,
    validate_ueransim_ue_startup_contract,
)
from fiveg_lab.models import CheckStatus

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repository_ue_uses_upstream_public_example_and_required_integrity_rates() -> None:
    ue = load_yaml(REPO_ROOT / "configs/ueransim/ue.yaml")
    # Public example in v3.3.0 config/open5gs-ue.yaml; not a subscriber secret.
    assert ue["homeNetworkPublicKey"] == (
        "5a8d38864820197c3394b92613b20b91633cbd897119273bf8e4a6f4eec0a650"
    )
    assert ue["protectionScheme"] == 0
    assert ue["integrityMaxRate"] == {"uplink": "full", "downlink": "full"}
    checks = {item.name: item.status for item in validate_repo(REPO_ROOT)}
    assert checks["ueransim_3_3_home_network_public_key"] == CheckStatus.PASS
    assert checks["ueransim_3_3_integrity_max_rate"] == CheckStatus.PASS


@pytest.mark.parametrize("key", ["a" * 65, "a" * 63, "g" * 64, "", None])
def test_null_protection_scheme_still_rejects_malformed_present_public_key(key: Any) -> None:
    ue = load_yaml(REPO_ROOT / "configs/ueransim/ue.yaml")
    ue["homeNetworkPublicKey"] = key
    assert not checks_pass(validate_ueransim_ue_startup_contract(ue))


def test_optional_public_key_can_be_omitted_for_null_scheme() -> None:
    ue = load_yaml(REPO_ROOT / "configs/ueransim/ue.yaml")
    del ue["homeNetworkPublicKey"]
    assert checks_pass(validate_ueransim_ue_startup_contract(ue))


@pytest.mark.parametrize(
    "rates",
    [None, {}, {"uplink": "full"}, {"downlink": "full"}, {"uplink": "full", "downlink": "bad"}],
)
def test_missing_or_invalid_integrity_rate_fields_fail_static_validation(rates: Any) -> None:
    ue = load_yaml(REPO_ROOT / "configs/ueransim/ue.yaml")
    if rates is None:
        del ue["integrityMaxRate"]
    else:
        ue["integrityMaxRate"] = rates
    assert not checks_pass(validate_ueransim_ue_startup_contract(ue))


def test_parser_supported_64kbps_integrity_rates_remain_valid() -> None:
    ue = load_yaml(REPO_ROOT / "configs/ueransim/ue.yaml")
    ue["integrityMaxRate"] = {"uplink": "64kbps", "downlink": "64kbps"}
    assert checks_pass(validate_ueransim_ue_startup_contract(ue))
