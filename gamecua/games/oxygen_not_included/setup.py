"""ONI snapshot preparation and private native Linux profiles."""

import argparse
import os
import shutil
from pathlib import Path

from ...storage import write_json
from .native import read_save

BINARY = "OxygenNotIncluded"


def config_dir(profile):
    """Return the game's configuration directory inside a profile."""
    return Path(profile) / "home/.config/unity3d/Klei/Oxygen Not Included"


def environment(profile):
    """Return the game environment with a private HOME and no provider keys."""
    profile = Path(profile).resolve()
    values = {key: value for key, value in os.environ.items() if not key.endswith("_API_KEY")}
    values.update(
        HOME=str(profile / "home"),
        XDG_CONFIG_HOME=str(profile / "home/.config"),
        XDG_DATA_HOME=str(profile / "home/.local/share"),
        SteamAppId="457140",
        SteamGameId="457140",
        SDL_AUDIODRIVER="dummy",
    )
    return values


def command(profile):
    """Return the windowed 1280x720 launch command for a profile."""
    profile = Path(profile).resolve()
    return [
        str(profile / "game" / BINARY),
        "-screen-width",
        "1280",
        "-screen-height",
        "720",
        "-screen-fullscreen",
        "0",
        "-logFile",
        str(profile / "Player.local.log"),
    ]


def stage_launcher(installation, profile):
    """Copy the executable into the profile and link the read-only game assets."""
    installation, profile = Path(installation).resolve(), Path(profile).resolve()
    if (installation / "debug_enable.txt").exists():
        raise ValueError("Disable ONI debug mode before preparation")
    target = profile / "game"
    target.mkdir()
    shutil.copy2(installation / BINARY, target / BINARY)
    for name in (
        "OxygenNotIncluded_Data",
        "UnityPlayer.so",
        "libdecor-0.so.0",
        "libdecor-cairo.so",
    ):
        (target / name).symlink_to(installation / name)


def link_steam_runtime(profile, steam_home="/state/home"):
    """Link only the running Steam client's runtime files into the profile."""
    target = Path(profile) / "home/.steam"
    target.mkdir()
    for name in ("sdk64", "steam.pid", "steam.token"):
        (target / name).symlink_to(Path(steam_home) / ".steam" / name)


def capture_snapshot(source, target):
    """Store an operator-supplied cycle-zero save as a new snapshot directory."""
    raw = Path(source).read_bytes()
    target = Path(target)
    target.mkdir(parents=True)
    (target / "initial.sav").write_bytes(raw)
    write_json(target / "preparation.json", {"initial": read_save(raw)})
    return target


def install_profile(snapshot, profile):
    """Create a private profile holding the snapshot save and return its bytes."""
    raw = (Path(snapshot) / "initial.sav").read_bytes()
    target = config_dir(profile) / "save_files/benchmark"
    target.mkdir(parents=True)
    (target / "benchmark.sav").write_bytes(raw)
    expansion = int(read_save(raw)["dlc_ids"] == ["EXPANSION1_ID"])
    preferences = "strings: {}\nints:\n" + f"  EXPANSION1_ID.ENABLED: {expansion}\n"
    preferences += "".join(f"  DLC{number}_ID.ENABLED: 0\n" for number in range(2, 6))
    (config_dir(profile) / "kplayerprefs.yaml").write_text(preferences + "floats: {}\n")
    (Path(profile) / "home/.local/share").mkdir(parents=True)
    return raw


def main():
    """Capture a snapshot from the command line."""
    parser = argparse.ArgumentParser(description="Capture a native ONI preparation save")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(capture_snapshot(args.source, args.output))


if __name__ == "__main__":
    main()
