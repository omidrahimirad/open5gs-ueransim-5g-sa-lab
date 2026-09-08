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
CONTAINER_STATE_FIELD_COUNT = 4


@dataclass(frozen=True)
class ImpairmentRule:
    protocol: str
    port: str
    peer_ip: str
    preference: str
    handle: str


@dataclass(frozen=True)
class ContainerState:
    running: bool
    status: str
    started_at: str
    health: str


IMPAIRMENT_RULES = {
    "n2_impairment": ImpairmentRule(
        protocol="sctp",
        port="38412",
        peer_ip="10.45.0.20",
        preference="38412",
        handle="0x4e32",
    ),
    "n3_impairment": ImpairmentRule(
        protocol="udp",
        port="2152",
        peer_ip="10.45.0.30",
        preference="2152",
        handle="0x4e33",
    ),
}


@dataclass
class FaultInjector:
    fault: FaultSpec
    runner: CommandRunner
    applied: bool = False
    history: list[Command] = field(default_factory=list)
    cleanup_required: bool = False
    last_verification_error: str | None = None
    _created_clsact: bool = False
    _restart_started_at: str | None = None

    def apply(self) -> None:
        fault_type = self.fault.type
        if fault_type == "none":
            self.applied = True
            return
        if fault_type == "restart_service":
            service = validated_service(self.fault.target)
            before = self._container_state(service)
            if before is None or not before.running:
                msg = f"cannot restart {service}: container is not running"
                raise RuntimeError(msg)
            self._restart_started_at = before.started_at
            self._run(self.apply_commands()[0])
            self.applied = True
            return
        if fault_type == "stop_service":
            self._run(self.apply_commands()[0])
            self.cleanup_required = True
            self.applied = True
            return
        if fault_type in IMPAIRMENT_RULES:
            self._apply_impairment()
            return
        if fault_type in {
            "subscriber_key_mismatch",
            "unknown_subscriber",
            "dnn_mismatch",
            "snssai_mismatch",
        }:
            self.applied = True
            return
        msg = f"unsupported fault type: {fault_type}"
        raise ValueError(msg)

    def verify_applied(self) -> bool:
        self.last_verification_error = None
        try:
            if self.fault.type == "none":
                return True
            if self.fault.type == "stop_service":
                state = self._container_state(validated_service(self.fault.target))
                return state is not None and not state.running
            if self.fault.type == "restart_service":
                state = self._container_state(validated_service(self.fault.target))
                return (
                    state is not None
                    and state.running
                    and state.health != "unhealthy"
                    and bool(self._restart_started_at)
                    and state.started_at != self._restart_started_at
                )
            if self.fault.type in IMPAIRMENT_RULES:
                return self._impairment_rule_present()
            return False
        except (RuntimeError, ValueError) as exc:
            self.last_verification_error = str(exc)
            return False

    def remove(self) -> None:
        errors: list[str] = []
        for command in self.rollback_commands():
            try:
                self._run(command)
            except RuntimeError as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
        self.applied = False
        self.cleanup_required = False

    def verify_removed(self) -> bool:
        self.last_verification_error = None
        try:
            if self.fault.type == "none":
                return True
            if self.fault.type in {"stop_service", "restart_service"}:
                state = self._container_state(validated_service(self.fault.target))
                return state is not None and state.running and state.health != "unhealthy"
            if self.fault.type in IMPAIRMENT_RULES:
                rule_removed = not self._impairment_rule_present()
                if not self._created_clsact:
                    return rule_removed
                return rule_removed and not self._clsact_present()
            return False
        except (RuntimeError, ValueError) as exc:
            self.last_verification_error = str(exc)
            return False

    def apply_commands(self) -> list[Command]:
        fault_type = self.fault.type
        if fault_type == "none":
            return []
        if fault_type == "restart_service":
            return [("docker", "compose", "restart", validated_service(self.fault.target))]
        if fault_type == "stop_service":
            return [("docker", "compose", "stop", validated_service(self.fault.target))]
        if fault_type in IMPAIRMENT_RULES:
            return [self._clsact_add_command(), self._filter_add_command()]
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
        if fault_type in IMPAIRMENT_RULES:
            commands = [self._filter_delete_command()]
            if self._created_clsact:
                commands.append(self._clsact_delete_command())
            return commands
        return []

    def _apply_impairment(self) -> None:
        if not self._clsact_present():
            self._run(self._clsact_add_command())
            self._created_clsact = True
            self.cleanup_required = True
        self._run(self._filter_add_command())
        self.cleanup_required = True
        self.applied = True

    def _container_state(self, service: str) -> ContainerState | None:
        container = self._run(
            ("docker", "compose", "ps", "--all", "-q", service),
            timeout=10,
        ).stdout.strip()
        if not container:
            return None
        container_id = container.splitlines()[0]
        output = self._run(
            (
                "docker",
                "inspect",
                "--format",
                "{{.State.Running}}|{{.State.Status}}|{{.State.StartedAt}}|"
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                container_id,
            ),
            timeout=10,
        ).stdout.strip()
        parts = output.split("|", maxsplit=3)
        if len(parts) != CONTAINER_STATE_FIELD_COUNT:
            msg = f"unexpected docker inspect state for {service}: {output!r}"
            raise RuntimeError(msg)
        return ContainerState(
            running=parts[0].lower() == "true",
            status=parts[1],
            started_at=parts[2],
            health=parts[3],
        )

    def _clsact_present(self) -> bool:
        result = self._run(self._qdisc_show_command(), timeout=10)
        return "qdisc clsact" in result.stdout

    def _impairment_rule_present(self) -> bool:
        rule = impairment_rule(self.fault.type)
        output = self._run(self._filter_show_command(), timeout=10).stdout.lower()
        markers = (
            f"handle {rule.handle}",
            f"ip_proto {rule.protocol}",
            f"dst_ip {rule.peer_ip}",
            f"dst_port {rule.port}",
            "action drop",
        )
        return all(marker in output for marker in markers)

    def _qdisc_show_command(self) -> Command:
        return self._tc_command("qdisc", "show", "dev", self._interface())

    def _clsact_add_command(self) -> Command:
        return self._tc_command("qdisc", "add", "dev", self._interface(), "clsact")

    def _clsact_delete_command(self) -> Command:
        return self._tc_command("qdisc", "del", "dev", self._interface(), "clsact")

    def _filter_add_command(self) -> Command:
        rule = impairment_rule(self.fault.type)
        return self._tc_command(
            "filter",
            "add",
            "dev",
            self._interface(),
            "egress",
            "protocol",
            "ip",
            "pref",
            rule.preference,
            "handle",
            rule.handle,
            "flower",
            "ip_proto",
            rule.protocol,
            "dst_ip",
            rule.peer_ip,
            "dst_port",
            rule.port,
            "action",
            "drop",
        )

    def _filter_delete_command(self) -> Command:
        rule = impairment_rule(self.fault.type)
        return self._tc_command(
            "filter",
            "del",
            "dev",
            self._interface(),
            "egress",
            "protocol",
            "ip",
            "pref",
            rule.preference,
            "handle",
            rule.handle,
            "flower",
        )

    def _filter_show_command(self) -> Command:
        rule = impairment_rule(self.fault.type)
        return self._tc_command(
            "filter",
            "show",
            "dev",
            self._interface(),
            "egress",
            "pref",
            rule.preference,
        )

    def _tc_command(self, *args: str) -> Command:
        return (
            "docker",
            "compose",
            "exec",
            "-T",
            validated_service(self.fault.target),
            "tc",
            *args,
        )

    def _interface(self) -> str:
        return validated_interface(self.fault.value or "eth0")

    def _run(self, command: Command, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        self.history.append(command)
        result = self.runner(command, timeout)
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or f"command failed: {command}"
            raise RuntimeError(msg)
        return result


def default_runner(command: Command, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def impairment_rule(fault_type: str) -> ImpairmentRule:
    try:
        return IMPAIRMENT_RULES[fault_type]
    except KeyError as exc:
        msg = f"unsupported impairment type: {fault_type}"
        raise ValueError(msg) from exc


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
    body_error: BaseException | None = None
    try:
        body()
    except BaseException as exc:
        body_error = exc
    rollback_error: BaseException | None = None
    try:
        injector.remove()
    except BaseException as exc:
        rollback_error = exc
    if body_error and rollback_error:
        msg = f"scenario failed: {body_error}; rollback failed: {rollback_error}"
        raise RuntimeError(msg) from body_error
    if body_error:
        raise body_error
    if rollback_error:
        raise rollback_error
