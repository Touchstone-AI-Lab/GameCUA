"""Presentation-boundary failures never become a successful frozen observation."""

import threading
from types import SimpleNamespace

import pytest

from gamecua.games.oxygen_not_included import render


class Connection:
    def __init__(self, events):
        self.events = iter(events)
        self.pending = []
        self.closed = False
        self.armed = False

    def has_extension(self, name):
        return True

    def damage_query_version(self):
        pass

    def create_resource_object(self, kind, identifier):
        return SimpleNamespace(
            get_geometry=lambda: SimpleNamespace(width=1280, height=720),
            damage_create=lambda level: 7,
        )

    def sync(self):
        pass

    def pending_events(self):
        if self.armed and not self.pending:
            self.pending = [next(self.events)]
        return len(self.pending)

    def next_event(self):
        return self.pending.pop()

    def damage_subtract(self, identifier):
        self.armed = True

    def close(self):
        self.closed = True


def event(timestamp, width=1280, identifier=7):
    return SimpleNamespace(
        damage=identifier,
        timestamp=timestamp,
        area=SimpleNamespace(x=0, y=0, width=width, height=720),
    )


def test_only_distinct_full_updates_for_the_game_are_counted(monkeypatch):
    connection = Connection(
        [event(1), event(1), event(2, width=1), event(2, identifier=8)]
        + [event(i) for i in range(2, 7)]
    )
    monkeypatch.setattr(render.display, "Display", lambda: connection)
    result = render.settle(123, threading.Event(), float("inf"))
    assert result["full_updates"] == 6
    assert result["method"] == "x11_damage_full_window_updates"
    assert connection.closed


@pytest.mark.parametrize("cancel,deadline", [(True, 100), (False, 0)])
def test_cancel_or_deadline_closes_without_waiting_for_frames(monkeypatch, cancel, deadline):
    connection = Connection([])
    monkeypatch.setattr(render.display, "Display", lambda: connection)
    monkeypatch.setattr(render.time, "monotonic", lambda: 0)
    stop = threading.Event()
    if cancel:
        stop.set()
    with pytest.raises(InterruptedError):
        render.settle(123, stop, deadline)
    assert connection.closed


def test_update_flood_cannot_evade_timeout(monkeypatch):
    connection = Connection(event(1) for _ in range(100))
    clock = iter(range(100))
    monkeypatch.setattr(render.display, "Display", lambda: connection)
    monkeypatch.setattr(render.time, "monotonic", lambda: next(clock))
    with pytest.raises(RuntimeError, match="enough full-window"):
        render.settle(123, threading.Event(), 1000)
    assert connection.closed


def test_missing_extension_fails_closed(monkeypatch):
    connection = Connection([])
    connection.has_extension = lambda name: False
    monkeypatch.setattr(render.display, "Display", lambda: connection)
    with pytest.raises(RuntimeError, match="DAMAGE"):
        render.settle(123, threading.Event(), float("inf"))
    assert connection.closed
