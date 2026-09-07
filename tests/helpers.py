from __future__ import annotations


def valid_scenario_payload() -> dict[str, object]:
    return {
        "id": "fixture",
        "title": "Fixture scenario",
        "category": "AUTHENTICATION",
        "description": "Fixture",
        "preconditions": ["baseline passes"],
        "fault": {"type": "subscriber_key_mismatch"},
        "expected_control_plane": "auth failure",
        "expected_user_plane": "unavailable",
        "expected_events": ["authentication_failure"],
        "forbidden_events": ["registration_accept"],
        "recovery_action": "restore key",
        "recovery_expectation": "baseline passes",
        "timeout_seconds": 60,
        "runtime_validated": False,
    }
