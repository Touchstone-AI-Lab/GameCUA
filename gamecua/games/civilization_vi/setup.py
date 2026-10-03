"""Private prepared base-game snapshots for the official Steam Proton client."""

import argparse
import json
import re
import shutil
from pathlib import Path

from ...storage import local_file, sha256, write_json
from .base_game import NativeBaseGame

CONFIG_FILES = (
    "AppOptions.txt",
    "GraphicsOptions.txt",
    "UserOptions.txt",
    "InputSettings.json",
    "Mods.sqlite",
)
OPTIONAL_CONFIG_FILES = ("EOSOptions.txt", "SoundOpts.txt")
SETTINGS = {
    "AppOptions.txt": {
        "PlayIntroVideo": 0,
        "EnableAudio": 0,
        "MaxJobThreads": 4,
        "MaxGameCoreThreads": 4,
        "EnableGameCoreEventLog": 1,
        "EnableTuner": 1,
    },
    "UserOptions.txt": {"AutoSaveFrequency": 1, "AutoEndTurn": 0},
}
START_SAVE = "profile/Saves/Single/GameCUAStart.Civ6Save"


def configure(profile):
    """Apply the fixed native options, including tuner access for the evaluator."""
    for name, values in SETTINGS.items():
        path = Path(profile) / name
        text = path.read_text()
        for key, value in values.items():
            text = re.sub(r"(?m)^" + key + r"\s+[^\r\n]+", f"{key} {value}", text)
        path.write_text(text)


def capture(profile, save, output, civilization, reference):
    """Write a snapshot from a native profile, its first-turn save and the loading references."""
    profile, save, output, reference = (
        Path(path).resolve() for path in (profile, save, output, reference)
    )
    reader = NativeBaseGame()
    try:
        native_state = reader.read()
    finally:
        reader.close()
    (output / "profile").mkdir(parents=True)
    for name in CONFIG_FILES:
        shutil.copyfile(profile / name, output / "profile" / name)
    for name in OPTIONAL_CONFIG_FILES:
        if (profile / name).is_file():
            shutil.copyfile(profile / name, output / "profile" / name)
    configure(output / "profile")
    target = output / START_SAVE
    target.parent.mkdir(parents=True)
    shutil.copyfile(save, target)
    auto = output / "profile/Saves/Single/auto/AutoSave_0001.Civ6Save"
    auto.parent.mkdir()
    shutil.copyfile(save, auto)
    shutil.copytree(reference, output / "reference")
    write_json(
        output / "preparation.json",
        {
            "schema_version": 1,
            "runtime": "steam_proton",
            "civilization": civilization,
            "save_sha256": sha256(target),
            "procedure": "Official native first-turn save captured through ordinary game controls; fixed prepared spawn, not a claim of a fresh seed-generated run.",
            "community_mods": [],
            "evaluation": "base_game_v1",
            "native_player_id": native_state["native_player_id"],
            "native_state": native_state,
        },
    )
    write_json(
        output / "snapshot.manifest.json",
        {
            str(path.relative_to(output)): sha256(path)
            for path in output.rglob("*")
            if path.is_file()
        },
    )
    return output


def start_save(manifest):
    """Return the snapshot's single prepared start save, whatever name it was captured under."""
    saves = [
        name
        for name in manifest
        if name.startswith("profile/Saves/Single/")
        and name.count("/") == 3
        and name.endswith(".Civ6Save")
    ]
    if len(saves) != 1:
        raise ValueError("Prepared snapshot needs exactly one start save")
    return saves[0]


def validate_snapshot(snapshot):
    """Return the snapshot's preparation record and the name of its single start save."""
    snapshot = Path(snapshot)
    manifest = json.loads((snapshot / "snapshot.manifest.json").read_text())
    preparation = json.loads(local_file(snapshot, "preparation.json").read_text())
    return preparation, start_save(manifest)


def main():
    parser = argparse.ArgumentParser(description="Capture a private Civilization VI prepared save")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--save", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--civilization", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    print(capture(args.profile, args.save, args.output, args.civilization, args.reference))


if __name__ == "__main__":
    main()
