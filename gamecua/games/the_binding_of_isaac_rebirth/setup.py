"""Repentance under Proton: launch command, isolated data directory and seeded snapshots."""

import os
import re
from pathlib import Path

from ...storage import write_json

APP_ID = 250900
BINARY = "isaac-ng.exe"
BUILD = "Repentance v1.7.9b.J835 (Windows, Steam build 22878971)"
DATA_DIRECTORY = "Binding of Isaac Repentance"
PROTON = "Proton - Experimental"
RUNTIME = "SteamLinuxRuntime_4"
DOCUMENTS = Path("pfx/drive_c/users/steamuser/Documents/My Games")
DEFAULT_SEED = "MVSN TFS1"
OPTIONS = {
    "Language": "0",
    "MusicVolume": "0.0000",
    "MusicEnabled": "0",
    "SFXVolume": "0.0000",
    "MapOpacity": "0.3000",
    "Fullscreen": "0",
    "Filter": "0",
    "Exposure": "1.0000",
    "Gamma": "1.0000",
    "ControllerHotplug": "0",
    "PopUps": "1",
    "CameraStyle": "1",
    "ShowRecentItems": "0",
    "HudOffset": "1.0000",
    "TryImportSave": "0",
    "FoundHUD": "0",
    "EnableMods": "0",
    "RumbleEnabled": "0",
    "ChargeBars": "0",
    "BulletVisibility": "0",
    "TouchMode": "0",
    "AimLock": "1",
    "EnableDebugConsole": "0",
    "MaxScale": "99",
    "MaxRenderScale": "2",
    "VSync": "1",
    "PauseOnFocusLost": "0",
    "SteamCloud": "0",
    "MouseControl": "0",
    "BossHpOnBottom": "1",
    "AnnouncerVoiceMode": "0",
    "ConsoleFont": "0",
    "FadedConsoleDisplay": "0",
    "SaveCommandHistory": "0",
    "WindowWidth": "1280",
    "WindowHeight": "720",
    "WindowPosX": "0",
    "WindowPosY": "0",
}


def steam_client():
    return Path(os.environ.get("HOME", str(Path.home()))) / ".steam/debian-installation"


def default_installation():
    return steam_client() / "steamapps/common/The Binding of Isaac Rebirth"


def proton_identity():
    common = steam_client() / "steamapps/common"
    return {"proton": (common / PROTON / "version").read_text().strip(), "runtime": RUNTIME}


def normalize_seed(seed):
    """Format a seed as two groups of four upper-case characters."""
    compact = re.sub(r"\s+", "", seed).upper()
    return f"{compact[:4]} {compact[4:]}"


def installation_identity(installation):
    return {"build": BUILD, "app_id": APP_ID, **proton_identity()}


def data_directory(prefix):
    return Path(prefix) / DOCUMENTS / DATA_DIRECTORY


def command(installation):
    common = steam_client() / "steamapps/common"
    return [
        str(common / RUNTIME / "_v2-entry-point"),
        "--verb=waitforexitandrun",
        "--",
        str(common / PROTON / "proton"),
        "waitforexitandrun",
        str(Path(installation) / BINARY),
    ]


def environment(installation, prefix):
    return dict(
        os.environ,
        STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam_client()),
        STEAM_COMPAT_DATA_PATH=str(prefix),
        STEAM_COMPAT_MOUNTS=str(Path(installation).resolve()),
        PROTON_NO_FSYNC="1",
        PROTON_NO_ESYNC="1",
        SteamAppId=str(APP_ID),
        SteamGameId=str(APP_ID),
    )


def create_snapshot(installation, output, seed=DEFAULT_SEED):
    """Write a zero-progression data directory and the fixed seed for new episodes."""
    output = Path(output).resolve()
    data = output / "data" / DATA_DIRECTORY
    data.mkdir(parents=True)
    (data / "options.ini").write_text(
        "[Options]\n" + "".join(f"{key}={value}\n" for key, value in OPTIONS.items())
    )
    write_json(
        output / "GOLDEN.json",
        {
            "id": output.name,
            "derivation": "Generated zero-progression Repentance data directory with Steam Cloud and mods disabled; every episode starts a fresh seeded Normal run as Isaac",
            "seed": normalize_seed(seed),
            "character": "Isaac",
            "difficulty": "normal",
            "build": BUILD,
        },
    )
    return output
