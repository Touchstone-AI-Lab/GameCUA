"""Stage the licensed game and a frozen zero-progress save for an isolated Proton launch."""

import os
import shutil
from pathlib import Path

APP_ID = 1299400
BINARY = "understand.exe"
SAVE = "understand.sav"
PROTON = "Proton - Experimental"
RUNTIME = "SteamLinuxRuntime_4"
FILES = (
    BINARY,
    "SDL2.dll",
    "love.dll",
    "steam_api64.dll",
    "steam_api.dll",
    "msvcr120.dll",
    "lua51.dll",
    "OpenAL32.dll",
    "json.lua",
    "msvcp120.dll",
    "steam_appid.txt",
    "ffi.dll",
    "mpg123.dll",
)


def steam_client():
    return Path.home() / ".steam/debian-installation"


def command(game):
    common = steam_client() / "steamapps/common"
    return [
        str(common / RUNTIME / "_v2-entry-point"),
        "--verb=waitforexitandrun",
        "--",
        str(common / PROTON / "proton"),
        "waitforexitandrun",
        str(Path(game) / BINARY),
    ]


def environment(game, prefix):
    return dict(
        os.environ,
        STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam_client()),
        STEAM_COMPAT_DATA_PATH=str(prefix),
        STEAM_COMPAT_MOUNTS=str(Path(game).resolve()),
        PROTON_NO_FSYNC="1",
        PROTON_NO_ESYNC="1",
        SteamAppId=str(APP_ID),
        SteamGameId=str(APP_ID),
        SDL_AUDIODRIVER="dummy",
    )


def stage_game(installation, snapshot, profile):
    game = Path(profile) / "game"
    game.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copyfile(Path(installation) / name, game / name)
    shutil.copyfile(Path(snapshot) / SAVE, game / SAVE)
    (Path(profile) / "prefix").mkdir(exist_ok=False)
    return game
