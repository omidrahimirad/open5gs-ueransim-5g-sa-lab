from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from fiveg_lab.orchestration import run_command


def delayed_child_command(marker: Path) -> list[str]:
    # Local process fixtures only: no Docker, Linux network, or lab behavior.
    child = (
        "import time; from pathlib import Path; time.sleep(2); "
        f"Path({str(marker)!r}).write_text('unexpected surviving child')"
    )
    parent = (
        "import os, subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "print(os.environ['LAB_CLEANUP_TEST_VALUE'], flush=True); "
        "print('partial error', file=sys.stderr, flush=True); time.sleep(30)"
    )
    return [sys.executable, "-c", parent]


def test_timeout_kills_descendants_and_preserves_output_and_environment(tmp_path: Path) -> None:
    marker = tmp_path / "orphan-created-resource"
    result = run_command(
        delayed_child_command(marker),
        tmp_path,
        1,
        env={"LAB_CLEANUP_TEST_VALUE": "configured environment"},
    )
    assert result.returncode == 124
    assert result.stdout.strip() == "configured environment"
    assert "partial error" in result.stderr
    assert "timeout after 1s" in result.stderr
    time.sleep(1.25)
    assert not marker.exists()


@pytest.mark.parametrize("terminate", [False, True], ids=["keyboard-interrupt", "sigterm"])
def test_interrupt_kills_descendants_before_propagating_and_restores_handler(
    tmp_path: Path, monkeypatch: MonkeyPatch, terminate: bool
) -> None:
    original_communicate = subprocess.Popen.communicate
    previous_term = signal.getsignal(signal.SIGTERM)
    interrupted = False

    def communicate(process: subprocess.Popen[str], *args: Any, **kwargs: Any) -> Any:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            try:
                return original_communicate(process, timeout=1)
            except subprocess.TimeoutExpired:
                if terminate:
                    # Deliver an actual SIGTERM; the scoped handler must turn
                    # it into an interruption that cleans up the child group.
                    os.kill(os.getpid(), signal.SIGTERM)
                raise KeyboardInterrupt from None
        return original_communicate(process, *args, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "communicate", communicate)
    marker = tmp_path / "orphan-after-interrupt"
    with pytest.raises(KeyboardInterrupt):
        run_command(
            delayed_child_command(marker),
            tmp_path,
            30,
            env={"LAB_CLEANUP_TEST_VALUE": "interrupt fixture"},
        )
    assert signal.getsignal(signal.SIGTERM) == previous_term
    time.sleep(1.25)
    assert not marker.exists()


def test_completed_command_preserves_exit_code_and_both_streams(tmp_path: Path) -> None:
    previous_term = signal.getsignal(signal.SIGTERM)
    result = run_command(
        [
            sys.executable,
            "-c",
            "import sys; print('output'); print('error', file=sys.stderr); sys.exit(7)",
        ],
        tmp_path,
        5,
    )
    assert result.returncode == 7
    assert result.stdout == "output\n"
    assert result.stderr == "error\n"
    assert signal.getsignal(signal.SIGTERM) == previous_term
