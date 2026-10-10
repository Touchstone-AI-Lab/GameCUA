"""Synthetic snapshots test complete and split restoration without native gameplay."""

import base64
import shutil
import xml.etree.ElementTree as ET

import pytest

from gamecua.catalog import digest
from gamecua.games.art_of_rally import setup
from gamecua.storage import sha256, write_json

STATE_FILES = {"customrally", "SaveGame.json", "career", "prefs", "preparation.json"}


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    monkeypatch.delenv(setup.RUNTIME_ENV, raising=False)
    monkeypatch.setattr(setup, "link_steam", lambda profile: None)
    snapshot, installation = tmp_path / "snapshot", tmp_path / "installation"
    snapshot.mkdir()
    (installation / "artofrally_Data").mkdir(parents=True)
    for name in (setup.BINARY, "UnityPlayer.so"):
        (installation / name).write_bytes(b"synthetic installation " + name.encode())
    for name in ("customrally", "career", "SaveGame.json"):
        write_json(snapshot / name, {"synthetic": name})
    (snapshot / "prefs").write_text(
        '<prefs><pref name="SETTINGS_APPLICATION_PATH">c3ludGhldGlj</pref></prefs>'
    )
    write_json(snapshot / "preparation.json", {"protocol": "art-of-rally-five-stage-integer-v8"})
    for name in (
        "loader/libdoorstop.so",
        "loader/RallyNativeObserver.dll",
        "loader/BepInEx/core/BepInEx.Preloader.dll",
        "main-menu.png",
        "title-screen.png",
    ):
        path = snapshot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic runtime " + name.encode())
    manifest = {
        path.relative_to(snapshot).as_posix(): sha256(path)
        for path in snapshot.rglob("*")
        if path.is_file()
    }
    write_json(snapshot / "manifest.json", manifest)
    return snapshot, installation, manifest


def separate(snapshot, manifest):
    runtime = snapshot.with_name(snapshot.name + ".runtime")
    runtime.mkdir()
    for name in set(manifest) - STATE_FILES:
        target = runtime / name
        target.parent.mkdir(parents=True, exist_ok=True)
        (snapshot / name).rename(target)
    shutil.rmtree(snapshot / "loader")
    return runtime


@pytest.mark.parametrize("location", ["complete", "sibling", "environment", "image"])
def test_snapshot_files_resolve_split_runtime(frozen, monkeypatch, location):
    snapshot, _, manifest = frozen
    runtime = snapshot
    if location != "complete":
        runtime = separate(snapshot, manifest)
    if location == "environment":
        runtime = runtime.rename(snapshot.parent / "explicit-runtime")
        monkeypatch.setenv(setup.RUNTIME_ENV, str(runtime))
    elif location == "image":
        image_root = snapshot.parent / "image-runtime"
        image_root.mkdir()
        runtime = runtime.rename(image_root / digest(manifest))
        monkeypatch.setattr(setup, "IMAGE_RUNTIME_ROOT", image_root)
    files = setup.snapshot_files(snapshot)
    assert set(files) == set(manifest)
    assert files["main-menu.png"] == runtime / "main-menu.png"
    assert files["career"] == snapshot / "career"
    assert all(sha256(files[name]) == checksum for name, checksum in manifest.items())


@pytest.mark.parametrize("layout", ["complete", "split"])
def test_restore_copies_state_loader_and_installation(frozen, layout):
    snapshot, installation, manifest = frozen
    if layout == "split":
        separate(snapshot, manifest)
    profile = snapshot.parent / "profile"
    preparation = setup.restore(snapshot, installation, profile)
    assert preparation["protocol"] == "art-of-rally-five-stage-integer-v8"
    for name, relative in setup.PROFILE_FILES.items():
        path = profile / "home/.config/unity3d" / relative
        if name != "prefs":
            assert sha256(path) == manifest[name]
        else:
            values = {pref.get("name"): pref.text for pref in ET.fromstring(path.read_bytes())}
            assert base64.b64decode(values["SETTINGS_APPLICATION_PATH"]).decode() == str(
                setup.config_dir(profile)
            )
    assert sha256(profile / "game/libdoorstop.so") == manifest["loader/libdoorstop.so"]
    assert (
        sha256(profile / "game/BepInEx/plugins/RallyNativeObserver.dll")
        == manifest["loader/RallyNativeObserver.dll"]
    )
    assert sha256(profile / "game" / setup.BINARY) == sha256(installation / setup.BINARY)
    assert (profile / "game/UnityPlayer.so").resolve() == installation / "UnityPlayer.so"


def test_game_process_does_not_receive_api_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-secret")
    values = setup.launch_environment(tmp_path)
    assert not any(key.endswith("API_KEY") for key in values)
    assert values["HOME"] == str(tmp_path.resolve() / "home")
    assert values["SteamAppId"] == "550320"
