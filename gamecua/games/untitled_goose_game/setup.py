"""Official Steam/Proton launch paths and clean title-screen snapshots."""

import os
import shutil
from pathlib import Path

from ...storage import write_json

APP_ID = 837470
BINARY = "Untitled.exe"
SAVE_DIRECTORY = Path(
    "pfx/drive_c/users/steamuser/AppData/LocalLow/House House/Untitled Goose Game"
)
PROTON_METADATA = ("config_info", "tracked_files", "version")


def capture_snapshot(installation, compatdata, target):
    """Copy a launched Proton prefix without slot saves as the title-screen start state."""
    compatdata, target = Path(compatdata).resolve(), Path(target).resolve()
    target.mkdir(parents=True)
    shutil.copytree(compatdata / "pfx", target / "pfx", symlinks=True)
    copy_external_file_links(target)
    for name in PROTON_METADATA:
        shutil.copy2(compatdata / name, target / name)
    for path in (target / SAVE_DIRECTORY).glob("savegame*.save"):
        path.unlink()
    write_json(
        target / "preparation.json",
        {
            "schema_version": 1,
            "app_id": APP_ID,
            "installation": str(Path(installation).resolve()),
            "initial_state": "title_screen_without_slot_saves",
        },
    )
    return target


def copy_external_file_links(target):
    """Replace prefix symlinks to files outside the snapshot with copies."""
    for path in sorted((target / "pfx").rglob("*")):
        if not path.is_symlink():
            continue
        resolved = path.resolve()
        if resolved.is_file() and not resolved.is_relative_to(target):
            path.unlink()
            shutil.copy2(resolved, path)


def environment(profile, client):
    """Return the Proton launch environment for one isolated profile."""
    return dict(
        os.environ,
        SteamAppId=str(APP_ID),
        SteamGameId=str(APP_ID),
        STEAM_COMPAT_APP_ID=str(APP_ID),
        STEAM_COMPAT_CLIENT_INSTALL_PATH=str(client),
        STEAM_COMPAT_DATA_PATH=str(Path(profile).resolve()),
        PROTON_USE_WINED3D="1",
        WINEDEBUG="-all",
    )
