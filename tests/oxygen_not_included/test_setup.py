"""Snapshot capture, private profiles and the staged native launcher."""

import pytest

from gamecua.games.oxygen_not_included.setup import (
    capture_snapshot,
    command,
    config_dir,
    environment,
    install_profile,
    link_steam_runtime,
    stage_launcher,
)

from .test_native import synthetic_save


def test_snapshot_is_copied_into_independent_profiles(tmp_path):
    source = tmp_path / "personal/save.sav"
    source.parent.mkdir()
    raw = synthetic_save()
    source.write_bytes(raw)
    snapshot = capture_snapshot(source, tmp_path / "snapshot")
    first, second = tmp_path / "first", tmp_path / "second"
    assert install_profile(snapshot, first) == raw
    install_profile(snapshot, second)
    (config_dir(first) / "save_files/benchmark/benchmark.sav").write_bytes(b"changed")
    assert source.read_bytes() == raw
    assert (config_dir(second) / "save_files/benchmark/benchmark.sav").read_bytes() == raw
    assert not (first / "home/.steam").exists()
    with pytest.raises(FileExistsError):
        capture_snapshot(source, snapshot)


@pytest.mark.parametrize("dlc_ids", [[""], ["EXPANSION1_ID"]])
def test_profile_selects_the_snapshot_game_mode(tmp_path, dlc_ids):
    source = tmp_path / "source.sav"
    source.write_bytes(synthetic_save(dlc_ids=dlc_ids))
    profile = tmp_path / "profile"
    install_profile(capture_snapshot(source, tmp_path / "snapshot"), profile)
    preferences = (config_dir(profile) / "kplayerprefs.yaml").read_text()
    assert f"EXPANSION1_ID.ENABLED: {int(dlc_ids == ['EXPANSION1_ID'])}" in preferences
    assert "DLC2_ID.ENABLED: 0" in preferences


def test_game_environment_drops_provider_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-secret")
    values = environment(tmp_path)
    assert "DEEPSEEK_API_KEY" not in values
    assert values["HOME"] == str(tmp_path / "home")
    assert values["SteamAppId"] == "457140"
    assert command(tmp_path)[0] == str(tmp_path.resolve() / "game/OxygenNotIncluded")


def test_launcher_copy_keeps_the_lock_private_and_refuses_debug_mode(tmp_path):
    installation, profile = tmp_path / "installation", tmp_path / "profile"
    (installation / "OxygenNotIncluded_Data").mkdir(parents=True)
    profile.mkdir()
    (installation / "OxygenNotIncluded").write_bytes(b"executable")
    stage_launcher(installation, profile)
    (profile / "game/unity.lock").write_bytes(b"private")
    assert not (installation / "unity.lock").exists()
    assert (profile / "game/OxygenNotIncluded").read_bytes() == b"executable"
    data = installation / "OxygenNotIncluded_Data"
    assert (profile / "game/OxygenNotIncluded_Data").resolve() == data.resolve()
    (installation / "debug_enable.txt").touch()
    with pytest.raises(ValueError, match="debug"):
        stage_launcher(installation, tmp_path / "other")


def test_steam_links_exclude_personal_account_and_save_directories(tmp_path):
    home, profile = tmp_path / "steam-home", tmp_path / "profile"
    (home / ".steam/sdk64").mkdir(parents=True)
    (home / ".steam/config").mkdir()
    (profile / "home").mkdir(parents=True)
    link_steam_runtime(profile, home)
    assert {p.name for p in (profile / "home/.steam").iterdir()} == {
        "sdk64",
        "steam.pid",
        "steam.token",
    }
    assert not (profile / "home/.steam/config").exists()
