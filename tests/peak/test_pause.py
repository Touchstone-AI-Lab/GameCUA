"""Real child processes verify PEAK pause identity and interruption cleanup."""

import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from gamecua.games.peak.integration import Backend
from gamecua.games.peak.pause import NativePause

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(os, "pidfd_open"), reason="Linux pidfds required"
)
HEARTBEAT = "import sys,time\nwith open(sys.argv[1], 'ab', buffering=0) as f:\n while True:\n  f.write(b'.')\n  time.sleep(0.01)\n"


@pytest.fixture
def native_child(tmp_path):
    """Run a heartbeat child process behind a PEAK backend."""
    path = tmp_path / "heartbeat"
    process = subprocess.Popen([sys.executable, "-c", HEARTBEAT, str(path)])
    backend = object.__new__(Backend)
    backend.root = tmp_path
    backend.process = process
    backend.process_id = {"pid": process.pid}
    backend.process_id = backend.process_identity()
    backend.proton = backend.profile = None
    backend.adapter = SimpleNamespace(close=lambda: None, window=None)
    try:
        end = time.monotonic() + 3
        while (not path.exists() or not path.stat().st_size) and time.monotonic() < end:
            time.sleep(0.01)
        assert path.exists() and path.stat().st_size
        yield backend, process, path
    finally:
        backend.release_pause()
        if process.poll() is None:
            os.kill(process.pid, signal.SIGCONT)
            process.terminate()
        process.wait(timeout=3)


def wait_for_progress(path, before):
    """Wait until the heartbeat file grows again."""
    end = time.monotonic() + 2
    while path.read_bytes() == before and time.monotonic() < end:
        time.sleep(0.01)
    assert path.read_bytes() != before


def test_freeze_stops_native_updates_and_thaw_resumes(native_child):
    backend, _, path = native_child
    backend.checkpoint = lambda: {"changing_game_state": time.time()}
    backend.freeze()
    before = path.read_bytes()
    time.sleep(0.08)
    assert path.read_bytes() == before
    backend.freeze()
    backend.thaw()
    wait_for_progress(path, before)


def test_changed_pid_identity_is_rejected_before_signalling(native_child):
    backend, _, path = native_child
    backend.process_id = {**backend.process_id, "start_ticks": "wrong"}
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="identity changed"):
        backend.freeze()
    wait_for_progress(path, before)


def test_preserving_close_releases_pause_and_keeps_game_running(native_child):
    backend, process, path = native_child
    backend.freeze()
    before = path.read_bytes()
    backend.close(preserve=True)
    assert process.poll() is None and backend.pause_handle is None
    wait_for_progress(path, before)


def test_normal_close_resumes_and_stops_frozen_game(native_child):
    backend, process, _ = native_child
    backend.freeze()
    backend.close()
    assert process.poll() is not None
    assert backend.process_id is backend.pause_handle is None


def test_delayed_confirmation_does_not_claim_a_pause_early(native_child, monkeypatch):
    backend, _, path = native_child
    handle = NativePause(backend.process_id, backend.process_identity)
    backend.pause_handle = handle
    stopped = handle.stopped
    started = time.monotonic()

    def delayed_confirmation():
        if time.monotonic() - started < 1.1:
            return False
        return stopped()

    monkeypatch.setattr(handle, "stopped", delayed_confirmation)
    backend.freeze()
    assert time.monotonic() - started >= 1.1
    assert stopped()
    before = path.read_bytes()
    time.sleep(0.05)
    assert path.read_bytes() == before
    backend.thaw()
    wait_for_progress(path, before)


def test_unconfirmed_pause_times_out_and_releases_native_process(native_child, monkeypatch):
    backend, _, path = native_child
    handle = NativePause(backend.process_id, backend.process_identity)
    backend.pause_handle = handle
    monkeypatch.setattr("gamecua.games.peak.pause.STOP_CONFIRMATION_SECONDS", 0.05)
    monkeypatch.setattr(handle, "stopped", lambda: False)
    with pytest.raises(RuntimeError, match="did not confirm all threads stopped"):
        backend.freeze()
    assert handle.fd is None
    wait_for_progress(path, path.read_bytes())


def test_externally_resumed_native_process_is_not_accepted(native_child):
    backend, process, path = native_child
    backend.freeze()
    os.kill(process.pid, signal.SIGCONT)
    wait_for_progress(path, path.read_bytes())
    with pytest.raises(RuntimeError, match="externally resumed"):
        backend.freeze()


def test_exiting_thread_does_not_produce_a_false_confirmation(native_child, monkeypatch):
    from gamecua.pause import ProcessPause

    backend, _, _ = native_child
    stopped = ProcessPause.stopped
    calls = 0

    def disappearing_task(handle):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise FileNotFoundError("A native worker exited during the thread snapshot")
        return stopped(handle)

    monkeypatch.setattr(ProcessPause, "stopped", disappearing_task)
    backend.freeze()
    assert calls >= 2 and stopped(backend.pause_handle)
