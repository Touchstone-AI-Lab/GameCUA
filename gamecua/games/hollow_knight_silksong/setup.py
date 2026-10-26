"""Read-only prepared-save snapshots and the Steam account that names the save directory."""

import ctypes
import os
import shutil
from pathlib import Path

from ...storage import sha256, write_json

APP_ID = 1030300
TITLE = "Hollow Knight Silksong"
DATA = f"{TITLE}_Data"
STEAM_API = f"{DATA}/Plugins/libsteam_api.so"
SAVES = Path("unity3d/Team Cherry") / TITLE
PREFS = Path("unity3d/unknown/unknown/prefs")
SAVE = "user1.dat"
SNAPSHOT_FILES = {SAVE: SAVE, "shared.dat": "shared.dat", "prefs": None}
ARGUMENTS = (
    "-force-glcore45",
    "-force-clamped",
    "-screen-fullscreen",
    "0",
    "-screen-width",
    "1280",
    "-screen-height",
    "720",
)


def default_installation():
    """Return the game folder of the default Steam client library."""
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".steam/debian-installation/steamapps/common" / TITLE


def steam_account(installation):
    """Return the logged-in Steam account ID through the game's own Steam API library."""
    os.environ["SteamAppId"] = str(APP_ID)
    os.environ["SteamGameId"] = str(APP_ID)
    api = ctypes.CDLL(str(Path(installation) / STEAM_API))
    api.SteamAPI_InitFlat.argtypes = [ctypes.c_void_p]
    api.SteamAPI_InitFlat.restype = ctypes.c_int
    if api.SteamAPI_InitFlat(ctypes.create_string_buffer(1024)) != 0:
        raise RuntimeError("A running, authorized official Steam client is required")
    try:
        api.SteamAPI_SteamUser_v023.restype = ctypes.c_void_p
        steam_id = api.SteamAPI_ISteamUser_GetSteamID
        steam_id.argtypes = [ctypes.c_void_p]
        steam_id.restype = ctypes.c_uint64
        return str(steam_id(api.SteamAPI_SteamUser_v023()) & 0xFFFFFFFF)
    finally:
        api.SteamAPI_Shutdown()


def save_directory(config):
    """Return the single save directory of a prepared profile."""
    root = Path(config) / SAVES
    return next(p for p in root.iterdir() if p.is_dir() and (p / SAVE).is_file())


def capture_snapshot(config, installation, target):
    """Copy a prepared profile's slot-1 save, shared data and preferences."""
    config, target = Path(config), Path(target)
    saves = save_directory(config)
    target.mkdir(parents=True)
    for name, relative in SNAPSHOT_FILES.items():
        shutil.copyfile(config / PREFS if relative is None else saves / relative, target / name)
    write_json(
        target / "snapshot.manifest.json",
        {name: sha256(target / name) for name in sorted(SNAPSHOT_FILES)},
    )
    return target
