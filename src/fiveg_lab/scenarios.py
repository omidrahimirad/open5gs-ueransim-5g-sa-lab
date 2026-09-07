from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from fiveg_lab.parser import ALL_EVENT_NAMES

FAULT_TYPES = {
    "none",
    "subscriber_key_mismatch",
    "unknown_subscriber",
    "dnn_mismatch",
    "snssai_mismatch",
    "restart_service",
    "stop_service",
    "n2_impairment",
    "n3_impairment",
}
TAXONOMY = {
    "CONFIGURATION",
    "AUTHENTICATION",
    "SUBSCRIBER",
    "SESSION_MANAGEMENT",
    "CONTROL_PLANE",
    "USER_PLANE",
    "TRANSPORT",
    "SERVICE_COMPONENT",
    "RECOVERY",
    "ENVIRONMENT",
    "UNKNOWN",
}
UNSAFE_KEYS = {"command", "shell", "script", "exec", "subprocess", "args"}
MAX_TIMEOUT_SECONDS = 1800


@dataclass(frozen=True)
class FaultSpec:
    type: str
    target: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    category: str
    description: str
    preconditions: list[str]
    fault: FaultSpec
    expected_control_plane: str
    expected_user_plane: str
    expected_events: list[str]
    forbidden_events: list[str]
    recovery_action: str
    recovery_expectation: str
    timeout_seconds: int
    runtime_validated: bool


def load_scenario(path: Path) -> Scenario:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{path} must contain a YAML mapping"
        raise ValueError(msg)
    data = cast("dict[str, Any]", raw)
    reject_unsafe_keys(data)
    return parse_scenario(data, path)


def reject_unsafe_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if str(key) in UNSAFE_KEYS:
                msg = f"Unsafe scenario key {path}.{key} is not allowed"
                raise ValueError(msg)
            reject_unsafe_keys(nested_value, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_unsafe_keys(item, f"{path}[{index}]")


def parse_scenario(data: dict[str, Any], path: Path) -> Scenario:
    reject_unsafe_keys(data)
    required = [
        "id",
        "title",
        "category",
        "description",
        "preconditions",
        "fault",
        "expected_control_plane",
        "expected_user_plane",
        "expected_events",
        "forbidden_events",
        "recovery_action",
        "recovery_expectation",
        "timeout_seconds",
        "runtime_validated",
    ]
    missing = [key for key in required if key not in data]
    if missing:
        msg = f"{path} missing required keys: {missing}"
        raise ValueError(msg)
    fault_raw = data["fault"]
    if not isinstance(fault_raw, dict):
        msg = f"{path} fault must be a mapping"
        raise ValueError(msg)
    fault = FaultSpec(
        type=str(fault_raw.get("type", "")),
        target=str(fault_raw["target"]) if "target" in fault_raw else None,
        value=str(fault_raw["value"]) if "value" in fault_raw else None,
    )
    if fault.type not in FAULT_TYPES:
        msg = f"{path} invalid fault type: {fault.type}"
        raise ValueError(msg)
    timeout = int(data["timeout_seconds"])
    if timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
        msg = f"{path} timeout_seconds must be 1..{MAX_TIMEOUT_SECONDS}"
        raise ValueError(msg)
    category = str(data["category"])
    if category not in TAXONOMY:
        msg = f"{path} invalid category: {category}"
        raise ValueError(msg)

    expected_events = list_of_strings(data["expected_events"], "expected_events", path)
    forbidden_events = list_of_strings(data["forbidden_events"], "forbidden_events", path)
    unknown = sorted((set(expected_events) | set(forbidden_events)) - ALL_EVENT_NAMES)
    if unknown:
        msg = f"{path} unknown event names: {unknown}"
        raise ValueError(msg)

    return Scenario(
        id=str(data["id"]),
        title=str(data["title"]),
        category=category,
        description=str(data["description"]),
        preconditions=list_of_strings(data["preconditions"], "preconditions", path),
        fault=fault,
        expected_control_plane=str(data["expected_control_plane"]),
        expected_user_plane=str(data["expected_user_plane"]),
        expected_events=expected_events,
        forbidden_events=forbidden_events,
        recovery_action=str(data["recovery_action"]),
        recovery_expectation=str(data["recovery_expectation"]),
        timeout_seconds=timeout,
        runtime_validated=bool(data["runtime_validated"]),
    )


def list_of_strings(value: Any, name: str, path: Path) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = f"{path} {name} must be a list of strings"
        raise ValueError(msg)
    return cast("list[str]", value)


def load_scenarios(directory: Path) -> list[Scenario]:
    return [load_scenario(path) for path in sorted(directory.glob("*.yaml"))]


def scenario_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
