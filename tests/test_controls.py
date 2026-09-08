import threading
import time
from types import SimpleNamespace

import pytest

from gamecua.actions import validate
from gamecua.desktop import X11Desktop


def backend():
    instance = object.__new__(X11Desktop)
    instance.input_backend, instance.mouse_mode = "xtest", "captured"
    instance.held_keys, instance.held_buttons = set(), set()
    instance.events = []
    instance.d = SimpleNamespace(keysym_to_keycode=lambda key: key)
    instance.root = SimpleNamespace(
        translate_coords=lambda *args: SimpleNamespace(x=0, y=0),
        get_geometry=lambda: SimpleNamespace(width=1280, height=720),
    )
    instance.focus = lambda **kwargs: SimpleNamespace(
        get_geometry=lambda: SimpleNamespace(width=1280, height=720)
    )

    def input_event(kind, detail, down):
        instance.events.append((kind, detail, down))
        held = instance.held_keys if kind == "key" else instance.held_buttons
        held.add(detail) if down else held.discard(detail)

    instance._input = input_event

    def release():
        for kind, held in (("key", instance.held_keys), ("button", instance.held_buttons)):
            for item in list(held):
                input_event(kind, item, False)

    instance.release_all = release
    return instance


def test_combined_input_is_bounded():
    action = validate(
        {
            "type": "control",
            "keys": ["w", "space", "Control_L"],
            "buttons": ["left"],
            "dx": 20,
            "duration": 0.05,
        }
    )
    assert action["dy"] == 0
    with pytest.raises(ValueError):
        validate({**action, "duration": 4})
    with pytest.raises(ValueError):
        validate({**action, "keys": ["w", "w"]})


@pytest.mark.parametrize("mode", ["cancellation", "deadline", "exception"])
def test_held_inputs_release_on_interruption(mode):
    instance = backend()
    stop = threading.Event()
    deadline = time.monotonic() + (0.06 if mode == "deadline" else 2)
    if mode == "cancellation":
        timer = threading.Timer(0.06, stop.set)
        timer.start()
    if mode == "exception":
        original = instance._input

        def failing(kind, detail, down):
            original(kind, detail, down)
            if kind == "button" and down:
                raise RuntimeError("Injected input transport error")

        instance._input = failing
    with pytest.raises((InterruptedError, RuntimeError)):
        instance.execute(
            {"type": "control", "keys": ["w", "space"], "buttons": ["left"], "duration": 0.2},
            stop=stop,
            deadline=deadline,
        )
    assert not instance.held_keys and not instance.held_buttons
    assert any(not event[2] for event in instance.events)


def test_existing_holds_release_even_before_new_action_begins():
    instance = backend()
    instance.held_buttons.add(1)
    stop = threading.Event()
    stop.set()
    with pytest.raises(InterruptedError):
        instance.execute({"type": "wait", "seconds": 0.1}, stop=stop)
    assert not instance.held_buttons


def test_dynamic_game_caption_requires_explicit_prefix_matching():
    instance = object.__new__(X11Desktop)
    instance.title, instance.title_prefix = "Luanti", False
    assert not instance.matches_title("Luanti 5.10.0 - FPS 60")
    instance.title_prefix = True
    assert instance.matches_title("Luanti 5.10.0 - FPS 60")
    assert not instance.matches_title("Other game") and not instance.matches_title(None)


def test_mouse_release_checks_server_state_and_retries(monkeypatch):
    from Xlib import X

    from gamecua import desktop

    instance = object.__new__(X11Desktop)
    instance.input_backend = "xtest"
    instance.held_keys, instance.held_buttons = set(), {1}
    instance.button_state = X.Button1Mask
    masks = iter((X.Button1Mask, 0))
    instance.root = SimpleNamespace(query_pointer=lambda: SimpleNamespace(mask=next(masks)))
    instance.d = SimpleNamespace(sync=lambda: None)
    instance._input = lambda *args: None
    events = []
    monkeypatch.setattr(desktop.xtest, "fake_input", lambda *args: events.append(args[1:]))
    monkeypatch.setattr(desktop.time, "sleep", lambda seconds: None)
    instance.release_all()
    assert events == [(X.ButtonRelease, 1)]
    assert not instance.held_buttons and instance.button_state == 0


@pytest.mark.parametrize("mode", ["captured", "cursor"])
def test_drag_handles_game_pointer_recentering_without_weakening_cursor_checks(mode):
    instance = backend()
    instance.mouse_mode = mode
    warps = []
    window = SimpleNamespace(
        get_geometry=lambda: SimpleNamespace(width=1280, height=720),
        warp_pointer=lambda x, y: warps.append((x, y)),
    )
    instance.focus = lambda **kwargs: window
    instance.d.sync = lambda: None
    instance.root.query_pointer = lambda: SimpleNamespace(root_x=640, root_y=360)
    action = {"type": "drag", "x": 0.5, "y": 0.5, "to_x": 0.8, "to_y": 0.5, "duration": 0.1}
    if mode == "captured":
        instance.execute(action, stop=threading.Event())
        assert len(warps) == 21
    else:
        with pytest.raises(RuntimeError, match="Pointer"):
            instance.execute(action, stop=threading.Event())
    assert not instance.held_buttons


def test_relative_cursor_motion_stops_at_the_window_edge():
    instance = backend()
    instance.mouse_mode = "cursor"
    warps = [(1200, 50)]
    window = SimpleNamespace(
        get_geometry=lambda: SimpleNamespace(width=1280, height=720),
        warp_pointer=lambda x, y: warps.append((x, y)),
        query_pointer=lambda: SimpleNamespace(win_x=warps[-1][0], win_y=warps[-1][1]),
    )
    instance.focus = lambda **kwargs: window
    instance.d.sync = lambda: None
    instance.root.query_pointer = lambda: SimpleNamespace(root_x=warps[-1][0], root_y=warps[-1][1])
    action = {"type": "control", "keys": [], "buttons": [], "dx": 400, "dy": -300, "duration": 0.1}
    instance.execute(action, stop=threading.Event())
    assert warps[1:] == [(1279, 0), (1279, 0)]


def test_relative_cursor_movement_stays_inside_window():
    instance = backend()
    instance.mouse_mode = "cursor"
    warps = []
    window = SimpleNamespace(
        get_geometry=lambda: SimpleNamespace(width=1280, height=720),
        query_pointer=lambda: SimpleNamespace(win_x=1270, win_y=710),
        warp_pointer=lambda x, y: warps.append((x, y)),
    )
    instance.focus = lambda **kwargs: window
    instance.d.sync = lambda: None
    instance.root.query_pointer = lambda: SimpleNamespace(root_x=warps[-1][0], root_y=warps[-1][1])
    instance.execute({"type": "relative_move", "dx": 100, "dy": 100}, stop=threading.Event())
    assert warps == [(1279, 719), (1279, 719)]


def test_absolute_cursor_movement_clamps_to_visible_root():
    instance = backend()
    instance.mouse_mode = "cursor"
    warps = []
    window = SimpleNamespace(
        get_geometry=lambda: SimpleNamespace(width=1280, height=720),
        warp_pointer=lambda x, y: warps.append((x, y)),
    )
    instance.focus = lambda **kwargs: window
    instance.d.sync = lambda: None
    instance.root.translate_coords = lambda *args: SimpleNamespace(x=0, y=21)
    instance.root.query_pointer = lambda: SimpleNamespace(
        root_x=warps[-1][0], root_y=warps[-1][1] + 21
    )
    instance.execute({"type": "move", "x": 0.5, "y": 0.99}, stop=threading.Event())
    assert warps == [(640, 698)]
