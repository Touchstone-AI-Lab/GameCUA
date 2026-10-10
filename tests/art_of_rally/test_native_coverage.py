"""Actual observer recovery hooks under synthetic native APIs and real Harmony patches."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not shutil.which("mcs") or not shutil.which("mono") or not os.getenv("RALLY_HARMONY_DLL"),
    reason="Mono tools and RALLY_HARMONY_DLL required for real patching",
)
def test_recovery_setter_remains_observable_inside_patched_physics(tmp_path):
    source = Path(__file__).parent
    harmony = Path(os.environ["RALLY_HARMONY_DLL"]).resolve()
    shutil.copyfile(harmony, tmp_path / "0Harmony.dll")
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
            f"-r:{tmp_path / '0Harmony.dll'}",
            str(source.parents[1] / "gamecua/games/art_of_rally/CoverageObserver.cs"),
            str(source / "native_recovery_hook_driver.cs"),
        ],
        check=True,
    )
    path = tmp_path / "native.jsonl"
    subprocess.run(
        ["mono", str(tmp_path / "test.exe"), str(path)],
        check=True,
        env={**os.environ, "MONO_PATH": str(harmony.parent)},
    )
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["coverage"]["event"] for r in rows] == [
        "physics",
        "recovery_begin",
        "physics",
        "physics",
        "recovery_end",
        "physics",
    ]
    assert [r["resetting"] for r in rows] == [False, True, True, True, False, False]
