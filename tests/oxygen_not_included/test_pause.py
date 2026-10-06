"""Verify ONI process-pause lifecycle against a real Linux child, not game timing."""

import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from gamecua.games.oxygen_not_included.integration import Backend
from gamecua.provider import InvalidResponse, RetryPolicy
from gamecua.provider_recovery import ProviderRecovery
from gamecua.specs import ProviderLedger

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux process pause")


def test_pause_thaw_and_stop_release_real_process():
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", "import time; print('ready', flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    backend = Backend.__new__(Backend)
    backend.process = process
    backend.identity = {"pid": process.pid}
    backend.identity = backend.process_identity()
    backend.assert_runtime = lambda: None
    backend.adapter = SimpleNamespace(close=lambda: None)
    try:
        assert process.stdout.readline().strip() == "ready"
        backend.freeze()
        assert backend.pause_handle.stopped()
        backend.thaw()
        assert not backend.pause_handle.stopped()
        backend.freeze()
        backend.close()
        assert backend.pause_handle is None
        assert process.poll() is not None
    finally:
        backend.release_pause()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        process.stdout.close()


def test_provider_failure_freezes_real_native_process_until_success():
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", "import time; print('ready', flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    backend = Backend.__new__(Backend)
    backend.process = process
    backend.identity = {"pid": process.pid}
    backend.identity = backend.process_identity()
    backend.assert_runtime = lambda: None
    backend.adapter = SimpleNamespace(close=lambda: None, release_all=lambda: None)
    backend.poll = lambda elapsed: None
    budget = SimpleNamespace(remaining=lambda: 10800, elapsed=lambda: 0)
    trial = SimpleNamespace(
        backend=backend,
        budget=budget,
        lock=threading.RLock(),
        spec=SimpleNamespace(action_execution="live"),
        state={"episodes": [], "provider_recovery": ProviderLedger().model_dump(mode="json")},
        event=lambda *a, **k: None,
        persist=lambda: None,
    )
    attempts = []

    def attempt(timeout):
        attempts.append(timeout)
        if len(attempts) == 1:
            raise InvalidResponse("synthetic failure")
        assert backend.pause_handle.stopped()
        return "ok", {}, None

    def wait(seconds):
        assert seconds == 1 and backend.pause_handle.stopped()
        return False

    try:
        assert process.stdout.readline().strip() == "ready"
        recovery = ProviderRecovery(trial)
        result, stats = recovery.request(
            RetryPolicy(),
            lambda e: None,
            SimpleNamespace(is_set=lambda: False, wait=wait),
            attempt,
            "decision",
        )
        assert result == "ok" and stats["attempts"] == 2
        assert not backend.pause_handle.stopped()
    finally:
        backend.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        process.stdout.close()
