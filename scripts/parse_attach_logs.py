#!/usr/bin/env python3
"""Compatibility wrapper for the 5G SA log parser."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "src"
    if src.exists():
        sys.path.insert(0, str(src))

from fiveg_lab.parser import (  # noqa: E402
    Event,
    build_summary,
    classify_events,
    duration_ms,
    first_timestamp,
    infer_component,
    infer_severity,
    is_relevant_unclassified,
    main,
    normalize_timestamp,
    parse_args,
    parse_file,
    parse_timestamp,
    trim_fractional_seconds,
    write_csv,
    write_json,
)

__all__ = [
    "Event",
    "build_summary",
    "classify_events",
    "duration_ms",
    "first_timestamp",
    "infer_component",
    "infer_severity",
    "is_relevant_unclassified",
    "main",
    "normalize_timestamp",
    "parse_args",
    "parse_file",
    "parse_timestamp",
    "trim_fractional_seconds",
    "write_csv",
    "write_json",
]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
