"""Licensed Factorio installs, prepared saves and isolated native profiles."""

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from ...storage import write_json
from .instrumentation import CONTROL

MOD = "gamecua_evidence"
SAVE = "start.zip"
APP_ID = 427520


def installation_identity(installation):
    """Return the game version and distribution of a Linux64 Factorio installation."""
    installation = Path(installation).resolve()
    output = subprocess.check_output(
        [str(installation / "bin/x64/factorio"), "--version"], text=True, timeout=30
    )
    version = re.search(r"Version: (2\.[01]\.\d+)\b", output)
    edition = re.search(r"linux64,\s*(full|steam)\b", output)
    if not version or not edition:
        raise ValueError(
            "Provide a licensed Linux64 full or Steam Factorio 2.0 or 2.1 installation"
        )
    steam = edition[1] == "steam" or any(installation.rglob("libsteam_api.so"))
    return {
        "game_version": version[1],
        "distribution": "steam" if steam else "licensed_standalone",
    }


def capture_snapshot(source, target, installation, seed, procedure, preset=None):
    """Copy a prepared native save and record how it was prepared."""
    target = Path(target).resolve()
    target.mkdir(parents=True)
    shutil.copyfile(source, target / SAVE)
    preparation = {
        "installation": installation_identity(installation),
        "seed": seed,
        "procedure": procedure,
        "content": "base-only singleplayer Nauvis; no Space Age, quality or elevated rails",
        "experiment_kind": "prepared_state",
    }
    if preset is not None:
        preparation["preset"] = preset
    write_json(target / "preparation.json", preparation)
    return target


def configure(profile, snapshot, installation, identity):
    """Create an isolated profile with the start save and the evidence mod."""
    profile, snapshot, installation = map(Path, (profile, snapshot, installation))
    version = json.loads((snapshot / "preparation.json").read_text())["installation"][
        "game_version"
    ]
    profile.mkdir(parents=True, exist_ok=False)
    (profile / "saves").mkdir()
    shutil.copyfile(snapshot / SAVE, profile / "saves" / SAVE)
    mod = profile / "mods" / f"{MOD}_0.1.0"
    mod.mkdir(parents=True)
    write_json(
        mod / "info.json",
        {
            "name": MOD,
            "version": "0.1.0",
            "title": "GameCUA native evidence",
            "author": "GameCUA",
            "factorio_version": ".".join(version.split(".")[:2]),
            "dependencies": ["base >= 2.0.0"],
            "description": "Private read-only evaluator telemetry; no gameplay modifications.",
        },
    )
    (mod / "control.lua").write_text(CONTROL)
    (mod / "identity.lua").write_text(
        "return {\n"
        + "\n".join(f"    {key} = {json.dumps(value)}," for key, value in identity.items())
        + "\n}\n"
    )
    write_json(
        profile / "mods/mod-list.json",
        {"mods": [{"name": "base", "enabled": True}, {"name": MOD, "enabled": True}]},
    )
    (profile / "config.ini").write_text(
        f"[path]\nread-data={installation / 'data'}\nwrite-data={profile}\n"
        "[general]\nlocale=en\ncheck-updates=false\n"
        "[graphics]\nfull-screen=false\nwindow-width=1280\nwindow-height=720\n"
        "graphics-quality=normal\nmax-threads=4\n"
        "[sound]\nmaster-volume=0\n"
        "[controls]\nmine=J\n"
    )


def command(installation, profile):
    """Build the native launch command for one profile."""
    installation, profile = Path(installation), Path(profile)
    return [
        str(installation / "bin/x64/factorio"),
        "--config",
        str(profile / "config.ini"),
        "--mod-directory",
        str(profile / "mods"),
        "--load-game",
        str(profile / "saves" / SAVE),
    ]


def environment(profile, steam=False):
    """Return a launch environment without provider keys and with isolated user data."""
    profile = Path(profile)
    values = dict(
        {key: value for key, value in os.environ.items() if not key.endswith("API_KEY")},
        HOME=str(profile / "home"),
        XDG_CONFIG_HOME=str(profile / "config"),
        XDG_DATA_HOME=str(profile / "data"),
        XDG_CACHE_HOME=str(profile / "cache"),
        SDL_AUDIODRIVER="dummy",
        SDL_VIDEODRIVER="x11",
    )
    if steam:
        values.update(HOME=os.environ["HOME"], SteamAppId=str(APP_ID), SteamGameId=str(APP_ID))
    return values


def main():
    """Capture a Factorio snapshot from the command line."""
    parser = argparse.ArgumentParser(description="Copy a licensed Factorio prepared save")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--installation", type=Path, required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--procedure", required=True)
    parser.add_argument("--preset", choices=["death-world-marathon"])
    args = parser.parse_args()
    print(
        capture_snapshot(
            args.source, args.output, args.installation, args.seed, args.procedure, args.preset
        )
    )


if __name__ == "__main__":
    main()
