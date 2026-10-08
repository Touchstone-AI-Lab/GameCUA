"""Synthetic process checks for transport pause ownership; never benchmark achievements."""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from gamecua.games.factorio.transport_pause import TransportPause
from gamecua.pause import ProcessPause

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(os, "pidfd_open"), reason="Linux pidfds required"
)


def identity(process):
    """Read the synthetic process identity."""
    fields = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()
    if fields[0] == "Z":
        raise RuntimeError("Synthetic process exited")
    return {"pid": process.pid, "start_ticks": fields[19]}


@pytest.fixture
def process_backend():
    """Run a synthetic process that writes a counter until it is stopped."""
    with tempfile.TemporaryDirectory(prefix="f413-") as directory:
        path = Path(directory) / "counter"
        code = "import sys,time; from pathlib import Path\np=Path(sys.argv[1])\nwhile True:\n p.write_text(str(time.monotonic_ns()))\n time.sleep(.01)"
        process = subprocess.Popen([sys.executable, "-c", code, str(path)])
        try:
            end = time.monotonic() + 2
            while not path.exists() and time.monotonic() < end:
                time.sleep(0.01)
            assert path.exists()
            backend = SimpleNamespace(
                process_id=identity(process), process_identity=lambda: identity(process)
            )
            yield backend, process, path, Path(directory)
        finally:
            process.send_signal(signal.SIGCONT)
            process.terminate()
            process.wait(timeout=2)


def test_live_error_freezes_the_verified_process_and_recovers_same_identity(process_backend):
    backend, process, path, directory = process_backend
    controller = TransportPause(backend, directory)
    try:
        assert controller.request("freeze", "a" * 64)["state"] == "paused"
        before = path.read_text()
        time.sleep(0.06)
        assert path.read_text() == before
        assert identity(process) == backend.process_id
        assert controller.request("recover", "a" * 64)["state"] == "resumed"
        time.sleep(0.06)
        assert path.read_text() != before
    finally:
        controller.close()


def test_existing_framework_freeze_is_never_resumed_by_transport_recovery(process_backend):
    backend, process, path, directory = process_backend
    framework = ProcessPause(backend.process_id, backend.process_identity)
    framework.freeze()
    controller = TransportPause(backend, directory)
    try:
        assert controller.request("freeze", "b" * 64)["state"] == "already_frozen"
        assert controller.request("recover", "b" * 64)["state"] == "left_frozen"
        assert framework.stopped()
    finally:
        controller.close()
        assert framework.stopped()
        framework.thaw()


def test_repeated_error_is_idempotent(process_backend):
    backend, process, path, directory = process_backend
    controller = TransportPause(backend, directory)
    try:
        controller.request("freeze", "c" * 64)
        handle = controller.handle
        assert controller.request("freeze", "c" * 64)["state"] == "paused"
        assert controller.handle is handle and handle.stopped()
        controller.request("recover", "c" * 64)
    finally:
        controller.close()


def test_private_channel_rejects_a_wrong_capability_and_has_private_permissions(process_backend):
    backend, process, path, directory = process_backend
    controller = TransportPause(backend, directory)
    try:
        assert controller.registry.stat().st_mode & 0o777 == 0o600
        assert controller.socket.stat().st_mode & 0o777 == 0o600
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(controller.socket))
            client.sendall(
                json.dumps(
                    {"secret": "wrong", "operation": "freeze", "request_sha256": "f" * 64}
                ).encode()
                + b"\n"
            )
            response = json.loads(client.makefile("rb").readline())
        assert response == {"ok": False, "error_type": "PermissionError"}
        assert controller.active is None
    finally:
        controller.close()
    assert not controller.registry.exists() and not controller.socket.exists()


def test_backend_shutdown_releases_only_its_owned_transport_pause(process_backend):
    backend, process, path, directory = process_backend
    controller = TransportPause(backend, directory)
    controller.request("freeze", "1" * 64)
    before = path.read_text()
    controller.close()
    time.sleep(0.06)
    assert path.read_text() != before


def test_no_game_before_preparation_needs_no_pause(process_backend):
    backend, process, path, directory = process_backend
    backend.process_id = None
    controller = TransportPause(backend, directory)
    try:
        assert controller.request("freeze", "2" * 64) == {"state": "no_game"}
        assert controller.request("recover", "2" * 64) == {"state": "no_pause"}
        assert controller.handle is None
    finally:
        controller.close()
