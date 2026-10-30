"""A hover delay must never duplicate a click or exceed cancellation and deadline guards."""

import copy

import pytest

from gamecua.desktop import X11Desktop
from gamecua.games.dont_starve import desktop


class Stop:
    def __init__(self, clock, cancel=False):
        self.clock, self.cancel, self.waits = clock, cancel, []

    def wait(self, seconds):
        self.waits.append(seconds)
        self.clock[0] += seconds
        return self.cancel


def adapter(monkeypatch):
    calls, releases, clock = [], [], [10.0]
    monkeypatch.setattr(desktop.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        X11Desktop, "_execute", lambda self, action, **kwargs: calls.append(copy.deepcopy(action))
    )
    monkeypatch.setattr(X11Desktop, "release_all", lambda self: releases.append(True))
    return object.__new__(desktop.Desktop), calls, releases, clock


@pytest.mark.parametrize(
    "action",
    [
        {"type": "pointer", "x": 0.8, "y": 0.2, "button": "left"},
        {"type": "pointer", "x": 0.2, "y": 0.8, "button": "right"},
        {"type": "drag", "x": 0.2, "y": 0.8, "to_x": 0.7, "to_y": 0.3, "duration": 1.5},
    ],
)
def test_native_pointer_waits_before_single_button_action(monkeypatch, action):
    target, calls, releases, clock = adapter(monkeypatch)
    original = copy.deepcopy(action)
    stop = Stop(clock)
    target.execute(action, stop=stop, deadline=12)
    assert calls == [{"type": "pointer", "x": action["x"], "y": action["y"]}, original]
    assert action == original
    assert stop.waits == [0.2]
    assert releases == [True]


@pytest.mark.parametrize("cancel,deadline", [(True, 12), (False, 10.05)])
def test_cancel_or_deadline_during_hover_never_presses_button(monkeypatch, cancel, deadline):
    target, calls, releases, clock = adapter(monkeypatch)
    stop = Stop(clock, cancel)
    with pytest.raises(InterruptedError):
        target.execute(
            {"type": "pointer", "x": 0.3, "y": 0.7, "button": "left"}, stop=stop, deadline=deadline
        )
    assert calls == [{"type": "pointer", "x": 0.3, "y": 0.7}]
    assert clock[0] <= deadline
    assert releases == [True]


def test_hover_without_button_has_no_added_delay(monkeypatch):
    target, calls, releases, clock = adapter(monkeypatch)
    stop = Stop(clock)
    action = {"type": "pointer", "x": 0.3, "y": 0.7}
    target.execute(action, stop=stop, deadline=12)
    assert calls == [action] and stop.waits == [] and releases == [True]
