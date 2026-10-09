"""PEAK isolated game staging and launch environment."""

import json
import os
from pathlib import Path

from gamecua.games.peak.setup import native_environment, stage_game


def test_overlay_keeps_immutable_game_files_and_private_loader_writes(tmp_path):
    source = tmp_path / "source"
    (source / "BepInEx").mkdir(parents=True)
    (source / "PEAK.exe").write_bytes(b"synthetic test-only file")
    (source / "BepInEx/LogOutput.log").write_text("old private log")
    game = stage_game(source, tmp_path / "episode/game")
    assert (game / "PEAK.exe").is_symlink()
    assert not (game / "BepInEx").is_symlink()
    assert not (game / "BepInEx/LogOutput.log").exists()
    (game / "BepInEx/new-private.log").write_text("episode only")
    assert not (source / "BepInEx/new-private.log").exists()


def test_native_environment_requires_wsl_hardware_and_never_reuses_evidence(tmp_path, monkeypatch):
    monkeypatch.delenv("GAMECUA_PEAK_MESA_LIBDIR", raising=False)
    monkeypatch.setenv("GITHUB_HEAD_REF", "feat/peak-progress-v1")
    inherited = dict(os.environ)
    env = native_environment(tmp_path, Path("/private/official-steam"), "fixture-binding")
    assert env["LIBGL_ALWAYS_SOFTWARE"] == "0"
    assert env["GALLIUM_DRIVER"] == "d3d12"
    assert env["PROTON_USE_WINED3D"] == "1"
    assert env["SteamAppId"] == "3527290"
    assert env["STEAM_COMPAT_DATA_PATH"] == str(tmp_path / "compat")
    assert env["GAMECUA_PEAK_EVIDENCE"] == "Z:" + str(tmp_path / "native.jsonl")
    assert env["GITHUB_HEAD_REF"] == inherited["GITHUB_HEAD_REF"]
    configured = {key: value for key, value in env.items() if inherited.get(key) != value}
    assert "peak-progress" not in json.dumps(configured)


def test_private_mesa_bundle_keeps_hardware_constraints_and_parent_environment(
    tmp_path, monkeypatch
):
    library_dir = tmp_path / "mesa/lib"
    (library_dir / "dri").mkdir(parents=True)
    for name in ("libGLX_mesa.so.0", "dri/d3d12_dri.so"):
        (library_dir / name).write_bytes(b"synthetic driver fixture")
    monkeypatch.setenv("GAMECUA_PEAK_MESA_LIBDIR", str(library_dir))
    monkeypatch.setenv("LD_LIBRARY_PATH", "/unrelated")
    monkeypatch.setenv("LIBGL_ALWAYS_SOFTWARE", "1")
    monkeypatch.setenv("GALLIUM_DRIVER", "llvmpipe")
    inherited = dict(os.environ)
    environment = native_environment(tmp_path / "profile", Path("/official-steam"), "fixture")
    assert environment["LD_LIBRARY_PATH"] == f"{library_dir}:/usr/lib/wsl/lib"
    assert environment["LIBGL_DRIVERS_PATH"] == str(library_dir / "dri")
    assert environment["LIBGL_ALWAYS_SOFTWARE"] == "0"
    assert environment["GALLIUM_DRIVER"] == "d3d12"
    assert environment["MESA_LOADER_DRIVER_OVERRIDE"] == "d3d12"
    assert dict(os.environ) == inherited
