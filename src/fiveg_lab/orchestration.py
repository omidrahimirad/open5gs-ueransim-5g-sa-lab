from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from fiveg_lab.assertions import evaluate_scenario_events, scenario_status
from fiveg_lab.config import checks_pass as config_checks_pass
from fiveg_lab.config import validate_repo
from fiveg_lab.evidence import environment_manifest, make_run_id, utc_now, write_result
from fiveg_lab.fault_injection import FaultInjector, default_runner
from fiveg_lab.models import CheckStatus, ClaimLevel, EvidenceRef, ResultStatus, ScenarioResult
from fiveg_lab.parser import parse_file
from fiveg_lab.preflight import checks_pass as preflight_checks_pass
from fiveg_lab.preflight import run_preflight
from fiveg_lab.scenarios import Scenario


@dataclass(frozen=True)
class CommandOutcome:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


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
    (output_dir / "environment.json").write_text(
        json.dumps(environment_manifest(scenario.id), indent=2),
        encoding="utf-8",
    )
    (output_dir / "versions.json").write_text(
        json.dumps(version_manifest(repo_root), indent=2),
        encoding="utf-8",
    )

    blocked = blocking_reason(repo_root)
    if blocked:
        result = blocked_result(scenario, run_id, started_at, blocked)
        write_result(result, output_dir)
        return result

    if scenario.id != "baseline_e2e" and not baseline_result_passed(baseline_result):
        result = blocked_result(
            scenario,
            run_id,
            started_at,
            ["baseline_e2e must pass before fault scenarios run."],
        )
        write_result(result, output_dir)
        return result

    if scenario.id == "baseline_e2e":
        result = execute_baseline(
            repo_root, scenario, output_dir, run_id, started_at, settle_seconds
        )
    else:
        result = execute_fault_scenario(
            repo_root, scenario, output_dir, run_id, started_at, settle_seconds
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
        notes=["Runtime scenario was not executed."] + reasons,
    )


def execute_baseline(
    repo_root: Path,
    scenario: Scenario,
    output_dir: Path,
    run_id: str,
    started_at: str,
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
        evidence=runtime_evidence(output_dir, traffic_path),
        notes=command_notes(outcomes),
    )


def execute_fault_scenario(
    repo_root: Path,
    scenario: Scenario,
    output_dir: Path,
    run_id: str,
    started_at: str,
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
                "but runtime mutation is intentionally not automated yet.",
            ],
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
    fault_applied = False
    recovery_attempted = False
    injector = FaultInjector(scenario.fault, default_runner)
    traffic_path = output_dir / "fault_traffic_result.txt"
    try:
        injector.apply()
        fault_applied = True
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
        write_command_log(outcomes, output_dir / "commands.json")
        return error_result(
            scenario,
            run_id,
            started_at,
            fault_applied=fault_applied,
            recovery_attempted=recovery_attempted,
            notes=[f"Fault scenario infrastructure failed: {exc}"],
        )
    finally:
        if fault_applied:
            recovery_attempted = True
            injector.remove()

    recovery_path = output_dir / "recovery_traffic_result.txt"
    outcomes.append(
        run_command(
            ["./scripts/traffic_test.sh"],
            repo_root,
            scenario.timeout_seconds,
            env={"OUT": str(recovery_path)},
        )
    )
    write_command_log(outcomes, output_dir / "commands.json")
    events = parse_runtime_events(repo_root, traffic_path, recovery_path)
    assertions = evaluate_scenario_events(scenario, set(events))
    recovery_status = ResultStatus.PASS if outcomes[-1].returncode == 0 else ResultStatus.FAIL
    status = scenario_status(assertions)
    if recovery_status != ResultStatus.PASS:
        status = ResultStatus.FAIL
    return ScenarioResult(
        scenario_id=scenario.id,
        run_id=run_id,
        started_at=started_at,
        status=status,
        baseline_ready=True,
        fault_applied=fault_applied,
        expected_failure_observed=status == ResultStatus.PASS,
        recovery_attempted=recovery_attempted,
        recovery_status=recovery_status,
        observed_events=sorted(set(events)),
        assertions=assertions,
        evidence=runtime_evidence(output_dir, traffic_path, recovery_path),
        notes=command_notes(outcomes),
    )


def error_result(
    scenario: Scenario,
    run_id: str,
    started_at: str,
    fault_applied: bool,
    recovery_attempted: bool,
    notes: list[str],
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario.id,
        run_id=run_id,
        started_at=started_at,
        status=ResultStatus.ERROR,
        baseline_ready=scenario.id != "baseline_e2e",
        fault_applied=fault_applied,
        expected_failure_observed=False,
        recovery_attempted=recovery_attempted,
        recovery_status=ResultStatus.ERROR,
        observed_events=[],
        assertions=[],
        notes=notes,
    )


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


def command_notes(outcomes: list[CommandOutcome]) -> list[str]:
    notes: list[str] = []
    for outcome in outcomes:
        if outcome.returncode != 0:
            notes.append(f"Command failed: {' '.join(outcome.args)}")
            if outcome.stderr.strip():
                notes.append(outcome.stderr.strip())
    return notes


def baseline_result_passed(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    data = cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
    return data.get("scenario_id") == "baseline_e2e" and data.get("status") == ResultStatus.PASS


def version_manifest(repo_root: Path) -> dict[str, str]:
    return {
        "compose_file": str(repo_root / "docker-compose.yml"),
        "open5gs_image_default": "gradiant/open5gs:2.8.0",
        "ueransim_image_default": "gradiant/ueransim:3.3.0",
        "mongodb_image_default": "mongo:8.3.8-noble",
        "dbctl_image_default": "gradiant/open5gs-dbctl:0.10.3",
        "dn_server_image_default": "busybox:1.37.0",
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
