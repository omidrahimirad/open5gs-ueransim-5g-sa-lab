from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from fiveg_lab.assertions import evaluate_scenario_events, scenario_status
from fiveg_lab.config import checks_pass as config_checks_pass
from fiveg_lab.config import load_yaml, validate_repo
from fiveg_lab.evidence import environment_manifest, make_run_id, utc_now, write_result
from fiveg_lab.fault_injection import Command, CommandRunner, FaultInjector
from fiveg_lab.models import (
    AssertionResult,
    CheckStatus,
    ClaimLevel,
    EvidenceRef,
    ResultStatus,
    ScenarioResult,
)
from fiveg_lab.parser import parse_file
from fiveg_lab.preflight import checks_pass as preflight_checks_pass
from fiveg_lab.preflight import run_preflight
from fiveg_lab.scenarios import Scenario

BASELINE_CONTEXT_SCHEMA_VERSION = 1
IMAGE_DEFAULT_RE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*):-([^}]+)}$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
RUNTIME_CONTEXT_PATHS = (
    "docker-compose.yml",
    "configs/subscriber_config.yaml",
)
REQUIRED_RUNTIME_SERVICES = (
    "mongodb",
    "nrf",
    "ausf",
    "udm",
    "udr",
    "pcf",
    "amf",
    "smf",
    "upf",
    "dn-server",
    "gnb",
    "ue",
)


@dataclass(frozen=True)
class CommandOutcome:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class BaselineGate:
    passed: bool
    reason: str


@dataclass(frozen=True)
class RecoveryValidation:
    status: ResultStatus
    assertions: list[AssertionResult]
    outcomes: list[CommandOutcome]
    evidence_paths: list[Path]


def run_runtime_scenario(
    repo_root: Path,
    scenario: Scenario,
    output_root: Path,
    baseline_result: Path | None,
    settle_seconds: int = 20,
) -> ScenarioResult:
    started_at = utc_now()
    run_id = make_run_id(scenario.id, started_at)
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    context = runtime_context_manifest(repo_root)
    fingerprint = context_fingerprint(context)
    (output_dir / "environment.json").write_text(
        json.dumps(environment_manifest(scenario.id), indent=2), encoding="utf-8"
    )
    (output_dir / "versions.json").write_text(
        json.dumps(version_manifest(repo_root), indent=2), encoding="utf-8"
    )
    (output_dir / "runtime_context.json").write_text(
        json.dumps(context, indent=2, sort_keys=True), encoding="utf-8"
    )

    blocked = blocking_reason(repo_root)
    if blocked:
        result = blocked_result(scenario, run_id, started_at, blocked, fingerprint)
        write_result(result, output_dir)
        return result

    if scenario.id != "baseline_e2e":
        gate = validate_baseline_result(baseline_result, fingerprint)
        if not gate.passed:
            result = blocked_result(
                scenario,
                run_id,
                started_at,
                [gate.reason],
                fingerprint,
            )
            write_result(result, output_dir)
            return result

    if scenario.id == "baseline_e2e":
        result = execute_baseline(
            repo_root,
            scenario,
            output_dir,
            run_id,
            started_at,
            fingerprint,
            settle_seconds,
        )
    else:
        result = execute_fault_scenario(
            repo_root,
            scenario,
            output_dir,
            run_id,
            started_at,
            fingerprint,
            settle_seconds,
        )
    write_result(result, output_dir)
    return result


def blocking_reason(repo_root: Path) -> list[str]:
    reasons: list[str] = []
    preflight = run_preflight()
    config = validate_repo(repo_root)
    if not preflight_checks_pass(preflight):
        reasons.extend(
            f"{check.name}: {check.detail}"
            for check in preflight
            if check.status == CheckStatus.FAIL
        )
    if not config_checks_pass(config):
        reasons.extend(
            f"{check.name}: {check.detail}" for check in config if check.status == CheckStatus.FAIL
        )
    return reasons


def blocked_result(
    scenario: Scenario,
    run_id: str,
    started_at: str,
    reasons: list[str],
    fingerprint: str | None = None,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario.id,
        run_id=run_id,
        started_at=started_at,
        status=ResultStatus.BLOCKED,
        baseline_ready=False,
        fault_applied=False,
        expected_failure_observed=False,
        recovery_attempted=False,
        recovery_status=ResultStatus.BLOCKED,
        observed_events=[],
        assertions=[],
        baseline_context_fingerprint=fingerprint,
        notes=["Runtime scenario was not executed."] + reasons,
    )


def execute_baseline(
    repo_root: Path,
    scenario: Scenario,
    output_dir: Path,
    run_id: str,
    started_at: str,
    fingerprint: str,
    settle_seconds: int,
) -> ScenarioResult:
    outcomes = [
        run_command(["./scripts/start_lab.sh"], repo_root, scenario.timeout_seconds),
        run_command(["./scripts/add_subscriber.sh"], repo_root, scenario.timeout_seconds),
        run_command(
            ["docker", "compose", "--profile", "ran", "up", "-d", "gnb", "ue"],
            repo_root,
            scenario.timeout_seconds,
        ),
    ]
    time.sleep(settle_seconds)
    traffic_path = output_dir / "traffic_result.txt"
    outcomes.append(
        run_command(
            ["./scripts/traffic_test.sh"],
            repo_root,
            scenario.timeout_seconds,
            env={"OUT": str(traffic_path)},
        )
    )
    outcomes.append(run_command(["./scripts/collect_logs.sh"], repo_root, scenario.timeout_seconds))
    write_command_log(outcomes, output_dir / "commands.json")
    events = parse_runtime_events(repo_root, traffic_path)
    assertions = evaluate_scenario_events(scenario, set(events))
    status = (
        ResultStatus.ERROR
        if any(outcome.returncode != 0 for outcome in outcomes)
        else scenario_status(assertions)
    )
    return ScenarioResult(
        scenario_id=scenario.id,
        run_id=run_id,
        started_at=started_at,
        status=status,
        baseline_ready=status == ResultStatus.PASS,
        fault_applied=False,
        expected_failure_observed=False,
        recovery_attempted=False,
        recovery_status=ResultStatus.SKIPPED,
        observed_events=sorted(set(events)),
        assertions=assertions,
        baseline_context_fingerprint=fingerprint,
        evidence=runtime_evidence(output_dir, traffic_path),
        notes=command_notes(outcomes),
    )


def execute_fault_scenario(  # noqa: PLR0912, PLR0915
    repo_root: Path,
    scenario: Scenario,
    output_dir: Path,
    run_id: str,
    started_at: str,
    fingerprint: str,
    settle_seconds: int,
) -> ScenarioResult:
    if scenario.fault.type in {
        "subscriber_key_mismatch",
        "unknown_subscriber",
        "dnn_mismatch",
        "snssai_mismatch",
    }:
        result = blocked_result(
            scenario,
            run_id,
            started_at,
            [
                "This config/subscriber mutation fault is defined and assertion-tested, "
                "but runtime mutation is intentionally not automated yet."
            ],
            fingerprint,
        )
        result.evidence.append(
            EvidenceRef(
                kind="scenario_definition",
                path=f"scenarios/{scenario.id}.yaml",
                claim_level=ClaimLevel.STATIC_VERIFIED,
                description="Declarative expected/forbidden event contract.",
            )
        )
        return result

    outcomes: list[CommandOutcome] = []
    notes: list[str] = []
    fault_applied = False
    fault_verified = False
    rollback_verified = False
    recovery_attempted = False
    infrastructure_error: str | None = None
    rollback_error: str | None = None
    injector = FaultInjector(scenario.fault, compose_runner(repo_root))
    traffic_path = output_dir / "fault_traffic_result.txt"

    try:
        injector.apply()
        fault_applied = injector.applied
        if not injector.verify_applied():
            detail = injector.last_verification_error or "runtime state did not match the fault"
            raise RuntimeError(f"fault apply verification failed: {detail}")
        fault_verified = True
        time.sleep(settle_seconds)
        outcomes.append(
            run_command(
                ["./scripts/traffic_test.sh"],
                repo_root,
                scenario.timeout_seconds,
                env={"OUT": str(traffic_path)},
            )
        )
        outcomes.append(
            run_command(["./scripts/collect_logs.sh"], repo_root, scenario.timeout_seconds)
        )
    except (RuntimeError, subprocess.SubprocessError, TimeoutError) as exc:
        infrastructure_error = str(exc)
    finally:
        if injector.applied or injector.cleanup_required:
            recovery_attempted = True
            try:
                injector.remove()
            except (RuntimeError, subprocess.SubprocessError, TimeoutError) as exc:
                rollback_error = str(exc)
            else:
                rollback_verified = injector.verify_removed()
                if not rollback_verified:
                    rollback_error = (
                        injector.last_verification_error
                        or "fault removal verification did not match runtime state"
                    )

    recovery = RecoveryValidation(ResultStatus.SKIPPED, [], [], [])
    if fault_verified and rollback_verified:
        recovery = validate_recovered_baseline(repo_root, output_dir, scenario.timeout_seconds)
        outcomes.extend(recovery.outcomes)

    write_command_log(outcomes, output_dir / "commands.json")
    events = parse_runtime_events(repo_root, traffic_path)
    assertions = evaluate_scenario_events(scenario, set(events))
    fault_status = scenario_status(assertions)
    expected_failure_observed = fault_status == ResultStatus.PASS

    if infrastructure_error:
        notes.append(f"Fault scenario infrastructure failed: {infrastructure_error}")
    if rollback_error:
        notes.append(f"Rollback failed or could not be verified: {rollback_error}")
    notes.extend(command_notes(outcomes))

    if infrastructure_error:
        status = ResultStatus.ERROR
    elif rollback_error or not rollback_verified:
        status = ResultStatus.FAIL
    else:
        status = fault_status
    if recovery.status != ResultStatus.PASS:
        status = ResultStatus.FAIL if status != ResultStatus.ERROR else status

    return ScenarioResult(
        scenario_id=scenario.id,
        run_id=run_id,
        started_at=started_at,
        status=status,
        baseline_ready=True,
        fault_applied=fault_applied,
        expected_failure_observed=expected_failure_observed,
        recovery_attempted=recovery_attempted,
        recovery_status=recovery.status,
        observed_events=sorted(set(events)),
        assertions=assertions,
        baseline_context_fingerprint=fingerprint,
        fault_verified=fault_verified,
        rollback_verified=rollback_verified,
        recovery_assertions=recovery.assertions,
        recovery_verified=recovery.status == ResultStatus.PASS,
        evidence=runtime_evidence(output_dir, traffic_path, *recovery.evidence_paths),
        notes=notes,
    )


def validate_recovered_baseline(
    repo_root: Path,
    output_dir: Path,
    timeout: int,
) -> RecoveryValidation:
    assertions: list[AssertionResult] = []
    outcomes: list[CommandOutcome] = []
    evidence_paths: list[Path] = []

    compose_ps = run_command(["docker", "compose", "--profile", "ran", "ps"], repo_root, timeout)
    outcomes.append(compose_ps)
    compose_ps_path = output_dir / "post_recovery_compose_ps.txt"
    write_outcome(compose_ps, compose_ps_path)
    evidence_paths.append(compose_ps_path)

    missing_services: list[str] = []
    for service in REQUIRED_RUNTIME_SERVICES:
        outcome = run_command(
            [
                "docker",
                "compose",
                "--profile",
                "ran",
                "ps",
                "--status",
                "running",
                "-q",
                service,
            ],
            repo_root,
            timeout,
        )
        outcomes.append(outcome)
        if outcome.returncode != 0 or not outcome.stdout.strip():
            missing_services.append(service)
    assertions.append(
        state_assertion(
            "recovery:required_lab_services_running",
            not missing_services,
            "all required 5GC, RAN, UE, and DN services running",
            "all running" if not missing_services else f"missing/not running: {missing_services}",
        )
    )

    gnb_status = run_ueransim_cli(repo_root, "gnb", "status", timeout)
    outcomes.extend(gnb_status[:2])
    gnb_status_path = output_dir / "post_recovery_gnb_status.txt"
    write_outcome(gnb_status[-1], gnb_status_path)
    evidence_paths.append(gnb_status_path)
    assertions.append(
        state_assertion(
            "recovery:n2_ready",
            gnb_status[-1].returncode == 0
            and bool(re.search(r"is-ngap-up:\s*true", gnb_status[-1].stdout, re.I)),
            "UERANSIM gNB reports is-ngap-up: true",
            gnb_status[-1].stdout.strip() or gnb_status[-1].stderr.strip() or "no status",
        )
    )

    ue_status = run_ueransim_cli(repo_root, "ue", "status", timeout)
    outcomes.extend(ue_status[:2])
    ue_status_path = output_dir / "post_recovery_ue_status.txt"
    write_outcome(ue_status[-1], ue_status_path)
    evidence_paths.append(ue_status_path)
    assertions.append(
        state_assertion(
            "recovery:ue_registered",
            ue_status[-1].returncode == 0
            and bool(re.search(r"rm-state:\s*RM-REGISTERED", ue_status[-1].stdout, re.I)),
            "UERANSIM UE reports RM-REGISTERED",
            ue_status[-1].stdout.strip() or ue_status[-1].stderr.strip() or "no status",
        )
    )

    pdu_status = run_ueransim_cli(repo_root, "ue", "ps-list", timeout)
    outcomes.extend(pdu_status[:2])
    pdu_status_path = output_dir / "post_recovery_pdu_sessions.txt"
    write_outcome(pdu_status[-1], pdu_status_path)
    evidence_paths.append(pdu_status_path)
    assertions.append(
        state_assertion(
            "recovery:pdu_session_active",
            pdu_status[-1].returncode == 0
            and bool(re.search(r"state:\s*PS-ACTIVE(?:\s|$)", pdu_status[-1].stdout, re.I)),
            "UERANSIM UE reports a PS-ACTIVE PDU session",
            pdu_status[-1].stdout.strip() or pdu_status[-1].stderr.strip() or "no session",
        )
    )

    tunnel = run_command(
        ["docker", "compose", "exec", "-T", "ue", "ip", "link", "show", "uesimtun0"],
        repo_root,
        timeout,
    )
    outcomes.append(tunnel)
    tunnel_path = output_dir / "post_recovery_ue_tunnel.txt"
    write_outcome(tunnel, tunnel_path)
    evidence_paths.append(tunnel_path)
    assertions.append(
        state_assertion(
            "recovery:ue_tunnel_exists",
            tunnel.returncode == 0 and "uesimtun0" in tunnel.stdout,
            "uesimtun0 exists in the UE container",
            tunnel.stdout.strip() or tunnel.stderr.strip() or "not found",
        )
    )

    traffic_path = output_dir / "recovery_traffic_result.txt"
    traffic = run_command(
        ["./scripts/traffic_test.sh"],
        repo_root,
        timeout,
        env={"OUT": str(traffic_path)},
    )
    outcomes.append(traffic)
    evidence_paths.append(traffic_path)
    assertions.append(
        state_assertion(
            "recovery:user_plane_dn_traffic",
            traffic.returncode == 0
            and traffic_path.exists()
            and "USER_PLANE_SUCCESS" in traffic_path.read_text(encoding="utf-8"),
            "interface-bound traffic reaches the lab DN target",
            "success" if traffic.returncode == 0 else f"exit {traffic.returncode}",
        )
    )

    assertions_path = output_dir / "recovery_assertions.json"
    assertions_path.write_text(
        json.dumps([asdict(assertion) for assertion in assertions], indent=2), encoding="utf-8"
    )
    evidence_paths.append(assertions_path)
    return RecoveryValidation(scenario_status(assertions), assertions, outcomes, evidence_paths)


def run_ueransim_cli(
    repo_root: Path, service: str, subcommand: str, timeout: int
) -> tuple[CommandOutcome, CommandOutcome]:
    dump = run_command(
        ["docker", "compose", "exec", "-T", service, "nr-cli", "--dump"],
        repo_root,
        timeout,
    )
    node_names = [line.strip() for line in dump.stdout.splitlines() if line.strip()]
    if dump.returncode != 0 or not node_names:
        error = CommandOutcome(
            args=["nr-cli", "<node>", "--exec", subcommand],
            returncode=dump.returncode or 1,
            stdout="",
            stderr=dump.stderr.strip() or f"no UERANSIM node found in {service}",
        )
        return dump, error
    result = run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            service,
            "nr-cli",
            node_names[0],
            "--exec",
            subcommand,
        ],
        repo_root,
        timeout,
    )
    return dump, result


def state_assertion(name: str, passed: bool, expected: str, observed: str) -> AssertionResult:
    return AssertionResult(
        name=name,
        status=ResultStatus.PASS if passed else ResultStatus.FAIL,
        expected=expected,
        observed=observed,
        detail="Runtime state matched the recovery invariant."
        if passed
        else "Runtime state did not match the recovery invariant.",
    )


def compose_runner(repo_root: Path) -> CommandRunner:
    def runner(command: Command, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(command),
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    return runner


def run_command(
    args: list[str],
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> CommandOutcome:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged_env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout
        return CommandOutcome(
            args=args,
            returncode=124,
            stdout=stdout or "",
            stderr=f"timeout after {timeout}s",
        )
    return CommandOutcome(
        args=args, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr
    )


def latest_log_dir(logs_root: Path) -> Path | None:
    candidates = [path for path in logs_root.glob("20*T*Z") if path.is_dir()]
    return sorted(candidates)[-1] if candidates else None


def parse_runtime_events(repo_root: Path, *extra_logs: Path) -> list[str]:
    log_paths = list((latest_log_dir(repo_root / "logs") or (repo_root / "logs")).glob("*.log"))
    log_paths.extend(path for path in extra_logs if path.exists())
    return [event.event for path in log_paths for event in parse_file(path)]


def write_command_log(outcomes: list[CommandOutcome], path: Path) -> None:
    path.write_text(
        json.dumps([asdict(outcome) for outcome in outcomes], indent=2), encoding="utf-8"
    )


def write_outcome(outcome: CommandOutcome, path: Path) -> None:
    command = " ".join(outcome.args)
    path.write_text(
        f"command: {command}\nreturncode: {outcome.returncode}\n"
        f"stdout:\n{outcome.stdout}\nstderr:\n{outcome.stderr}",
        encoding="utf-8",
    )


def command_notes(outcomes: list[CommandOutcome]) -> list[str]:
    notes: list[str] = []
    for outcome in outcomes:
        if outcome.returncode != 0:
            notes.append(f"Command failed: {' '.join(outcome.args)}")
            if outcome.stderr.strip():
                notes.append(outcome.stderr.strip())
    return notes


def validate_baseline_result(  # noqa: PLR0911
    path: Path | None, expected_fingerprint: str
) -> BaselineGate:
    if path is None:
        return BaselineGate(False, "baseline_e2e result is required before fault scenarios run.")
    if not path.exists():
        return BaselineGate(False, f"baseline result does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return BaselineGate(False, f"malformed baseline result: {exc}")
    if not isinstance(data, dict):
        return BaselineGate(False, "malformed baseline result: root must be an object")
    typed_data = cast("dict[str, Any]", data)
    required_types = {
        "scenario_id": str,
        "status": str,
        "baseline_ready": bool,
        "baseline_context_fingerprint": str,
    }
    invalid = [
        key
        for key, expected_type in required_types.items()
        if not isinstance(data.get(key), expected_type)
    ]
    if invalid:
        return BaselineGate(
            False, f"malformed baseline result: invalid or missing fields {sorted(invalid)}"
        )
    fingerprint = typed_data["baseline_context_fingerprint"]
    if not FINGERPRINT_RE.fullmatch(fingerprint):
        return BaselineGate(False, "malformed baseline result: invalid context fingerprint")
    if (
        typed_data["scenario_id"] != "baseline_e2e"
        or typed_data["status"] != ResultStatus.PASS
        or typed_data["baseline_ready"] is not True
    ):
        return BaselineGate(False, "baseline_e2e result is not a passing runtime baseline.")
    if fingerprint != expected_fingerprint:
        return BaselineGate(False, "baseline result does not match current runtime context.")
    return BaselineGate(True, "baseline result matches current runtime context.")


def baseline_result_passed(path: Path | None, expected_fingerprint: str) -> bool:
    return validate_baseline_result(path, expected_fingerprint).passed


def runtime_context_manifest(repo_root: Path) -> dict[str, Any]:
    config_paths = [repo_root / item for item in RUNTIME_CONTEXT_PATHS]
    config_paths.extend(sorted((repo_root / "configs/open5gs").glob("*.yaml")))
    config_paths.extend(sorted((repo_root / "configs/ueransim").glob("*.yaml")))
    return {
        "schema_version": BASELINE_CONTEXT_SCHEMA_VERSION,
        "git_commit": repository_commit(repo_root),
        "config_sha256": {
            str(path.relative_to(repo_root)): sha256_file(path) for path in config_paths
        },
        "runtime_images": resolved_runtime_images(repo_root),
        "host": {
            "node": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "docker_engine": docker_engine_identity(repo_root),
        },
    }


def context_fingerprint(context: dict[str, Any]) -> str:
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def docker_engine_identity(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            [
                "docker",
                "version",
                "--format",
                "{{.Server.Version}}|{{.Server.Os}}|{{.Server.Arch}}|{{.Server.KernelVersion}}",
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def resolved_runtime_images(repo_root: Path) -> dict[str, str]:
    compose = load_yaml(repo_root / "docker-compose.yml")
    services = cast("dict[str, Any]", compose.get("services", {}))
    images: dict[str, str] = {}
    for service, config in services.items():
        if not isinstance(config, dict) or "image" not in config:
            continue
        images[service] = resolve_image_value(str(config["image"]))
    return dict(sorted(images.items()))


def resolve_image_value(value: str) -> str:
    match = IMAGE_DEFAULT_RE.fullmatch(value)
    if not match:
        return value
    variable, default = match.groups()
    return os.environ.get(variable, default)


def version_manifest(repo_root: Path) -> dict[str, str]:
    return {
        "compose_file": str(repo_root / "docker-compose.yml"),
        "open5gs_image_default": "gradiant/open5gs:2.8.0",
        "ueransim_image_default": "gradiant/ueransim:3.3.0",
        "mongodb_image_default": "mongo:8.3.8-noble",
        "dbctl_image_default": "gradiant/open5gs-dbctl:0.10.3",
        "dn_server_image_default": "busybox:1.37.0",
        "policy_control_mode": "PCF enabled for Open5GS 2.8.0",
        "slice_selection_mode": "direct NRF/SMF discovery; NSSF omitted",
    }


def runtime_evidence(output_dir: Path, *paths: Path) -> list[EvidenceRef]:
    refs = [
        EvidenceRef(
            kind="runtime_manifest",
            path=str(output_dir / "environment.json"),
            claim_level=ClaimLevel.RUNTIME_VERIFIED,
            description="Environment metadata captured at scenario start.",
        ),
        EvidenceRef(
            kind="runtime_versions",
            path=str(output_dir / "versions.json"),
            claim_level=ClaimLevel.RUNTIME_VERIFIED,
            description="Pinned runtime image defaults and execution context.",
        ),
        EvidenceRef(
            kind="runtime_context",
            path=str(output_dir / "runtime_context.json"),
            claim_level=ClaimLevel.RUNTIME_VERIFIED,
            description="Context used to bind the baseline gate to this runtime.",
        ),
    ]
    refs.extend(
        EvidenceRef(
            kind="runtime_output",
            path=str(path),
            claim_level=ClaimLevel.RUNTIME_VERIFIED,
            description="Runtime command output generated during scenario execution.",
        )
        for path in paths
        if path.exists()
    )
    return refs
