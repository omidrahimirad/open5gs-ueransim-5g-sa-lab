from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fiveg_lab.models import ScenarioResult


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def make_run_id(scenario_id: str, started_at: str) -> str:
    compact = started_at.replace("-", "").replace(":", "").replace(".", "").replace("Z", "Z")
    return f"{compact}_{scenario_id}"


def environment_manifest(scenario_id: str) -> dict[str, str]:
    return {
        "timestamp_utc": utc_now(),
        "os": platform.platform(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "scenario_id": scenario_id,
        "runtime_claim": "REAL LINUX RUNTIME PENDING unless collected on a capable Linux host",
    }


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip()


def write_result(result: ScenarioResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "scenario_result.json"
    markdown_path = output_dir / "scenario_report.md"
    json_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(result: ScenarioResult) -> str:
    observed_events = (
        ", ".join(result.observed_events)
        if result.observed_events
        else "No runtime events were observed."
    )
    assertion_rows = "\n".join(
        f"| {item.name} | {item.status} | {item.expected} | {item.observed} |"
        for item in result.assertions
    )
    recovery_rows = "\n".join(
        f"| {item.name} | {item.status} | {item.expected} | {item.observed} |"
        for item in result.recovery_assertions
    )
    evidence_rows = "\n".join(
        f"| {item.kind} | {item.claim_level} | `{item.path}` | {item.description} |"
        for item in result.evidence
    )
    notes = "\n".join(f"- {note}" for note in result.notes) or "- None"
    return f"""# Scenario Report: {result.scenario_id}

Run ID: `{result.run_id}`

Started: `{result.started_at}`

Status: **{result.status}**

## Runtime State

- Baseline ready: {result.baseline_ready}
- Baseline context fingerprint: {result.baseline_context_fingerprint or "not recorded"}
- Fault applied: {result.fault_applied}
- Fault verified: {result.fault_verified}
- Expected failure observed: {result.expected_failure_observed}
- Recovery attempted: {result.recovery_attempted}
- Recovery status: {result.recovery_status}
- Rollback verified: {result.rollback_verified}
- Recovery verified: {result.recovery_verified}

## Observed Events

{observed_events}

## Assertions

| Assertion | Status | Expected | Observed |
| --- | --- | --- | --- |
{assertion_rows}

## Recovery Assertions

| Assertion | Status | Expected | Observed |
| --- | --- | --- | --- |
{recovery_rows}

## Evidence

| Type | Claim level | Path | Description |
| --- | --- | --- | --- |
{evidence_rows}

## Notes

{notes}
"""
