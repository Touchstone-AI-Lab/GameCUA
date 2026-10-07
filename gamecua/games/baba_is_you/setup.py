"""Fresh-start Baba Is You snapshots and isolated per-episode native profiles."""

import argparse
import json
import os
import shutil
from pathlib import Path

from ...storage import write_json
from .saves import read_save

BINARY = "bin64/Chowdren"
SETTINGS = "SettingsC.txt"
SLOTS = ("0ba.ba", "1ba.ba", "2ba.ba")


def data_dir(profile):
    return Path(profile) / "home/.local/share/Baba_Is_You"


def environment(profile):
    profile = Path(profile).resolve()
    return dict(
        os.environ,
        HOME=str(profile / "home"),
        XDG_DATA_HOME=str(profile / "home/.local/share"),
        SDL_AUDIODRIVER="dummy",
    )


def command(installation):
    return [str(Path(installation) / BINARY)]


def slot_paths(profile):
    return [data_dir(profile) / name for name in SLOTS]


def capture_snapshot(settings, target):
    """Freeze the game's default settings file as the starting state."""
    settings, target = Path(settings).resolve(), Path(target).resolve()
    (target / "Baba_Is_You").mkdir(parents=True)
    shutil.copyfile(settings, target / "Baba_Is_You" / SETTINGS)
    write_json(
        target / "preparation.json",
        {
            "derivation": "Default native settings written by the game on first launch; no slot save. Each episode starts a new game whose first screen is the opening level.",
            "initial_state": read_save(b""),
        },
    )
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(str(capture_snapshot(args.settings, args.output))))


if __name__ == "__main__":
    main()
