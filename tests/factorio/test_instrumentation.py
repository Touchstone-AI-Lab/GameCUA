"""Optional native Lua execution of the telemetry collector against synthetic APIs."""

import shutil
import subprocess
from pathlib import Path

import pytest

from gamecua.games.factorio.instrumentation import CONTROL


def test_lua_collector_reads_production_without_changing_gameplay(tmp_path):
    lua = shutil.which("lua5.4") or shutil.which("lua")
    if not lua:
        pytest.skip("Lua interpreter is required for synthetic collector execution")
    control = tmp_path / "control.lua"
    control.write_text(CONTROL)
    harness = Path(__file__).parents[1] / "fixtures/factorio/telemetry-harness.lua"
    result = subprocess.run(
        [lua, str(harness), str(control)], check=True, capture_output=True, text=True, timeout=10
    )
    assert "Synthetic Lua telemetry checks passed" in result.stdout
