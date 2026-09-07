from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CheckStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class ResultStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class ClaimLevel(StrEnum):
    STATIC_VERIFIED = "STATIC VERIFIED"
    FIXTURE_VERIFIED = "FIXTURE VERIFIED"
    RUNTIME_VERIFIED = "RUNTIME VERIFIED"
    RUNTIME_PENDING = "REAL LINUX RUNTIME PENDING"


@dataclass(frozen=True)
class Check:
    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class AssertionResult:
    name: str
    status: ResultStatus
    expected: str
    observed: str
    detail: str


@dataclass(frozen=True)
class EvidenceRef:
    kind: str
    path: str
    claim_level: ClaimLevel
    description: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    run_id: str
    started_at: str
    status: ResultStatus
    baseline_ready: bool
    fault_applied: bool
    expected_failure_observed: bool
    recovery_attempted: bool
    recovery_status: ResultStatus
    observed_events: list[str]
    assertions: list[AssertionResult]
    evidence: list[EvidenceRef] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
