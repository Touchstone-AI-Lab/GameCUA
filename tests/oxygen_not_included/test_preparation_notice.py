"""Recognize the observed native Mod Events title without loosening cue tolerance."""

from pathlib import Path

from PIL import Image

from gamecua.games.oxygen_not_included.ui import preparation_action


def test_native_mod_events_title_selects_only_ordinary_ok():
    image = Image.new("RGB", (1280, 720))
    with Image.open(Path(__file__).parent / "fixtures/preparation/mod-events-title.png") as crop:
        image.paste(crop, (421, 251))
    assert preparation_action(image) == (
        "mod_notice",
        {"type": "click", "x": 0.5, "y": 0.597, "button": "left"},
    )


def test_missing_mod_events_title_does_not_click():
    assert preparation_action(Image.new("RGB", (1280, 720))) is None
