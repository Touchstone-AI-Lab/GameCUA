"""Factorio profile isolation, installation detection and native stream checks."""

import json
import zipfile

import pytest

from gamecua.games.factorio.integration import Backend
from gamecua.games.factorio.setup import (
    capture_snapshot,
    command,
    configure,
    environment,
    installation_identity,
)

from .test_progress import sample


@pytest.fixture
def installation(tmp_path, monkeypatch):
    """Create a synthetic standalone installation."""
    root = tmp_path / "installation"
    (root / "bin/x64").mkdir(parents=True)
    (root / "bin/x64/factorio").write_bytes(b"synthetic-executable")
    monkeypatch.setattr(
        "subprocess.check_output",
        lambda *args, **kwargs: "Version: 2.0.72 (build 84555, linux64, full)\n",
    )
    return root


@pytest.fixture
def snapshot(tmp_path, installation):
    """Capture a synthetic prepared save."""
    source = tmp_path / "source/start.zip"
    source.parent.mkdir()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("start/level.dat", b"synthetic-native-fixture")
    target = tmp_path / "snapshot"
    capture_snapshot(source, target, installation, "12345", "Synthetic offline fixture only")
    return target


def test_demo_and_headless_installs_are_rejected(installation, monkeypatch):
    for suffix in ("demo", "headless"):
        monkeypatch.setattr(
            "subprocess.check_output",
            lambda *args, **kwargs: f"Version: 2.0.72 (build 84555, linux64, {suffix})\n",
        )
        with pytest.raises(ValueError, match="licensed Linux64 full"):
            installation_identity(installation)


def test_steam_builds_are_detected(installation, monkeypatch):
    assert installation_identity(installation)["distribution"] == "licensed_standalone"
    monkeypatch.setattr(
        "subprocess.check_output",
        lambda *a, **kw: "Version: 2.0.77 (build 84539, linux64, steam)\n",
    )
    assert installation_identity(installation) == {
        "game_version": "2.0.77",
        "distribution": "steam",
    }


def test_steam_profile_preserves_client_home_but_isolates_native_game_data(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", "/state/home")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-private-provider-credential")
    values = environment(tmp_path, steam=True)
    assert values["HOME"] == "/state/home"
    assert values["SteamAppId"] == "427520"
    assert values["XDG_DATA_HOME"] == str(tmp_path / "data")
    assert "DEEPSEEK_API_KEY" not in values


def test_each_episode_gets_its_own_profile_and_gameplay_unchanged(snapshot, installation, tmp_path):
    original = (snapshot / "start.zip").read_bytes()
    for name in ("one", "two"):
        profile = tmp_path / name
        configure(profile, snapshot, installation, {"session_id": name})
        assert (profile / "saves/start.zip").read_bytes() == original
        assert str(profile / "mods") in command(installation, profile)
        assert environment(profile)["HOME"] == str(profile / "home")
        assert json.loads((profile / "mods/mod-list.json").read_text())["mods"] == [
            {"name": "base", "enabled": True},
            {"name": "gamecua_evidence", "enabled": True},
        ]
        assert (
            'session_id = "' + name + '"'
            in (profile / "mods/gamecua_evidence_0.1.0/identity.lua").read_text()
        )
        info = json.loads((profile / "mods/gamecua_evidence_0.1.0/info.json").read_text())
        assert info["factorio_version"] == "2.0"
    assert (snapshot / "start.zip").read_bytes() == original


def test_stream_waits_for_full_lines_and_consumes_events_once(tmp_path):
    backend = object.__new__(Backend)
    backend.profile, backend.offset = tmp_path, 0
    path = backend.log_path()
    path.parent.mkdir(parents=True)
    first, second = sample(), sample(seq=2, tick=120)
    path.write_text(json.dumps(first) + '\n{"kind":')
    assert backend.read_rows() == [first]
    assert backend.read_rows() == []
    path.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n")
    assert backend.read_rows() == [second]
    assert backend.read_rows() == []
