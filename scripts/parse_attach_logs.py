#!/usr/bin/env python3
"""Parse Open5GS/UERANSIM logs into a 5G attach/session event timeline.

The parser intentionally uses broad procedure-level patterns. Open5GS and
UERANSIM log text varies across versions, so unmatched NAS/NGAP/PFCP/GTP lines
are retained as ``unclassified_relevant`` events for manual review.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

EVENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ng_setup",
        re.compile(
            r"\b(NG[- ]?Setup|NGSetup|gNB.*(connect|accepted)|"
            r"SCTP.*(connect|established|association))",
            re.I,
        ),
    ),
    (
        "registration_request",
        re.compile(
            r"\b(Registration request|InitialUEMessage|Initial UE Message|5GS registration)",
            re.I,
        ),
    ),
    (
        "authentication",
        re.compile(
            r"\b(Authentication (request|response|successful|failure|reject)|"
            r"AUSF|auth[- ]?vector)",
            re.I,
        ),
    ),
    (
        "security_mode",
        re.compile(
            r"\b(Security mode (command|complete|reject)|Security Mode|NAS security)",
            re.I,
        ),
    ),
    (
        "registration_accept",
        re.compile(
            r"\b(Registration accept|Registration complete|Registration Accept|"
            r"Registration Complete|registered)",
            re.I,
        ),
    ),
    (
        "pdu_session_request",
        re.compile(
            r"\b(PDU session establishment request|PDUSessionResourceSetupRequest|"
            r"PDU Session Establishment Request|CreateSMContext)",
            re.I,
        ),
    ),
    (
        "pdu_session_accept",
        re.compile(
            r"\b(PDU session establishment accept|PDU Session Establishment Accept|"
            r"PDU Session Establishment is successful|PDU Session Resource Setup Response|"
            r"CreateSMContext.*success)",
            re.I,
        ),
    ),
    (
        "ue_tunnel_created",
        re.compile(
            r"\b(uesimtun\d*|TUN interface|UE IP|PDU Address|IPv4 address|"
            r"allocated.*address)",
            re.I,
        ),
    ),
    (
        "error",
        re.compile(
            r"\b(ERROR|WARN|FAIL(?:ED|URE)?|reject(?:ed)?|denied|No response|"
            r"timed out|mismatch|not found|unknown|invalid)",
            re.I,
        ),
    ),
]

TIMESTAMP_PATTERNS: Sequence[re.Pattern[str]] = [
    re.compile(
        r"(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))"
    ),
    re.compile(r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)"),
    re.compile(r"\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)\]"),
    re.compile(r"(?P<ts>\d{2}/\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)"),
]

SEVERITY_RE = re.compile(r"\b(?P<sev>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\b", re.I)
RELEVANT_BUT_UNCLASSIFIED_RE = re.compile(
    r"\b(NAS|NGAP|SCTP|PFCP|GTP|PDU|DNN|NSSAI|S-NSSAI|SUPI|IMSI|TUN|UE|gNB|AMF|SMF|UPF)\b",
    re.I,
)


@dataclass(frozen=True)
class Event:
    timestamp: str
    component: str
    event: str
    severity: str
    raw_line: str
    source_file: str
    line_number: int


def parse_timestamp(line: str) -> datetime | None:
    for pattern in TIMESTAMP_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        value = match.group("ts")
        try:
            if re.match(r"\d{2}/\d{2} ", value):
                year = datetime.now(UTC).year
                timestamp_format = "%Y/%m/%d %H:%M:%S.%f" if "." in value else "%Y/%m/%d %H:%M:%S"
                parsed = datetime.strptime(f"{year}/{value}", timestamp_format)
                return parsed.replace(tzinfo=UTC)
            if "T" in value:
                value = trim_fractional_seconds(value)
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            if re.search(r"[+-]\d{2}:\d{2}$", value):
                return datetime.fromisoformat(value)
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def trim_fractional_seconds(value: str) -> str:
    """Convert Docker nanosecond timestamps to Python-supported microseconds."""
    return re.sub(r"\.(\d{6})\d+(?=Z|[+-]\d{2}:\d{2}$)", r".\1", value)


def normalize_timestamp(ts: datetime | None) -> str:
    if ts is None:
        return ""
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


def infer_component(path: Path) -> str:
    name = path.name.lower()
    for component in ("ue", "gnb", "amf", "smf", "upf", "nrf"):
        if component in name:
            return component.upper()
    return path.stem.upper()


def infer_severity(line: str) -> str:
    match = SEVERITY_RE.search(line)
    if not match:
        return "INFO"
    sev = match.group("sev").upper()
    return "WARN" if sev == "WARNING" else sev


def classify_events(line: str) -> list[str]:
    events: list[str] = []
    for event, pattern in EVENT_PATTERNS:
        if pattern.search(line):
            events.append(event)
    return events


def is_relevant_unclassified(line: str) -> bool:
    return bool(RELEVANT_BUT_UNCLASSIFIED_RE.search(line))


def parse_file(path: Path) -> list[Event]:
    component = infer_component(path)
    events: list[Event] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise RuntimeError(f"Cannot read {path}: {exc}") from exc

    for line_number, line in enumerate(lines, start=1):
        event_names = classify_events(line)
        if not event_names and is_relevant_unclassified(line):
            event_names = ["unclassified_relevant"]
        for event in event_names:
            events.append(
                Event(
                    timestamp=normalize_timestamp(parse_timestamp(line)),
                    component=component,
                    event=event,
                    severity=infer_severity(line),
                    raw_line=line.strip(),
                    source_file=str(path),
                    line_number=line_number,
                )
            )
    return events


def first_timestamp(events: Iterable[Event], names: set[str]) -> datetime | None:
    for event in events:
        if event.event not in names or not event.timestamp:
            continue
        try:
            return datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def duration_ms(events: list[Event], start_names: set[str], end_names: set[str]) -> float | None:
    start = first_timestamp(events, start_names)
    end = first_timestamp(events, end_names)
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds() * 1000, 3)


def write_csv(events: list[Event], output: Path) -> None:
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "component",
                "event",
                "severity",
                "source_file",
                "line_number",
                "raw_line",
            ],
        )
        writer.writeheader()
        for event in events:
            writer.writerow(asdict(event))


def write_json(events: list[Event], output: Path, summary: dict[str, object]) -> None:
    payload = {"events": [asdict(event) for event in events], "summary": summary}
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_summary(events: list[Event]) -> dict[str, object]:
    event_names = {event.event for event in events}
    required = [
        "ng_setup",
        "registration_request",
        "authentication",
        "security_mode",
        "registration_accept",
        "pdu_session_request",
        "pdu_session_accept",
        "ue_tunnel_created",
    ]
    missing = [name for name in required if name not in event_names]
    return {
        "event_count": len(events),
        "unclassified_relevant_count": sum(
            1 for event in events if event.event == "unclassified_relevant"
        ),
        "error_or_warning_count": sum(
            1
            for event in events
            if event.severity in {"WARN", "ERROR", "FATAL"} or event.event == "error"
        ),
        "missing_events": missing,
        "registration_duration_ms": duration_ms(
            events,
            {"registration_request"},
            {"registration_accept"},
        ),
        "authentication_duration_ms": duration_ms(events, {"authentication"}, {"security_mode"}),
        "pdu_session_establishment_duration_ms": duration_ms(
            events,
            {"pdu_session_request"},
            {"pdu_session_accept", "ue_tunnel_created"},
        ),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Examples:\n"
            "  python3 scripts/parse_attach_logs.py logs/*sample.txt "
            "-o logs/parsed_attach_events.csv\n"
            "  python3 scripts/parse_attach_logs.py logs/20260621T*/"
            "{ue,gnb,amf,smf}.log --json -o logs/parsed_attach_events.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "logs",
        nargs="+",
        type=Path,
        help="Log files to parse, e.g. logs/*sample.txt",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("logs/parsed_attach_events.csv"),
        help="Output CSV or JSON path",
    )
    parser.add_argument("--json", action="store_true", help="Write JSON instead of CSV")
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    all_events: list[Event] = []
    for path in args.logs:
        if not path.exists():
            print(f"WARNING: missing log file {path}", file=sys.stderr)
            continue
        all_events.extend(parse_file(path))

    all_events.sort(key=lambda event: (event.timestamp or "9999", event.component, event.event))
    summary = build_summary(all_events)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.json:
        write_json(all_events, args.output, summary)
    else:
        write_csv(all_events, args.output)

    print(f"Parsed {len(all_events)} events -> {args.output}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    if summary["missing_events"]:
        missing_events = cast("list[str]", summary["missing_events"])
        print(
            "WARNING: required events missing: " + ", ".join(missing_events),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
