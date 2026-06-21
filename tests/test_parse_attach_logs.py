from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
PARSER_PATH = REPO_ROOT / "scripts" / "parse_attach_logs.py"
SAMPLE_LOGS = sorted((REPO_ROOT / "logs").glob("*sample.txt"))


def load_parser() -> ModuleType:
    spec = importlib.util.spec_from_file_location("parse_attach_logs", PARSER_PATH)
    if spec is None or spec.loader is None:
        msg = f"Cannot load parser module from {PARSER_PATH}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parser_extracts_registration_events_from_sample_logs() -> None:
    parser = load_parser()

    events = [event for path in SAMPLE_LOGS for event in parser.parse_file(path)]
    event_names = {event.event for event in events}

    assert "ng_setup" in event_names
    assert "registration_request" in event_names
    assert "registration_accept" in event_names


def test_parser_extracts_authentication_events() -> None:
    parser = load_parser()

    events = [event for path in SAMPLE_LOGS for event in parser.parse_file(path)]

    assert any(event.event == "authentication" for event in events)
    assert any("Authentication successful" in event.raw_line for event in events)


def test_parser_extracts_pdu_session_events() -> None:
    parser = load_parser()

    events = [event for path in SAMPLE_LOGS for event in parser.parse_file(path)]
    event_names = {event.event for event in events}

    assert "pdu_session_request" in event_names
    assert "pdu_session_accept" in event_names
    assert "ue_tunnel_created" in event_names


def test_parser_handles_noisy_unmatched_lines_without_crashing(tmp_path: Path) -> None:
    parser = load_parser()
    noisy_log = tmp_path / "ue_noise.log"
    noisy_log.write_text(
        "\n".join(
            [
                "random line that should not match",
                "2026-06-21T10:00:00.000Z [nas] INFO NAS layer started",
                "2026-06-21T10:00:01.000Z [ngap] DEBUG unrelated NGAP detail",
            ]
        ),
        encoding="utf-8",
    )

    events = parser.parse_file(noisy_log)

    assert [event.event for event in events] == [
        "unclassified_relevant",
        "unclassified_relevant",
    ]


def test_parser_calculates_durations_correctly() -> None:
    parser = load_parser()

    events = [event for path in SAMPLE_LOGS for event in parser.parse_file(path)]
    events.sort(key=lambda event: (event.timestamp or "9999", event.component, event.event))
    summary = parser.build_summary(events)

    assert summary["registration_duration_ms"] == 1020.0
    assert summary["authentication_duration_ms"] == 320.0
    assert summary["pdu_session_establishment_duration_ms"] == 520.0


def test_parser_reports_missing_events_for_incomplete_logs(tmp_path: Path) -> None:
    parser = load_parser()
    incomplete_log = tmp_path / "amf_incomplete.log"
    incomplete_log.write_text(
        "2026-06-21T10:00:01.150Z [amf] INFO InitialUEMessage: Registration request\n",
        encoding="utf-8",
    )

    summary = parser.build_summary(parser.parse_file(incomplete_log))

    assert "pdu_session_accept" in summary["missing_events"]
    assert "ue_tunnel_created" in summary["missing_events"]


def test_csv_output_has_expected_columns(tmp_path: Path) -> None:
    parser = load_parser()
    output = tmp_path / "events.csv"
    events = [event for path in SAMPLE_LOGS for event in parser.parse_file(path)]

    parser.write_csv(events, output)

    with output.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "timestamp",
            "component",
            "event",
            "severity",
            "source_file",
            "line_number",
            "raw_line",
        ]


def test_json_output_is_valid(tmp_path: Path) -> None:
    parser = load_parser()
    output = tmp_path / "events.json"
    events = [event for path in SAMPLE_LOGS for event in parser.parse_file(path)]
    summary = parser.build_summary(events)

    parser.write_json(events, output, summary)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["missing_events"] == []
    assert payload["events"]


def test_cli_returns_success_on_sample_logs(tmp_path: Path) -> None:
    output = tmp_path / "events.csv"

    result = subprocess.run(
        [sys.executable, str(PARSER_PATH), *(str(path) for path in SAMPLE_LOGS), "-o", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "missing_events: []" in result.stdout
    assert output.exists()
