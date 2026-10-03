"""Proton launch wrapper, compatibility mounts, process identity and snapshot loading."""

import json
import os

import pytest

from gamecua.games.civilization_vi import runtime, setup
from gamecua.games.civilization_vi.runtime import process_identity, profile_mounts, proton_paths


def test_proton_paths_split_profile_and_documents(tmp_path):
    paths = proton_paths(tmp_path / "steam client")
    prefix = (tmp_path / "steam client").resolve() / "steamapps/compatdata/289070/pfx"
    user = prefix / "drive_c/users/steamuser"
    assert paths == {
        "prefix": prefix,
        "profile": user / "AppData/Local/Firaxis Games/Sid Meier's Civilization VI",
        "saves": user / "Documents/My Games/Sid Meier's Civilization VI/Saves",
    }
    assert runtime.steam_ipc_command(tmp_path) == [
        str(tmp_path.resolve() / "steam.sh"),
        "-applaunch",
        "289070",
    ]


def test_bound_episode_profile_and_saves_are_exposed_once(tmp_path):
    client = tmp_path / "steam"
    paths = proton_paths(client)
    episode = tmp_path / "work/.profiles/trial/episode"
    (episode / "Saves").mkdir(parents=True)
    paths["profile"].parent.mkdir(parents=True)
    paths["saves"].parent.mkdir(parents=True)
    assert profile_mounts(client, "/existing") == "/existing"
    paths["profile"].symlink_to(episode, target_is_directory=True)
    paths["saves"].symlink_to(episode / "Saves", target_is_directory=True)
    assert profile_mounts(client, f"/existing:{episode}").split(":") == [
        "/existing",
        str(episode),
        str(episode / "Saves"),
    ]


def test_launcher_keeps_the_official_steam_chain_and_selects_dx11(tmp_path, monkeypatch):
    wrapper = tmp_path / "steam/ubuntu12_32/steam-launch-wrapper"
    target = tmp_path / "game/Base/Binaries/Win64Steam/CivilizationVI.exe"
    calls = []
    monkeypatch.setattr(os, "execvpe", lambda *args: calls.append(args))
    monkeypatch.delenv("STEAM_COMPAT_MOUNTS", raising=False)
    args = [
        str(wrapper),
        "--",
        "SteamLaunch",
        "AppId=289070",
        "--",
        str(target.with_name("CivilizationVI_DX12.exe")),
    ]
    runtime.main(args)
    executable, command, env = calls[0]
    assert executable == str(wrapper)
    assert command[:-1] == args[:-1] and command[-1] == str(target)
    assert env["DXVK_CONFIG"] == "dxvk.numCompilerThreads = 4"
    assert env["DISABLE_VK_LAYER_VALVE_steam_overlay_1"] == "1"
    assert "STEAM_COMPAT_MOUNTS" not in env


def test_process_identity_names_a_live_process():
    identity = process_identity(os.getpid())
    assert identity["pid"] == os.getpid() and identity["start_ticks"].isdigit()
    assert process_identity(os.getpid()) == identity


def test_start_save_accepts_any_captured_name(tmp_path):
    for name in ("GameCUAStart", "GameScientistStart", "Anything"):
        manifest = {
            f"profile/Saves/Single/{name}.Civ6Save": "a",
            "profile/Saves/Single/auto/AutoSave_0001.Civ6Save": "b",
        }
        assert setup.start_save(manifest) == f"profile/Saves/Single/{name}.Civ6Save"
    with pytest.raises(ValueError):
        setup.start_save({"profile/Saves/Single/auto/AutoSave_0001.Civ6Save": "b"})
    (tmp_path / "snapshot.manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "preparation.json").write_text(json.dumps({"civilization": "CIVILIZATION_AZTEC"}))
    assert setup.validate_snapshot(tmp_path) == (
        {"civilization": "CIVILIZATION_AZTEC"},
        "profile/Saves/Single/Anything.Civ6Save",
    )


def test_configure_sets_the_fixed_native_options(tmp_path):
    (tmp_path / "AppOptions.txt").write_text("EnableTuner 0\r\nPlayIntroVideo 1\r\nOther 3\r\n")
    (tmp_path / "UserOptions.txt").write_text("AutoSaveFrequency 5\nAutoEndTurn 1\n")
    setup.configure(tmp_path)
    options = (tmp_path / "AppOptions.txt").read_text()
    assert "EnableTuner 1\n" in options and "PlayIntroVideo 0\n" in options
    assert "Other 3" in options
    assert (tmp_path / "UserOptions.txt").read_text() == "AutoSaveFrequency 1\nAutoEndTurn 0\n"


def test_captured_snapshot_loads_with_its_native_baseline(tmp_path, monkeypatch):
    class Reader:
        def read(self):
            return {"native_player_id": 0, "turn": 1}

        def close(self):
            pass

    profile = tmp_path / "profile"
    profile.mkdir()
    for name in setup.CONFIG_FILES:
        (profile / name).write_text("EnableTuner 0\nAutoSaveFrequency 5\n")
    save = tmp_path / "first-turn.Civ6Save"
    save.write_bytes(b"native save")
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "plan.json").write_text("{}")
    monkeypatch.setattr(setup, "NativeBaseGame", Reader)
    output = setup.capture(profile, save, tmp_path / "snapshot", "CIVILIZATION_AZTEC", reference)
    preparation, start = setup.validate_snapshot(output)
    assert start == setup.START_SAVE
    assert (output / start).read_bytes() == b"native save"
    assert "EnableTuner 1" in (output / "profile/AppOptions.txt").read_text()
    assert preparation["evaluation"] == "base_game_v1"
    assert preparation["native_state"] == {"native_player_id": 0, "turn": 1}
