"""Synthetic native bridge replies and pidfd signals exercise pauses and native steps."""

import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

from gamecua import pause as shared_pause
from gamecua.games.art_of_rally import pause as rally_pause
from gamecua.games.art_of_rally.pause import NativeStep, Pause, StepAdapter
from gamecua.storage import write_json


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    state = SimpleNamespace(status=4, error="", requests=[], signals=[], stopped=False, step=None)
    tasks = tmp_path / "tasks"
    (tasks / "42").mkdir(parents=True)

    def stat():
        (tasks / "42/stat").write_text(f"42 (synthetic) {'T' if state.stopped else 'S'} 0 0")

    stat()

    def send(fd, sig):
        state.signals.append(sig)
        state.stopped = sig == signal.SIGSTOP
        stat()

    original_close = shared_pause.os.close

    def write(path, value):
        write_json(path, value)
        state.requests.append(value)
        assert not state.stopped
        status = state.status if value["paused"] else (3 if state.status == 4 else 0)
        driving = status in (3, 4)
        write_json(
            path.with_name("ack.json"),
            {
                "binding": value["binding"],
                "id": value["id"],
                "paused": value["paused"] and driving,
                "native_status": status,
                "disposition": "driving" if driving else "transition_unfrozen",
                "error": state.error,
            },
        )
        if value.get("step_seconds") and state.step:
            write_json(path.with_name("step.json"), {"id": value["id"], **state.step})

    monkeypatch.setattr(
        shared_pause, "Path", lambda p: tasks if str(p) == "/proc/42/task" else Path(p)
    )
    monkeypatch.setattr(shared_pause.os, "pidfd_open", lambda pid: 424242)
    monkeypatch.setattr(
        shared_pause.os, "close", lambda fd: None if fd == 424242 else original_close(fd)
    )
    monkeypatch.setattr(shared_pause.signal, "pidfd_send_signal", send)
    monkeypatch.setattr(rally_pause, "write_json", write)
    state.pause = Pause(tmp_path, "synthetic", {"pid": 42}, lambda: None)
    return state


def test_driving_uses_native_pause_without_process_signals(bridge):
    ack = bridge.pause.freeze()
    assert ack["disposition"] == "driving" and bridge.pause.owned
    bridge.pause.thaw()
    assert not bridge.pause.owned
    assert [r["paused"] for r in bridge.requests] == [True, False]
    assert bridge.signals == []


@pytest.mark.parametrize("status", [0, 1, 2, 5, 6, 7, 8])
def test_transitions_stop_the_process_and_extend_the_next_wait(bridge, status):
    bridge.status = status
    ack = bridge.pause.freeze()
    assert ack["disposition"] == "transition_process_frozen"
    assert bridge.stopped and bridge.pause.transition and not bridge.pause.owned
    bridge.pause.thaw()
    assert not bridge.stopped
    assert bridge.signals == [signal.SIGSTOP, signal.SIGCONT]
    assert [r["paused"] for r in bridge.requests] == [True]


def test_native_error_releases_the_pause(bridge):
    bridge.error = "native failure"
    with pytest.raises(RuntimeError, match="native failure"):
        bridge.pause.freeze()
    assert not bridge.pause.owned
    assert [r["paused"] for r in bridge.requests] == [True, False]


class Stop:
    def is_set(self):
        return False

    def wait(self, seconds):
        return False


class Desktop:
    def __init__(self):
        self.actions, self.released = [], 0

    def execute(self, action, *, stop=None, deadline=None):
        stop.wait(0.5)
        self.actions.append(action)

    def release_all(self):
        self.released += 1


@pytest.mark.parametrize("state", ["completed", "running"])
def test_step_adapter_runs_one_native_step_and_aborts_unfinished_steps(bridge, state):
    bridge.pause.freeze()
    bridge.step = {"state": state, "elapsed_seconds": 1.0, "error": None}
    step = NativeStep(bridge.pause, 1.0)
    backend = SimpleNamespace(desktop=Desktop(), native_step=step, executing_native_step=None)
    adapter = StepAdapter(backend)
    action = {"type": "wait", "seconds": 0.5}
    if state == "completed":
        adapter.execute(action, stop=Stop(), deadline=float("inf"))
        assert bridge.pause.owned
        assert [r.get("step_seconds") for r in bridge.requests] == [None, 1.0]
    else:
        bridge.step["elapsed_seconds"] = 0.2
        with pytest.raises(InterruptedError):
            adapter.execute(action, stop=Stop(), deadline=0)
    assert backend.desktop.released == 1
    assert backend.native_step is None and backend.executing_native_step is step
