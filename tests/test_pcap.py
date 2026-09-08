from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from fiveg_lab import pcap


def test_tshark_metadata_extraction_is_optional(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(pcap, "tshark_available", lambda: False)

    assert not pcap.extract_tshark_metadata(tmp_path / "missing.pcap", tmp_path / "out.csv")
