"""Offline staging and Proton launch tests; no game is started."""

from pathlib import Path

import pytest

from gamecua.games.understand import setup

FIXTURE = Path(__file__).parents[1] / "fixtures/understand/zero-progress.sav"


@pytest.fixture
def official(tmp_path, monkeypatch):
    game = tmp_path / "steam/steamapps/common/Understand"
    game.mkdir(parents=True)
    for name in setup.FILES:
        (game / name).write_bytes(name.encode())
    (game / setup.SAVE).write_bytes(b"personal native progress")
    (game / "steam_autocloud.vdf").write_bytes(b"private account metadata")
    monkeypatch.setattr(setup, "steam_client", lambda: tmp_path / "steam")
    return game


def test_profile_never_copies_personal_save_or_cloud_metadata(official, tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / setup.SAVE).write_bytes(FIXTURE.read_bytes())
    original = (official / setup.SAVE).read_bytes()
    game = setup.stage_game(official, snapshot, tmp_path / "profile")
    assert (game / setup.SAVE).read_bytes() == FIXTURE.read_bytes()
    assert not (game / "steam_autocloud.vdf").exists()
    assert (tmp_path / "profile/prefix").is_dir()
    (game / setup.SAVE).write_bytes(b"private episode update")
    assert (official / setup.SAVE).read_bytes() == original
    assert (snapshot / setup.SAVE).read_bytes() == FIXTURE.read_bytes()
    with pytest.raises(FileExistsError):
        setup.stage_game(official, snapshot, tmp_path / "profile")


def test_proton_launch_sets_isolated_prefix_without_shell_commands(official, tmp_path):
    prefix = tmp_path / "prefix"
    command = setup.command(official)
    env = setup.environment(official, prefix)
    assert command[-1] == str(official / setup.BINARY)
    assert "waitforexitandrun" in command
    assert env["SteamAppId"] == "1299400"
    assert env["STEAM_COMPAT_DATA_PATH"] == str(prefix)
    assert env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] == str(setup.steam_client())
