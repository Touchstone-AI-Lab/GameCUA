"""Check the shared pointer profile and the game-specific frozen drag time budget."""

from pathlib import Path

import pytest

from gamecua.desktop import X11Desktop
from gamecua.games.papers_please.desktop import Desktop
from gamecua.specs import InputProfile


def test_shared_profile_offers_only_left_click_and_drag():
    root = Path(__file__).resolve().parents[2]
    profile = InputProfile.model_validate_json(
        (root / "benchmarks/inputs/papers-please/pointer-v1.json").read_text()
    )
    buttons = profile.groups["input"].buttons
    assert {name: button.pointer for name, button in buttons.items()} == {
        "click_target": "left",
        "drag_target": "drag",
    }


@pytest.mark.parametrize(("duration", "expected"), [(1.0, 0.8), (0.4, 0.4)])
def test_frozen_drag_reserves_the_native_hover_interval(monkeypatch, duration, expected):
    executed = []
    monkeypatch.setattr(
        X11Desktop, "_execute", lambda self, action, **kwargs: executed.append(action)
    )
    desktop = Desktop.__new__(Desktop)
    desktop.step_seconds = 1.0
    desktop._execute(
        {"type": "drag", "x": 0.3, "y": 0.6, "to_x": 0.6, "to_y": 0.6, "duration": duration}
    )
    assert [a["type"] for a in executed] == ["pointer", "wait", "drag"]
    assert executed[1]["seconds"] == 0.2
    assert executed[2]["duration"] == expected
    assert executed[1]["seconds"] + executed[2]["duration"] <= desktop.step_seconds
