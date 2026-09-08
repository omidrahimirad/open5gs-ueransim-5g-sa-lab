from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path


def tshark_available() -> bool:
    return shutil.which("tshark") is not None


def extract_tshark_metadata(pcap_path: Path, output_csv: Path) -> bool:
    if not tshark_available():
        return False
    result = subprocess.run(
        [
            "tshark",
            "-r",
            str(pcap_path),
            "-T",
            "fields",
            "-e",
            "frame.number",
            "-e",
            "frame.time_epoch",
            "-e",
            "ip.src",
            "-e",
            "ip.dst",
            "-e",
            "_ws.col.Protocol",
            "-e",
            "sctp.port",
            "-e",
            "udp.port",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        return False
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame", "time_epoch", "src", "dst", "protocol", "sctp_port", "udp_port"])
        for line in result.stdout.splitlines():
            writer.writerow(line.split("\t"))
    return True
