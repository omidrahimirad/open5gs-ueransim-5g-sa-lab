from __future__ import annotations

from fiveg_lab.models import CheckStatus
from fiveg_lab.preflight import check_sctp, command_check


def test_optional_missing_command_is_warn() -> None:
    result = command_check("unlikely_tool", "definitely-not-a-real-lab-tool", required=False)

    assert result.status == CheckStatus.WARN


def test_required_missing_command_is_fail() -> None:
    result = command_check("unlikely_tool", "definitely-not-a-real-lab-tool", required=True)

    assert result.status == CheckStatus.FAIL


def test_sctp_check_fails_closed_on_non_linux() -> None:
    result = check_sctp(is_linux=False)

    assert result.status == CheckStatus.FAIL
