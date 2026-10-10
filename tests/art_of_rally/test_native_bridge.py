"""Compile and exercise the actual C# bridge with isolated synthetic native APIs."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not shutil.which("mcs") or not shutil.which("mono"), reason="Mono tools unavailable"
)
def test_native_bridge_transition_races(tmp_path):
    source = Path(__file__).parent
    bridge = source.parents[1] / "gamecua/games/art_of_rally/NativePause.cs"
    subprocess.run(
        [
            "mcs",
            "-target:library",
            f"-out:{tmp_path / 'Assembly-CSharp.dll'}",
            "-r:System.Web.Extensions",
            str(source / "native_pause_stubs.cs"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "mcs",
            f"-out:{tmp_path / 'test.exe'}",
            f"-r:{tmp_path / 'Assembly-CSharp.dll'}",
            str(bridge),
            str(source / "native_pause_driver.cs"),
        ],
        check=True,
    )
    result = subprocess.run(
        [
            "mono",
            str(tmp_path / "test.exe"),
            str(tmp_path / "handshake"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "transition checks passed" in result.stdout
    assert "native step checks passed" in result.stdout
