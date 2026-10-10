"""Synthetic input restrictions preserve automatic recovery, native pauses and stage navigation."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

POLICY = "art-of-rally-driving-only-v1"
PATCHES = [
    "PauseScreen.RecoverCar",
    "PauseScreen.ResetCar",
    "PauseScreen.Restart",
    "ShortcutManager.DoAction",
    "PauseScreen.UpdateMe",
    "PauseScreen.PauseStage",
]


@pytest.mark.skipif(
    not shutil.which("mcs") or not shutil.which("mono") or not os.getenv("RALLY_HARMONY_DLL"),
    reason="Mono tools and RALLY_HARMONY_DLL required for real patching",
)
@pytest.mark.parametrize("mode", ["enabled", "disabled"])
def test_native_control_policy_blocks_manual_reset_and_allows_stage_navigation(tmp_path, mode):
    source = Path(__file__).parent
    harmony = Path(os.environ["RALLY_HARMONY_DLL"]).resolve()
    subprocess.run(
        [
            "mcs",
            "-define:REAL_HARMONY",
            "-target:library",
            f"-out:{tmp_path / 'Assembly-CSharp.dll'}",
            "-r:System.Web.Extensions",
            str(source / "native_coverage_stubs.cs"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "mcs",
            f"-out:{tmp_path / 'test.exe'}",
            f"-r:{tmp_path / 'Assembly-CSharp.dll'}",
            f"-r:{harmony}",
            str(source.parents[1] / "gamecua/games/art_of_rally/DrivingOnlyControls.cs"),
            str(source / "native_driving_only_driver.cs"),
        ],
        check=True,
    )
    subprocess.run(
        ["mono", str(tmp_path / "test.exe"), str(tmp_path), mode],
        env={**os.environ, "MONO_PATH": str(harmony.parent)},
        check=True,
    )
    ready = tmp_path / "control-policy.json"
    if mode == "enabled":
        assert json.loads(ready.read_text()) == {
            "policy": POLICY,
            "binding": "synthetic-controls",
            "patches": PATCHES,
        }
    else:
        assert not ready.exists()
