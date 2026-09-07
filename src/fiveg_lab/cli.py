from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fiveg_lab.assertions import evaluate_scenario_events, scenario_status
from fiveg_lab.config import checks_pass as config_checks_pass
from fiveg_lab.config import validate_repo
from fiveg_lab.evidence import make_run_id, utc_now, write_result
from fiveg_lab.models import (
    Check,
    ClaimLevel,
    EvidenceRef,
    ResultStatus,
    ScenarioResult,
)
from fiveg_lab.orchestration import run_runtime_scenario
from fiveg_lab.parser import parse_file
from fiveg_lab.preflight import checks_pass as preflight_checks_pass
from fiveg_lab.preflight import run_preflight
from fiveg_lab.scenarios import load_scenario, load_scenarios

RUNTIME_EXIT_CODES = {
    ResultStatus.PASS: 0,
    ResultStatus.FAIL: 1,
    ResultStatus.BLOCKED: 2,
    ResultStatus.ERROR: 3,
    ResultStatus.SKIPPED: 4,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-config":
        checks = validate_repo(Path(args.repo_root))
        print_checks(checks)
        return 0 if config_checks_pass(checks) else 1
    if args.command == "preflight":
        checks = run_preflight()
        print_checks(checks)
        return 0 if preflight_checks_pass(checks) else 1
    if args.command == "scenario":
        return handle_scenario(args)
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="5g-lab", description="5G SA lab validation tooling")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("validate-config", help="Validate lab configuration consistency")
    subcommands.add_parser("preflight", help="Check Linux runtime prerequisites")
    scenario = subcommands.add_parser("scenario", help="Scenario operations")
    scenario_subcommands = scenario.add_subparsers(dest="scenario_command", required=True)
    scenario_subcommands.add_parser("list", help="List scenario IDs")
    scenario_subcommands.add_parser("validate", help="Validate scenario schemas")
    run = scenario_subcommands.add_parser(
        "run", help="Run a scenario in fixture or blocked-runtime mode"
    )
    run.add_argument("scenario_id")
    run.add_argument("--fixture-log", action="append", type=Path, default=[])
    run.add_argument("--output-dir", type=Path, default=Path("reports/runtime"))
    run.add_argument("--baseline-result", type=Path, default=None)
    run.add_argument("--settle-seconds", type=int, default=20)
    return parser


def handle_scenario(args: argparse.Namespace) -> int:
    root = Path(args.repo_root)
    scenarios_dir = root / "scenarios"
    if args.scenario_command == "list":
        for scenario in load_scenarios(scenarios_dir):
            print(f"{scenario.id}\t{scenario.category}\t{scenario.title}")
        return 0
    if args.scenario_command == "validate":
        for scenario in load_scenarios(scenarios_dir):
            print(f"PASS {scenario.id}: {scenario.title}")
        return 0
    if args.scenario_command == "run":
        return run_scenario_fixture_or_blocked(args, scenarios_dir)
    return 2


def run_scenario_fixture_or_blocked(args: argparse.Namespace, scenarios_dir: Path) -> int:
    scenario = load_scenario(scenarios_dir / f"{args.scenario_id}.yaml")
    started_at = utc_now()
    run_id = make_run_id(scenario.id, started_at)
    events = [event.event for fixture_log in args.fixture_log for event in parse_file(fixture_log)]
    if args.fixture_log:
        assertions = evaluate_scenario_events(scenario, set(events))
        status = scenario_status(assertions)
        result = ScenarioResult(
            scenario_id=scenario.id,
            run_id=run_id,
            started_at=started_at,
            status=status,
            baseline_ready=scenario.id == "baseline_e2e" and status == ResultStatus.PASS,
            fault_applied=False,
            expected_failure_observed=status == ResultStatus.PASS and scenario.fault.type != "none",
            recovery_attempted=False,
            recovery_status=ResultStatus.SKIPPED,
            observed_events=sorted(set(events)),
            assertions=assertions,
            evidence=[
                EvidenceRef(
                    kind="fixture_logs",
                    path=",".join(str(path) for path in args.fixture_log),
                    claim_level=ClaimLevel.FIXTURE_VERIFIED,
                    description="Sample or fixture logs only; not real Linux runtime evidence.",
                )
            ],
        )
    else:
        result = run_runtime_scenario(
            Path(args.repo_root),
            scenario,
            args.output_dir,
            args.baseline_result,
            settle_seconds=args.settle_seconds,
        )
        print(f"{result.status} {result.scenario_id}")
        print(f"JSON: {args.output_dir / result.run_id / 'scenario_result.json'}")
        print(f"Markdown: {args.output_dir / result.run_id / 'scenario_report.md'}")
        return runtime_exit_code(result.status)

    output_dir = args.output_dir / result.run_id
    json_path, markdown_path = write_result(result, output_dir)
    print(f"{result.status} {result.scenario_id}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0 if result.status == ResultStatus.PASS else 1


def runtime_exit_code(status: ResultStatus) -> int:
    return RUNTIME_EXIT_CODES[status]


def print_checks(checks: list[Check]) -> None:
    for check in checks:
        print(f"{check.status}\t{check.name}\t{check.detail}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
