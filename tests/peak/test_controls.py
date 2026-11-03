"""Shared PEAK controls preserve free actions and translate only declared aliases."""

import pytest

from gamecua.games.peak.desktop import Desktop, translate


def test_aliases_combine_climbing_and_mouse_without_mutating_the_action():
    action = {"type": "control", "keys": ["w", "space", "Right", "j"], "duration": 1.0}
    result = translate(action)
    assert result["keys"] == ["w", "space"]
    assert result["buttons"] == ["left"]
    assert result["dx"] == 600 and result["dy"] == 0
    assert action["keys"] == ["w", "space", "Right", "j"]


def test_free_pointer_actions_and_explicit_mouse_buttons_are_preserved():
    pointer = {"type": "pointer", "x": 0.4, "y": 0.6, "button": "left"}
    assert translate(pointer) == pointer
    result = translate(
        {"type": "control", "keys": ["k"], "buttons": ["right"], "dx": 12, "duration": 0.5}
    )
    assert result["buttons"] == ["right"] and result["dx"] == 12


def test_aliases_keep_the_shared_action_bounds():
    with pytest.raises(ValueError, match="finite number"):
        translate({"type": "control", "keys": ["Right"], "dx": 2048, "duration": 1})


def test_desktop_delegates_aliases_with_the_original_cancellation_and_deadline(monkeypatch):
    from gamecua.desktop import X11Desktop

    calls = []
    monkeypatch.setattr(
        X11Desktop, "_execute", lambda self, action, **kwargs: calls.append((action, kwargs))
    )
    stop = object()
    object.__new__(Desktop)._execute(
        {"type": "control", "keys": ["Up"], "duration": 1}, stop=stop, deadline=12
    )
    assert calls[0][0]["dy"] == -600
    assert calls[0][1] == {"stop": stop, "deadline": 12}
