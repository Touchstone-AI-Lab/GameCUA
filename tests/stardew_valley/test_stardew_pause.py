"""Stardew Valley process pause is proven on a real child process, never on game timing."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.games.stardew_valley.integration import Backend

ROOT = Path(__file__).resolve().parents[2]
BEAT = (
    "import pathlib,time,sys; p=pathlib.Path(sys.argv[1]); n=0\n"
    "while True:\n n+=1; p.write_text(str(n)); time.sleep(.01)"
)


@pytest.fixture
def backend(tmp_path):
    path = tmp_path / "heartbeat"
    process = subprocess.Popen([sys.executable, "-c", BEAT, str(path)], start_new_session=True)
    end = time.monotonic() + 3
    while not path.exists() and time.monotonic() < end:
        time.sleep(0.01)
    assert path.exists()
    game = Backend.__new__(Backend)
    game.process = process
    game.identity = game.process_identity()
    try:
        yield game, path
    finally:
        if process.poll() is None:
            os.kill(process.pid, signal.SIGCONT)
            process.terminate()
        process.wait(timeout=3)


def advances(path, before):
    end = time.monotonic() + 1
    while path.read_bytes() == before and time.monotonic() < end:
        time.sleep(0.01)
    return path.read_bytes() != before


def test_freeze_stops_the_game_process_and_thaw_resumes_it(backend):
    game, path = backend
    game.freeze()
    before = path.read_bytes()
    time.sleep(0.08)
    game.freeze()
    assert path.read_bytes() == before
    assert game.pause_handle.stopped()
    game.thaw()
    assert advances(path, before)


def test_stopping_a_frozen_game_releases_it_first(backend):
    game, path = backend
    game.freeze()
    game.stop_process()
    assert game.pause_handle is None
    assert game.process.wait(timeout=5) == -signal.SIGTERM


def test_freeze_refuses_a_recycled_process_identity(backend):
    game, _ = backend
    game.identity = {**game.identity, "start_ticks": "0"}
    with pytest.raises(RuntimeError, match="identity changed"):
        game.freeze()
    assert game.pause_handle.fd is None


def test_game_declares_the_process_pause_for_frozen_trials():
    catalog = Catalog(ROOT / "benchmarks")
    assert catalog.games["stardew-valley"].pause.method == "process"
    frozen = [
        t
        for t in catalog.trials.values()
        if t.game_id == "stardew-valley" and t.action_execution == "frozen_steps"
    ]
    assert {t.model_id for t in frozen} == {
        "deepseek-v41-flash-thinking",
        "grok-4.7",
        "gpt-6-astra",
        "jev-1-14",
        "kimi-k3-1-pro",
        "stardew-valley-claude-opus-5-5-high",
    }
