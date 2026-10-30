"""Real child processes exercise pause identity and cleanup, not native-game readiness."""

import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from gamecua.games.dont_starve.integration import Backend
from gamecua.games.dont_starve.setup import process_identity

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(os, "pidfd_open"),
    reason="Process pause requires Linux pidfds",
)
HEARTBEAT = (
    "import sys,time\n"
    "with open(sys.argv[1], 'ab', buffering=0) as stream:\n"
    " while True:\n"
    "  stream.write(b'.')\n"
    "  time.sleep(0.01)\n"
)


@pytest.fixture
def native_child(tmp_path):
    path = tmp_path / "heartbeat"
    process = subprocess.Popen([sys.executable, "-c", HEARTBEAT, str(path)])
    backend = object.__new__(Backend)
    backend.process = process
    backend.identity = process_identity(process.pid)
    backend.offset = 0
    backend.lease = None
    backend.adapter = SimpleNamespace(close=lambda: None)
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
    end = time.monotonic() + 2
    while path.read_bytes() == before and time.monotonic() < end:
        time.sleep(0.01)
    assert path.read_bytes() != before


def test_freeze_stops_and_thaw_resumes_the_identified_process(native_child):
    backend, _, path = native_child
    backend.freeze()
    before = path.read_bytes()
    time.sleep(0.08)
    assert path.read_bytes() == before
    assert backend.checkpoint() == backend.identity
    backend.freeze()
    backend.thaw()
    wait_for_progress(path, before)
    backend.freeze()
    before = path.read_bytes()
    time.sleep(0.08)
    assert path.read_bytes() == before


def test_changed_identity_is_rejected_before_signalling(native_child):
    backend, _, path = native_child
    backend.identity = {**backend.identity, "start_ticks": "invalid"}
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="Don't Starve pause process identity changed"):
        backend.freeze()
    wait_for_progress(path, before)


def test_interruption_releases_pause_without_terminating_the_original_process(native_child):
    backend, process, path = native_child
    backend.freeze()
    before = path.read_bytes()
    original = dict(backend.identity)
    backend.close(preserve=True)
    assert process.poll() is None
    assert backend.identity == original
    assert backend.pause_handle is None
    wait_for_progress(path, before)


def test_normal_close_resumes_then_terminates_a_frozen_process(native_child):
    backend, process, _ = native_child
    backend.freeze()
    backend.close()
    assert process.poll() is not None
    assert backend.process is backend.identity is backend.pause_handle is None
