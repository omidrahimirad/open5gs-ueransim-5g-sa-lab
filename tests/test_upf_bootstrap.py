from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# These executables model command outcomes only. No Linux network operation,
# capability, iptables rule, or real interface is exercised by this fixture.
FAKE_NETWORK_TOOL = r"""
import json, os, sys
from pathlib import Path
path = Path(os.environ["PROBE_STATE"])
state = json.loads(path.read_text())
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
state["calls"].append([tool, *args])
mode = os.environ.get("FAIL_STEP", "")
code = 0
output = ""
if tool == "sysctl":
    if args[0] != "-n":
        code, output = 255, "sysctl: permission denied"
    else:
        key = args[1]
        output = "1" if key == "net.ipv4.ip_forward" else "0"
        if mode == "sysctl" and key == "net.ipv6.conf.all.disable_ipv6": output = "1"
elif tool == "ip":
    if args[:2] == ["link", "show"]: code = 0 if state.get("tun") else 1
    elif args[:2] == ["tuntap", "add"]: state["tun"] = True
    elif args[:3] == ["link", "set", "ogstun"]:
        if mode == "link_up": code = 1
        else: state["up"] = True
    elif args[:2] == ["link", "del"]:
        if mode == "tun_cleanup": code = 1
        else: state["tun"] = False
    elif args[:3] == ["-4", "addr", "replace"]: state["ipv4"] = args[3]
    elif args[:3] == ["-6", "addr", "replace"]:
        if mode == "ipv6_address": code = 1
        else: state["ipv6"] = args[3]
    elif args[:3] == ["-o", "-4", "addr"]:
        output = "1: ogstun inet " + state.get("ipv4", "") + " scope global"
        if mode == "partial_read_failure": code = 1
    elif args[:3] == ["-o", "-6", "addr"]:
        output = "1: ogstun inet6 " + state.get("ipv6", "") + " scope global"
    elif args[:3] == ["-o", "link", "show"]:
        output = "1: ogstun: "
        output += "<POINTOPOINT,UP,LOWER_UP>" if state.get("up") else "<LOWER_UP>"
    else: code = 99
elif tool == "iptables":
    if "-A" in args:
        if mode == "nat_add": code = 1
        else: state["nat"] = True
    elif "-C" in args:
        code = 0 if state.get("nat") and mode != "nat_verify" else 1
    elif "-D" in args:
        if mode == "nat_cleanup": code = 1
        else: state["nat"] = False
    else: code = 99
elif tool == "open5gs-upfd":
    state["daemon_started"] = True
    code = 0 if state.get("tun") and state.get("up") else 1
elif tool != "sleep": code = 99
path.write_text(json.dumps(state))
print(output)
sys.exit(code)
"""


def run_bootstrap(
    tmp_path: Path, *, failure: str = "", nat: str = "true", check: bool = True
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name in ("ip", "sysctl", "iptables", "sleep", "open5gs-upfd"):
        path = binaries / name
        path.write_text(f"#!{sys.executable}\n" + FAKE_NETWORK_TOOL)
        path.chmod(0o755)
    state = tmp_path / "state.json"
    state.write_text('{"calls": []}')
    environment = os.environ | {
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "PROBE_STATE": str(state),
        "FAIL_STEP": failure,
        "IPV4_TUN_ADDR": "10.45.1.1/24",
        "IPV4_TUN_SUBNET": "10.45.1.0/24",
        "IPV6_TUN_ADDR": "cafe::1/64",
        "ENABLE_NAT": nat,
    }
    result = subprocess.run(
        [
            "sh",
            str(REPO_ROOT / "scripts/upf-entrypoint.sh"),
            "--check" if check else "open5gs-upfd",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, json.loads(state.read_text())


def test_full_bootstrap_checks_addresses_forwarding_nat_and_cleanup(tmp_path: Path) -> None:
    result, state = run_bootstrap(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "UPF_BOOTSTRAP_PASS" in result.stdout
    assert state["ipv4"] == "10.45.1.1/24" and state["ipv6"] == "cafe::1/64"
    assert state["up"] and not state["tun"] and not state["nat"]
    sysctls = [call for call in state["calls"] if call[0] == "sysctl"]
    assert len(sysctls) == 4
    assert all(call[1] == "-n" for call in sysctls)


@pytest.mark.parametrize(
    "failure",
    [
        "sysctl",
        "ipv6_address",
        "link_up",
        "nat_add",
        "nat_verify",
        "partial_read_failure",
        "tun_cleanup",
        "nat_cleanup",
    ],
)
def test_failed_bootstrap_or_cleanup_never_emits_pass(tmp_path: Path, failure: str) -> None:
    result, _state = run_bootstrap(tmp_path, failure=failure)
    assert result.returncode != 0
    assert "UPF_BOOTSTRAP_PASS" not in result.stdout


def test_nat_can_be_explicitly_disabled_without_iptables(tmp_path: Path) -> None:
    result, state = run_bootstrap(tmp_path, nat="false")
    assert result.returncode == 0
    assert not any(call[0] == "iptables" for call in state["calls"])


def test_normal_startup_executes_daemon_with_initialized_tunnel(tmp_path: Path) -> None:
    result, state = run_bootstrap(tmp_path, check=False)
    assert result.returncode == 0
    assert state["daemon_started"] and state["tun"] and state["nat"]
    assert "UPF_BOOTSTRAP_PASS" not in result.stdout
