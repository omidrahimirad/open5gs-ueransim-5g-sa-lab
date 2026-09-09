from __future__ import annotations

from pathlib import Path

import pytest

from fiveg_lab.config import exposes_tun_device, load_yaml, mount_at

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("component", ["gnb", "ue"])
def test_ueransim_bypasses_component_wrapper_and_uses_mounted_config(component: str) -> None:
    # The inspected 3.3.0 wrapper shifts its first argument before dispatch and
    # treats nr-gnb/nr-ue as unknown components. This is static invocation
    # validation, not execution of the Linux binary or registration evidence.
    compose = load_yaml(REPO_ROOT / "docker-compose.yml")
    service = compose["services"][component]
    target = f"/UERANSIM/config/{component}.yaml"
    assert service["image"] == "${UERANSIM_IMAGE:-gradiant/ueransim:3.3.0}"
    assert service["entrypoint"] == [f"/usr/local/bin/nr-{component}"]
    assert service["command"] == ["-c", target]
    assert mount_at(service, target) == {
        "source": f"./configs/ueransim/{component}.yaml",
        "target": target,
        "type": "bind",
        "read_only": True,
    }


def test_ue_retains_scoped_tun_privileges_without_privileged_container() -> None:
    compose = load_yaml(REPO_ROOT / "docker-compose.yml")
    ue = compose["services"]["ue"]
    assert ue["user"] == "0:0"
    assert ue["cap_add"] == ["NET_ADMIN"]
    assert exposes_tun_device(ue["devices"])
    assert not ue.get("read_only", False)  # UE maintains /etc/iproute2/rt_tables.
    assert not load_yaml(REPO_ROOT / "configs/ueransim/ue.yaml").get("useNamespace", False)
    assert all(not service.get("privileged", False) for service in compose["services"].values())
