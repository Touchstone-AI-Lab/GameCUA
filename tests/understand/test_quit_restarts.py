"""Offline normal-exit restart checks; native game and model providers are never launched."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from gamecua.games.understand import lifecycle
from gamecua.games.understand.integration import Backend
from gamecua.trials import Budget, Trial

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/understand"
MISSING = lifecycle.MISSING


def fixture(tmp_path, monkeypatch, code=0):
    ticks = [100.0]
    monkeypatch.setattr(lifecycle.time, "time", lambda: ticks[0])
    backend = object.__new__(Backend)
    backend.root = tmp_path / "trial"
    backend.folder = backend.root / "episodes/episode-001"
    (backend.folder / "evidence").mkdir(parents=True)
    backend.profile = tmp_path / "private-profile"
    backend.game.mkdir(parents=True)
    backend.snapshot = tmp_path / "snapshot"
    backend.installation = tmp_path / "installation"
    raw = (FIXTURES / "one-panel.sav").read_bytes()
    (backend.game / "understand.sav").write_bytes(raw)
    backend.initial = {"active_slot": 1}
    backend.seen = None
    backend.identity = {"pid": 42, "start_ticks": "old"}
    backend.process = SimpleNamespace(pid=42, poll=lambda: code)
    state = {"id": "offline-trial", "status": "running", "started_at": 100.0, "deadline": 10900.0}
    (backend.root / "trial.json").write_text(json.dumps(state))
    calls = []

    def find():
        raise RuntimeError(MISSING)

    backend.adapter = SimpleNamespace(find=find)
    backend.stop_process = lambda: calls.append("stop")
    guard = lifecycle.QuitRestarts(backend)
    guard.stop = threading.Event()
    backend.quit_restarts = guard

    def launch(attempt):
        calls.append("launch")
        ticks[0] += 12.0
        backend.identity = {"pid": 43, "start_ticks": "new"}
        backend.process = SimpleNamespace(pid=43, poll=lambda: None)
        Image.new("RGB", (2, 2), "blue").save(attempt / "reopened.png")

    guard.launch_existing = launch
    return backend, guard, ticks, calls


def test_normal_exit_preserves_progress_and_original_clock(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)
    clock_before = (backend.root / "trial.json").read_bytes()
    raw = backend.native_save()[0]
    assert guard.reopen("after_confirmed_input")
    assert calls == ["launch"] and backend.native_save()[0] == raw
    assert (backend.root / "trial.json").read_bytes() == clock_before
    attempt = backend.folder / "lifecycle/restart-0001"
    events = [json.loads(line) for line in (attempt / "events.jsonl").read_text().splitlines()]
    assert events[-1]["elapsed"] == 12 and events[-1]["agent_context"] == "unchanged"
    assert json.loads((backend.root / "runtime.local.json").read_text())["process"]["pid"] == 43


@pytest.mark.parametrize("code", [1, -9, None])
def test_crash_signal_or_still_running_process_does_not_restart(tmp_path, monkeypatch, code):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch, code)
    monkeypatch.setattr(lifecycle, "EXIT_GRACE_SECONDS", 0)
    assert guard.reopen("after_confirmed_input") is False
    assert not calls and not (backend.folder / "lifecycle").exists()


def test_visible_or_hidden_uncertain_window_is_not_restarted(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)
    backend.adapter.find = lambda: object()
    assert not guard.reopen("between_turns") and not calls


def test_other_window_error_is_not_reclassified_as_normal_exit(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)

    def fail():
        raise RuntimeError("focus failed")

    backend.adapter.find = fail
    with pytest.raises(RuntimeError, match="focus failed"):
        guard.reopen("after_confirmed_input")
    assert not calls


@pytest.mark.parametrize("stop_kind", ["stop_file", "stop_event", "deadline"])
def test_cancellation_and_original_deadline_prevent_launch(tmp_path, monkeypatch, stop_kind):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)
    if stop_kind == "stop_file":
        (backend.root / "STOP").touch()
    elif stop_kind == "stop_event":
        guard.stop.set()
    else:
        ticks[0] = 10900
    with pytest.raises(InterruptedError):
        guard.reopen("after_confirmed_input")
    assert not calls


def test_invalid_save_is_not_replaced_with_fresh_snapshot(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)
    (backend.game / "understand.sav").write_bytes(b"[partial")
    with pytest.raises(ValueError):
        guard.reopen("after_confirmed_input")
    assert not calls and (backend.game / "understand.sav").read_bytes() == b"[partial"


def test_relaunch_cannot_extend_deadline(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)
    launch = guard.launch_existing

    def late(attempt):
        launch(attempt)
        ticks[0] = 10901

    guard.launch_existing = late
    with pytest.raises(InterruptedError):
        guard.reopen("after_confirmed_input")
    assert calls == ["launch", "stop"]
    assert json.loads((backend.root / "trial.json").read_text())["deadline"] == 10900


def test_unconfirmed_delivery_does_not_trigger_capture_restart(monkeypatch):
    adapter = object.__new__(lifecycle.RestartDesktop)
    calls = []
    adapter.restarts = SimpleNamespace(reopen=lambda phase: calls.append(phase))
    adapter.after_action = False

    def failed(*args, **kwargs):
        raise RuntimeError(MISSING)

    adapter.raw_capture = failed
    monkeypatch.setattr(lifecycle.X11Desktop, "execute", failed)
    with pytest.raises(RuntimeError):
        adapter.execute({"type": "pointer"})
    with pytest.raises(RuntimeError):
        adapter.capture()
    assert not calls and not adapter.after_action


def test_capture_restarts_only_after_confirmed_input_and_returns_real_new_frame(monkeypatch):
    adapter = object.__new__(lifecycle.RestartDesktop)
    calls = []
    image = Image.new("RGB", (2, 2), "blue")
    adapter.restarts = SimpleNamespace(reopen=lambda phase: calls.append(phase) or True)
    adapter.after_action = False
    monkeypatch.setattr(lifecycle.X11Desktop, "execute", lambda *a, **k: calls.append("execute"))
    captures = [None, image]

    def raw(focus=True):
        value = captures.pop(0)
        if value is None:
            raise RuntimeError(MISSING)
        return value

    adapter.raw_capture = raw
    adapter.execute({"type": "pointer"})
    assert adapter.capture() is image
    assert calls == ["execute", "after_confirmed_input"] and not adapter.after_action


def test_full_unchanged_trial_loop_keeps_agent_memory_and_charges_restart(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch, code=None)
    closed = [False]
    adapter = object.__new__(lifecycle.RestartDesktop)
    adapter.restarts = guard
    adapter.after_action = False
    backend.adapter = adapter
    adapter.release_all = lambda: None
    original_frame = Image.new("RGB", (2, 2), "white")
    reopened_frame = Image.new("RGB", (2, 2), "blue")

    def find():
        if closed[0]:
            raise RuntimeError(MISSING)
        return SimpleNamespace(query_pointer=lambda: SimpleNamespace(win_x=0, win_y=0))

    def capture(focus=True):
        find()
        return reopened_frame if backend.identity["pid"] == 43 else original_frame

    def execute(*args, **kwargs):
        calls.append("input_once")
        closed[0] = True
        backend.process = SimpleNamespace(pid=42, poll=lambda: 0)

    adapter.find = find
    adapter.raw_capture = capture
    monkeypatch.setattr(lifecycle.X11Desktop, "execute", execute)
    launch = guard.launch_existing

    def relaunch(attempt):
        launch(attempt)
        closed[0] = False

    guard.launch_existing = relaunch
    backend.process_identity = lambda: backend.identity
    backend.window_identity = lambda: {
        "window_id": backend.identity["pid"],
        "width": 1280,
        "height": 720,
    }
    obj = object.__new__(Trial)
    obj.root = backend.root
    obj.backend = backend
    obj.stop = guard.stop
    obj.profile = None
    obj.spec = SimpleNamespace(
        action_execution="live", recording_fps=2, episode_context="trial_memory"
    )
    obj.game = SimpleNamespace(timing="turn_based")
    episode = {"id": "episode-001", "status": "running", "segments": []}
    obj.state = {
        "id": "offline-trial",
        "episodes": [episode],
        "started_at": 100.0,
        "deadline": 10900.0,
        "elapsed_seconds": 0,
        "chargeable_seconds": 0,
        "last_seen": 100.0,
        "effective_seconds": 0,
    }
    obj.budget = Budget(obj.state, 10800, clock=lambda: ticks[0], monotonic=lambda: ticks[0])
    obj.persist = lambda: (
        obj.budget.touch(),
        (obj.root / "trial.json").write_text(json.dumps({**obj.state, "status": "running"})),
    )
    obj.event = lambda *a, **k: None
    obj.recorder = lambda *a: SimpleNamespace(close=lambda: None)
    observations = []

    def decide(image, memory, history, stop, deadline):
        observations.append((image, memory, history[:]))
        if len(observations) == 2:
            stop.set()
        return {
            "action": {"type": "pointer", "x": 0.951, "y": 0.064, "button": "left"},
            "memory": "own prior note",
        }, {}

    agent = SimpleNamespace(decide=decide, close=lambda: None)
    factories = []
    obj.make_agent = lambda *a: factories.append("one conversation") or agent
    obj.persist()
    obj.play(episode)
    assert calls.count("input_once") == 1 and calls.count("launch") == 1
    assert len(factories) == 1 and observations[1][1] == "own prior note"
    assert observations[1][0] is reopened_frame and len(obj.state["episodes"]) == 1
    assert obj.state["deadline"] == 10900 and obj.state["chargeable_seconds"] == 12
    record = json.loads((backend.folder / "segments/segment-001/00001.json").read_text())
    assert record["execution_status"] == "completed"


def test_persisted_elapsed_time_is_not_refunded_if_wall_clock_moves_back(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)
    state = json.loads((backend.root / "trial.json").read_text())
    state["elapsed_seconds"] = 33
    (backend.root / "trial.json").write_text(json.dumps(state))
    ticks[0] = 90
    assert guard.guard() == (33, 10800 - 33)


def test_reopen_checks_new_owned_process_after_old_pid_has_exited(tmp_path, monkeypatch):
    backend, guard, ticks, calls = fixture(tmp_path, monkeypatch)
    old = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    old.wait(timeout=10)
    backend.identity = {"pid": old.pid, "start_ticks": "previous"}
    backend.adapter.raw_capture = lambda: Image.new("RGB", (2, 2), "blue")
    backend.window_identity = lambda: {"window_id": 1, "width": 1280, "height": 720}
    monkeypatch.setattr(
        lifecycle,
        "command",
        lambda game: [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    monkeypatch.setattr(lifecycle, "environment", lambda game, prefix: dict(os.environ))
    attempt = tmp_path / "reopen"
    attempt.mkdir()
    try:
        lifecycle.QuitRestarts.launch_existing(guard, attempt)
        assert backend.identity["pid"] == backend.process.pid != old.pid
        assert backend.identity["start_ticks"].isdigit()
        assert backend.process_identity() == backend.identity
        assert (attempt / "reopened.png").exists()
    finally:
        if backend.process and backend.process.poll() is None:
            backend.process.terminate()
            backend.process.wait(timeout=10)
