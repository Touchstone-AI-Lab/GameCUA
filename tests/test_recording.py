"""Recorder metadata survives capture failures and an encoder that does not exit."""

import io
import json
import subprocess
import threading
from types import SimpleNamespace

from gamecua import recording


class FailingDesktop:
    closed = False

    def __init__(self, *args, **kwargs):
        pass

    def capture(self, focus=False):
        raise RuntimeError("window vanished")

    def close(self):
        FailingDesktop.closed = True


class StubbornEncoder:
    def __init__(self, *args, **kwargs):
        self.stdin = io.BytesIO()
        self.signals = []

    def poll(self):
        return None if "kill" not in self.signals else -9

    def terminate(self):
        self.signals.append("terminate")

    def kill(self):
        self.signals.append("kill")

    def wait(self, timeout=None):
        if "kill" not in self.signals:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        return -9


def test_capture_failure_with_stuck_encoder_still_writes_metadata(tmp_path, monkeypatch):
    encoders = []
    monkeypatch.setattr(recording, "X11Desktop", FailingDesktop)
    monkeypatch.setattr(recording.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        recording.subprocess,
        "Popen",
        lambda *a, **k: encoders.append(StubbornEncoder()) or encoders[-1],
    )
    game = SimpleNamespace(
        resolution=(4, 4), window_title="Game", input_backend="xtest", window_title_prefix=False
    )
    recorder = recording.Recording(tmp_path, game, 2, lambda: 1.5, threading.Event())
    recorder.thread.join(timeout=5)
    recorder.close()
    result = json.loads((tmp_path / "recording.json").read_text())
    assert result["error_type"] == "RuntimeError"
    assert [gap["reason"] for gap in result["gaps"]] == ["recording_failed", "encoder_killed"]
    assert encoders[0].stdin.closed
    assert encoders[0].signals == ["kill"]
    assert FailingDesktop.closed
