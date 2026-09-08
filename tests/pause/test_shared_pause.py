"""Shared process pause is proven on a real child process, never on game timing."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from gamecua.catalog import Catalog, digest
from gamecua.pause import PausableProcess, ProcessPause
from gamecua.specs import GameSpec

ROOT = Path(__file__).parents[2]
BEAT = (
    "import pathlib,time,sys; p=pathlib.Path(sys.argv[1]); n=0\n"
    "while True:\n n+=1; p.write_text(str(n)); time.sleep(.01)"
)


def identity(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    if fields[0] == "Z":
        raise RuntimeError("Child exited")
    return {"pid": pid, "start_ticks": fields[19]}


@pytest.fixture
def child(tmp_path):
    path = tmp_path / "heartbeat"
    process = subprocess.Popen([sys.executable, "-c", BEAT, str(path)])
    end = time.monotonic() + 3
    while not path.exists() and time.monotonic() < end:
        time.sleep(0.01)
    assert path.exists()
    try:
        yield process, path
    finally:
        if process.poll() is None:
            os.kill(process.pid, signal.SIGCONT)
            process.terminate()
        process.wait(timeout=3)


class Backend(PausableProcess):
    pause_name = "Fixture"

    def __init__(self, process):
        self.process = process
        self.identity = identity(process.pid)

    def checkpoint(self):
        return identity(self.process.pid)


def test_mixin_freezes_and_thaws_a_real_process(child):
    process, path = child
    backend = Backend(process)
    backend.freeze()
    before = path.read_bytes()
    time.sleep(0.08)
    assert path.read_bytes() == before
    backend.thaw()
    end = time.monotonic() + 1
    while path.read_bytes() == before and time.monotonic() < end:
        time.sleep(0.01)
    assert path.read_bytes() != before


def test_release_resumes_a_frozen_process_and_is_idempotent(child):
    process, path = child
    backend = Backend(process)
    backend.freeze()
    assert backend.pause_handle.stopped()
    backend.release_pause()
    backend.release_pause()
    assert backend.pause_handle is None
    before = path.read_bytes()
    time.sleep(0.1)
    assert path.read_bytes() != before


def test_thaw_without_freeze_is_a_no_op(child):
    process, _ = child
    Backend(process).thaw()


def test_identity_mismatch_names_the_game(child):
    process, _ = child
    wrong = dict(identity(process.pid), start_ticks="invalid")
    pause = ProcessPause(wrong, lambda: identity(process.pid), name="Fixture")
    with pytest.raises(RuntimeError, match="Fixture pause process identity changed"):
        pause.freeze()
    assert not pause.stopped()


def test_external_resume_is_detected(child):
    process, _ = child
    pause = ProcessPause(identity(process.pid), lambda: identity(process.pid))
    pause.freeze()
    os.kill(process.pid, signal.SIGCONT)
    time.sleep(0.05)
    with pytest.raises(RuntimeError, match="externally resumed"):
        pause.freeze()
    pause.release()


def test_pause_declaration_keeps_undeclared_hashes():
    base = {"id": "fixture", "title": "Fixture", "window_title": "Fixture"}
    turn_based = GameSpec.model_validate(
        {**base, "timing": "turn_based", "pause": {"method": "process"}}
    )
    assert turn_based.pause.method == "process"
    plain = GameSpec.model_validate({**base, "timing": "realtime"})
    assert "pause" not in plain.model_dump(mode="json")
    declared = GameSpec.model_validate(
        {**base, "timing": "realtime", "pause": {"method": "native"}}
    )
    assert digest(plain) != digest(declared)


def test_frozen_trials_need_a_declared_pause_method(tmp_path):
    catalog = Catalog(ROOT / "benchmarks")
    frozen = [t for t in catalog.trials.values() if t.action_execution == "frozen_steps"]
    assert frozen
    assert all(catalog.games[t.game_id].pause is not None for t in frozen)


def test_celeste_pilot_has_live_and_frozen_three_hour_specs():
    catalog = Catalog(ROOT / "benchmarks")
    live = catalog.trials["hollow-knight-silksong-points-v1-kimi-k3-1-pro-live-3h"]
    frozen = catalog.trials["hollow-knight-silksong-points-v1-kimi-k3-1-pro-frozen-3h"]
    assert (live.total_seconds, frozen.total_seconds) == (10800.0, 10800.0)
    assert (live.action_execution, frozen.action_execution) == ("live", "frozen_steps")
    assert live.rubric_id == frozen.rubric_id == "hollow-knight-silksong-points-v1"
    assert catalog.games["hollow-knight-silksong"].pause.method == "process"
