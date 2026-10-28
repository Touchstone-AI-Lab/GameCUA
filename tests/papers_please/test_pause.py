"Exercise the Papers, Please pause cleanup using a real Linux child process."

import subprocess
import sys

import pytest

from gamecua.games.papers_please.integration import Backend

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux process pause")


def test_close_releases_a_paused_process():
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", "import time; print('ready', flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE,
        start_new_session=True,
        text=True,
    )
    backend = Backend.__new__(Backend)
    backend.process = process
    backend.identity = backend.process_identity()
    try:
        assert process.stdout.readline().strip() == "ready"
        backend.freeze()
        assert backend.pause_handle.stopped()
        backend.thaw()
        assert not backend.pause_handle.stopped()
        backend.freeze()
        backend.close_process()
        assert backend.pause_handle is None
        assert process.poll() is not None
    finally:
        backend.release_pause()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        process.stdout.close()
