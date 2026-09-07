from __future__ import annotations

import os

import pytest


@pytest.mark.runtime
def test_runtime_requires_explicit_opt_in() -> None:
    if os.environ.get("FIVEG_LAB_RUN_RUNTIME") != "1":
        pytest.skip("Runtime validation requires explicit FIVEG_LAB_RUN_RUNTIME=1 on Linux.")
