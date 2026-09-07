from __future__ import annotations

import platform
import shutil
import socket
import subprocess
from pathlib import Path

from fiveg_lab.models import Check, CheckStatus

MIN_FREE_DISK_GIB = 5.0


def run_command(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)


def command_check(name: str, command: str, required: bool) -> Check:
    found = shutil.which(command) is not None
    if found:
        return Check(name, CheckStatus.PASS, f"{command} found")
    return Check(name, CheckStatus.FAIL if required else CheckStatus.WARN, f"{command} not found")


def run_preflight() -> list[Check]:
    checks: list[Check] = []
    is_linux = platform.system() == "Linux"
    checks.append(
        Check(
            "linux_os",
            CheckStatus.PASS if is_linux else CheckStatus.FAIL,
            f"detected={platform.system()} {platform.machine()}",
        )
    )
    checks.append(command_check("docker_installed", "docker", required=True))
    checks.append(command_check("iproute2_available", "ip", required=True))
    checks.append(command_check("ss_available", "ss", required=False))
    checks.append(command_check("tc_available", "tc", required=False))
    checks.append(command_check("tcpdump_available", "tcpdump", required=False))
    checks.append(command_check("tshark_available", "tshark", required=False))
    checks.append(command_check("jq_available", "jq", required=False))
    checks.append(command_check("curl_available", "curl", required=False))
    checks.append(command_check("ping_available", "ping", required=True))

    if shutil.which("docker"):
        result = run_command(["docker", "compose", "version"])
        checks.append(
            Check(
                "docker_compose_available",
                CheckStatus.PASS if result.returncode == 0 else CheckStatus.FAIL,
                result.stdout.strip() or result.stderr.strip() or "docker compose did not respond",
            )
        )

    tun = Path("/dev/net/tun")
    checks.append(
        Check(
            "tun_device",
            CheckStatus.PASS if tun.exists() and tun.is_char_device() else CheckStatus.FAIL,
            "/dev/net/tun exists" if tun.exists() else "/dev/net/tun missing",
        )
    )
    checks.append(check_sctp(is_linux))
    checks.append(check_ip_forward(is_linux))
    checks.append(check_ports([7777, 38412]))
    checks.append(check_disk_space(Path.cwd()))
    return checks


def check_sctp(is_linux: bool) -> Check:
    if not is_linux:
        return Check("sctp_kernel_support", CheckStatus.FAIL, "SCTP requires a Linux runtime")
    modules = Path("/proc/modules")
    if modules.exists() and "sctp" in modules.read_text(encoding="utf-8", errors="ignore"):
        return Check("sctp_kernel_support", CheckStatus.PASS, "sctp module listed in /proc/modules")
    if shutil.which("modinfo") and run_command(["modinfo", "sctp"]).returncode == 0:
        return Check("sctp_kernel_support", CheckStatus.PASS, "sctp module available")
    return Check("sctp_kernel_support", CheckStatus.FAIL, "SCTP module not visible")


def check_ip_forward(is_linux: bool) -> Check:
    if not is_linux:
        return Check("ip_forwarding", CheckStatus.WARN, "Linux sysctl unavailable on this host")
    path = Path("/proc/sys/net/ipv4/ip_forward")
    if not path.exists():
        return Check("ip_forwarding", CheckStatus.FAIL, "ip_forward sysctl missing")
    enabled = path.read_text(encoding="utf-8").strip() == "1"
    return Check(
        "ip_forwarding",
        CheckStatus.PASS if enabled else CheckStatus.WARN,
        "enabled" if enabled else "disabled on host; UPF container still sets its own sysctl",
    )


def check_ports(ports: list[int]) -> Check:
    conflicts: list[str] = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                conflicts.append(str(port))
    return Check(
        "host_port_conflicts",
        CheckStatus.WARN if conflicts else CheckStatus.PASS,
        "in_use=" + ",".join(conflicts) if conflicts else "no TCP conflicts detected",
    )


def check_disk_space(path: Path) -> Check:
    usage = shutil.disk_usage(path)
    free_gib = usage.free / (1024**3)
    return Check(
        "disk_space",
        CheckStatus.PASS if free_gib >= MIN_FREE_DISK_GIB else CheckStatus.WARN,
        f"free_gib={free_gib:.1f}",
    )


def checks_pass(checks: list[Check]) -> bool:
    return all(check.status != CheckStatus.FAIL for check in checks)
