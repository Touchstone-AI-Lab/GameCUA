"""Capture the fresh native settings, decoder key and setup screens of the licensed client."""

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image

from ...storage import sha256, write_json
from .saves import discover_key

SCREENS = ("title-menu.png", "new-menu.png", "office-start.png")


def screen_matches(image, reference, box):
    """Compare the visible pixels of a setup screen region with its reference capture."""
    expected = Image.open(reference).convert("RGB").crop(box)
    actual = image.convert("RGB").crop(box)
    selected = [(a, b) for a, b in zip(expected.getdata(), actual.getdata()) if max(a) >= 40]
    matching = sum(max(abs(x - y) for x, y in zip(a, b)) <= 25 for a, b in selected)
    return matching / len(selected) >= 0.90


def capture_snapshot(profile, installation, references, output):
    """Copy a fresh profile's settings and setup screens with the discovered decoder key."""
    profile, installation, references, output = map(
        Path, (profile, installation, references, output)
    )
    key = discover_key(
        (installation / "PapersPlease_Data/il2cpp_data/Metadata/global-metadata.dat").read_bytes(),
        (profile / "settings.sav").read_bytes(),
    )
    output.mkdir(parents=True)
    shutil.copy2(profile / "settings.sav", output / "settings.sav")
    for name in SCREENS:
        shutil.copy2(references / name, output / name)
    write_json(output / "preparation.json", {"decoder_key": key.hex()})
    write_json(
        output / "snapshot.manifest.json",
        {name: sha256(output / name) for name in ("settings.sav", "preparation.json", *SCREENS)},
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("profile", "installation", "references", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "snapshot": str(
                    capture_snapshot(args.profile, args.installation, args.references, args.output)
                )
            }
        )
    )
