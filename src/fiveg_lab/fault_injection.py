from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

from fiveg_lab.scenarios import FaultSpec

Command = tuple[str, ...]
CommandRunner = Callable[[Command, int], subprocess.CompletedProcess[str]]
FaultBody = Callable[[], None]

ALLOWED_SERVICES = {"amf", "smf", "upf", "gnb", "ue"}
ALLOWED_CONTAINER_INTERFACES = {"eth0", "uesimtun0", "ogstun"}


@dataclass
class FaultInjector:
    fault: FaultSpec
    runner: CommandRunner
    applied: bool = False
    history: list[Command] = field(default_factory=list)

    def apply(self) -> None:
        for command in self.apply_commands():
            self._run(command)
        self.applied = True

    def verify_applied(self) -> bool:
        return self.applied

    def remove(self) -> None:
        for command in self.rollback_commands():
            self._run(command)
        self.applied = False

    def verify_removed(self) -> bool:
        return not self.applied

    def apply_commands(self) -> list[Command]:
        fault_type = self.fault.type
        if fault_type == "none":
            return []
        if fault_type == "restart_service":
            return [("docker", "compose", "restart", validated_service(self.fault.target))]
        if fault_type == "stop_service":
            return [("docker", "compose", "stop", validated_service(self.fault.target))]
        if fault_type in {"n2_impairment", "n3_impairment"}:
            service = validated_service(self.fault.target)
            interface = validated_interface(self.fault.value or "eth0")
            return [
                (
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    service,
                    "tc",
                    "qdisc",
                    "replace",
                    "dev",
                    interface,
                    "root",
                    "netem",
                    "loss",
                    "25%",
                )
            ]
        if fault_type in {
            "subscriber_key_mismatch",
            "unknown_subscriber",
            "dnn_mismatch",
            "snssai_mismatch",
        }:
            return []
        msg = f"unsupported fault type: {fault_type}"
        raise ValueError(msg)

    def rollback_commands(self) -> list[Command]:
        fault_type = self.fault.type
        if fault_type in {"none", "restart_service"}:
            return []
        if fault_type == "stop_service":
            return [("docker", "compose", "start", validated_service(self.fault.target))]
        if fault_type in {"n2_impairment", "n3_impairment"}:
            service = validated_service(self.fault.target)
            interface = validated_interface(self.fault.value or "eth0")
            return [
                (
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    service,
                    "tc",
                    "qdisc",
                    "del",
                    "dev",
                    interface,
                    "root",
                )
            ]
        return []

    def _run(self, command: Command) -> None:
        self.history.append(command)
        result = self.runner(command, 30)
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or f"command failed: {command}"
            raise RuntimeError(msg)


def default_runner(command: Command, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def validated_service(service: str | None) -> str:
    if service not in ALLOWED_SERVICES:
        msg = f"fault target must be one of {sorted(ALLOWED_SERVICES)}"
        raise ValueError(msg)
    return service


def validated_interface(interface: str) -> str:
    if interface not in ALLOWED_CONTAINER_INTERFACES:
        msg = f"network impairment interface must be one of {sorted(ALLOWED_CONTAINER_INTERFACES)}"
        raise ValueError(msg)
    return interface


def run_with_fault_cleanup(injector: FaultInjector, body: FaultBody) -> None:
    injector.apply()
    try:
        body()
    finally:
        injector.remove()
