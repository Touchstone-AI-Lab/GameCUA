"""Read-only prepared-save snapshots and isolated per-episode Stardew Valley profiles."""

import os
import shutil
from pathlib import Path

from ...storage import sha256, write_json

BINARY = "Stardew Valley"


def config_dir(profile):
    """Return the game's configuration folder inside an isolated profile."""
    return Path(profile) / "home/.config/StardewValley"


def environment(profile):
    """Point the game's home and XDG folders at the isolated profile."""
    profile = Path(profile).resolve()
    return dict(
        os.environ,
        HOME=str(profile / "home"),
        XDG_CONFIG_HOME=str(profile / "home/.config"),
        XDG_DATA_HOME=str(profile / "home/.local/share"),
        SDL_AUDIODRIVER="dummy",
        SDL_VIDEODRIVER="x11",
    )


def save_slot(folder):
    """Return the single save slot folder and its main save file."""
    slot = next(p for p in (Path(folder) / "Saves").iterdir() if p.is_dir())
    return slot, slot / slot.name


def capture_snapshot(source, target):
    """Copy a prepared profile's save slot and startup preferences."""
    source, target = Path(source), Path(target)
    slot, _ = save_slot(source)
    (target / "Saves" / slot.name).mkdir(parents=True)
    for name in (slot.name, "SaveGameInfo"):
        shutil.copyfile(slot / name, target / "Saves" / slot.name / name)
    if (source / "startup_preferences").exists():
        shutil.copyfile(source / "startup_preferences", target / "startup_preferences")
    write_json(
        target / "snapshot.manifest.json",
        {str(p.relative_to(target)): sha256(p) for p in sorted(target.rglob("*")) if p.is_file()},
    )
    return target
