"""Native campaign preparation snapshot for Left 4 Dead 2."""

import json
import shutil
from pathlib import Path


def create_snapshot(installation, videodefaults, output):
    """Freeze the key bindings and native low graphics files for new episodes."""
    installation, videodefaults, output = Path(installation), Path(videodefaults), Path(output)
    output.mkdir(parents=True)
    shutil.copy2(Path(__file__).with_name("baseline.cfg"), output / "baseline.cfg")
    shutil.copy2(installation / "left4dead2/cfg/video_bench_low.txt", output / "video.txt")
    shutil.copy2(videodefaults, output / "videodefaults.txt")
    preparation = {
        "schema_version": 1,
        "map": "c1m1_hotel",
        "mode": "coop",
        "difficulty": "Easy",
        "cheats": 0,
        "teammates": "three native survivor bots",
        "experiment_kind": "fresh_campaign",
        "resolution": [640, 360],
        "graphics_preset": "native_low",
        "renderer": "vulkan_software",
    }
    (output / "preparation.json").write_text(json.dumps(preparation, indent=2) + "\n")
    return output
