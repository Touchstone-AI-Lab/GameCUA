"""Private native records are consumed incrementally and never read from the UI."""

import json
import signal
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from gamecua.games.left_4_dead_2.integration import Backend, Desktop, running, signal_group


def backend(tmp_path):
    value = Backend.__new__(Backend)
    value.nonce = "episode"
    value.native_evidence = tmp_path
    value.last_native = (0, -1)
    return value


def record(tmp_path, generation, sequence):
    path = tmp_path / f"gs-episode-{generation}-{sequence}.json"
    row = {"session": "episode", "generation": generation, "sequence": sequence}
    path.write_bytes(json.dumps(row).encode() + b"\n\0")
    return row


def test_partial_write_is_retried_and_complete_records_are_not_replayed(tmp_path):
    value = backend(tmp_path)
    (tmp_path / "gs-episode-generation.txt").write_bytes(b"1\0")
    path = tmp_path / "gs-episode-1-0.json"
    path.write_bytes(b'{"session":')
    assert value.read_rows() == []
    row = record(tmp_path, 1, 0)
    assert value.read_rows() == [row]
    assert value.read_rows() == []
    next_row = record(tmp_path, 1, 1)
    assert value.read_rows() == [next_row]


def test_map_reload_keeps_generation_identity(tmp_path):
    value = backend(tmp_path)
    (tmp_path / "gs-episode-generation.txt").write_text("2")
    first = record(tmp_path, 1, 0)
    second = record(tmp_path, 2, 0)
    assert value.read_rows() == [first, second]


def test_startup_requires_the_visible_console_panel():
    console = Image.new("RGB", (640, 360), (118, 118, 118))
    assert Backend.console_ready(console)
    console.putpixel((350, 25), (30, 20, 10))
    assert not Backend.console_ready(console)


def test_key_tap_covers_native_frames_and_preserves_cancellation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "gamecua.desktop.X11Desktop.execute",
        lambda self, action, **kwargs: calls.append((action, kwargs)),
    )
    value = Desktop.__new__(Desktop)
    original = {"type": "press", "key": "E"}
    value.execute(original, stop="cancel", deadline=123)
    assert original == {"type": "press", "key": "E"}
    assert calls == [
        (
            {
                "type": "control",
                "keys": ["e"],
                "buttons": [],
                "dx": 0.0,
                "dy": 0.0,
                "duration": 0.2,
            },
            {"stop": "cancel", "deadline": 123},
        )
    ]
    with pytest.raises(ValueError):
        value.execute({"type": "press", "key": "e", "unexpected": True})


def test_group_signal_needs_the_recorded_leader():
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        stat = Path(f"/proc/{child.pid}/stat").read_text()
        identity = {"pid": child.pid, "start_ticks": stat.rsplit(")", 1)[1].split()[19]}
        signal_group({**identity, "start_ticks": "0"}, signal.SIGTERM)
        assert child.poll() is None and running(identity)
        signal_group(identity, signal.SIGTERM)
        assert child.wait(timeout=5) == -signal.SIGTERM and not running(identity)
    finally:
        child.kill()
        child.wait()
