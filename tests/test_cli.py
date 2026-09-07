from __future__ import annotations

import json
from pathlib import Path

from pytest import CaptureFixture

from fiveg_lab.cli import main, runtime_exit_code
from fiveg_lab.models import ResultStatus

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cli_lists_scenarios(capsys: CaptureFixture[str]) -> None:
    status = main(["--repo-root", str(REPO_ROOT), "scenario", "list"])

    captured = capsys.readouterr()
    assert status == 0
    assert "baseline_e2e" in captured.out


def test_cli_validates_config(capsys: CaptureFixture[str]) -> None:
    status = main(["--repo-root", str(REPO_ROOT), "validate-config"])

    captured = capsys.readouterr()
    assert status == 0
    assert "required_network_functions" in captured.out


def test_cli_generates_fixture_scenario_result(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    fixture_log = tmp_path / "fixture.log"
    fixture_log.write_text(
        "\n".join(
            [
                "2026-06-21T10:00:00Z [gnb] INFO NG Setup accepted",
                "2026-06-21T10:00:01Z [amf] INFO InitialUEMessage Registration request",
                "2026-06-21T10:00:02Z [amf] INFO Authentication successful",
                "2026-06-21T10:00:03Z [amf] INFO Security mode complete",
                "2026-06-21T10:00:04Z [amf] INFO Registration Accept",
                "2026-06-21T10:00:05Z [ue] INFO PDU Session Establishment Request",
                "2026-06-21T10:00:06Z [ue] INFO PDU Session Establishment Accept",
                "2026-06-21T10:00:07Z [ue] INFO uesimtun0 IPv4 address allocated",
                "2026-06-21T10:00:08Z [test] INFO USER_PLANE_SUCCESS ping 0% packet loss",
            ]
        ),
        encoding="utf-8",
    )

    status = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "scenario",
            "run",
            "baseline_e2e",
            "--fixture-log",
            str(fixture_log),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )

    captured = capsys.readouterr()
    result_path = next((tmp_path / "reports").glob("*/scenario_result.json"))
    assert status == 0
    assert "PASS baseline_e2e" in captured.out
    assert json.loads(result_path.read_text(encoding="utf-8"))["status"] == "PASS"


def test_runtime_exit_codes_are_unambiguous() -> None:
    assert runtime_exit_code(ResultStatus.PASS) == 0
    assert runtime_exit_code(ResultStatus.FAIL) == 1
    assert runtime_exit_code(ResultStatus.BLOCKED) == 2
    assert runtime_exit_code(ResultStatus.ERROR) == 3
    assert runtime_exit_code(ResultStatus.SKIPPED) == 4
