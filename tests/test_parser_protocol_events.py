from __future__ import annotations

from pathlib import Path

from fiveg_lab.parser import parse_file


def write_log(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "amf_runtime.log"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_parser_detects_negative_control_plane_events(tmp_path: Path) -> None:
    path = write_log(
        tmp_path,
        [
            "2026-06-21T10:00:00Z [amf] ERROR Authentication failure: MAC failure",
            "2026-06-21T10:00:01Z [amf] WARN Registration reject for unknown UE",
        ],
    )

    events = {event.event for event in parse_file(path)}

    assert "authentication_failure" in events
    assert "registration_reject" in events


def test_parser_detects_pfcp_and_user_plane_events(tmp_path: Path) -> None:
    path = write_log(
        tmp_path,
        [
            "2026-06-21T10:00:02Z [smf] INFO PFCP Association established",
            "2026-06-21T10:00:03Z [smf] INFO PFCP Session Establishment Request",
            "2026-06-21T10:00:04Z [test] INFO USER_PLANE_SUCCESS ping 0% packet loss",
            "2026-06-21T10:00:05Z [test] ERROR USER_PLANE_FAILURE 100% packet loss",
        ],
    )

    events = {event.event for event in parse_file(path)}

    assert {"pfcp_association", "pfcp_session_establishment"} <= events
    assert {"user_plane_success", "user_plane_failure"} <= events
