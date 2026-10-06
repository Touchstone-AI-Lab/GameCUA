"""Native startup recognition, one-shot input and failure isolation."""

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from gamecua.games.oxygen_not_included.integration import Backend
from gamecua.games.oxygen_not_included.startup import BOX, simulation_state

FIXTURES = Path(__file__).parent / "fixtures/startup"


def frame(state):
    image = Image.new("RGB", (1280, 720))
    if state:
        with Image.open(FIXTURES / f"{state}.png") as crop:
            image.paste(crop, BOX)
    return image


@pytest.mark.parametrize("state", ["paused", "running", None])
def test_native_pause_cues(state):
    assert simulation_state(frame(state)) == state


def backend(tmp_path, states, frozen=False):
    value = Backend.__new__(Backend)
    value.folder = tmp_path
    value.startup_pending = True
    value.startup_stop = threading.Event()
    value.startup_deadline = time.monotonic() + 5
    actions = []
    images = iter(frame(s) for s in states)
    value.adapter = SimpleNamespace(
        capture=lambda: next(images),
        execute=lambda a, **kw: actions.append(a),
        release_all=lambda: actions.append("release"),
    )
    value.pause_handle = SimpleNamespace(stopped=lambda: True) if frozen else None
    value.thaw = lambda: actions.append("thaw")
    value.freeze = lambda: actions.append("freeze")
    value.wait = lambda *args: None
    value.assert_runtime = lambda: None
    return value, actions


@pytest.mark.parametrize("frozen", [False, True])
def test_unpause_once_and_restore_frozen_boundary(tmp_path, frozen):
    value, actions = backend(tmp_path, ["paused", "paused", "running"], frozen)
    value.start_simulation(0.25)
    assert [a for a in actions if isinstance(a, dict)] == [
        {"type": "control", "keys": ["space"], "duration": 0.1}
    ]
    assert ("thaw" in actions) == frozen
    assert ("freeze" in actions) == frozen
    assert not value.startup_pending
    record = json.loads((tmp_path / "simulation-start.json").read_text())
    assert record["status"] == "completed" and record["elapsed"] == 0.25


def test_running_start_never_toggled(tmp_path):
    value, actions = backend(tmp_path, ["running"])
    value.start_simulation(0)
    assert actions == ["release"]


def test_unknown_state_never_gets_input(tmp_path):
    value, actions = backend(tmp_path, [None])
    with pytest.raises(RuntimeError, match="unrecognized"):
        value.start_simulation(0)
    assert actions == []
    assert not (tmp_path / "simulation-start.json").exists()


def test_failed_input_not_retried_and_frozen_restored(tmp_path):
    value, actions = backend(tmp_path, ["paused"], True)

    def fail(*args, **kwargs):
        raise RuntimeError("uncertain input")

    value.adapter.execute = fail
    with pytest.raises(RuntimeError, match="uncertain"):
        value.start_simulation(0)
    assert actions == ["thaw", "release", "freeze"]
    assert not (tmp_path / "simulation-start.json").exists()
    assert not value.startup_pending


def test_timeout_does_not_toggle_again(tmp_path):
    value, actions = backend(tmp_path, ["paused"])

    def timeout(*args):
        raise InterruptedError("deadline")

    value.wait = timeout
    with pytest.raises(InterruptedError):
        value.start_simulation(0)
    assert len([a for a in actions if isinstance(a, dict)]) == 1


def test_later_poll_does_not_override_model_pause(tmp_path):
    value, actions = backend(tmp_path, ["running"])
    value.profile = tmp_path
    (tmp_path / "Player.local.log").write_text("Loading save file: benchmark.sav\n")
    value.save_paths = lambda: []
    value.terminal = "synthetic-terminal"
    assert value.poll(0) == "synthetic-terminal"
    assert value.poll(1) == "synthetic-terminal"
    assert actions == ["release"]


@pytest.mark.parametrize("status", [None, "pending"])
def test_recovery_rejects_unconfirmed_startup(tmp_path, status):
    value = Backend.__new__(Backend)
    value.root = tmp_path
    folder = tmp_path / "episode"
    folder.mkdir()
    (tmp_path / "runtime.local.json").write_text(
        json.dumps(
            {
                "profile": str(tmp_path),
                "snapshot": str(tmp_path),
                "installation": str(tmp_path),
                "process": {"pid": 1},
            }
        )
    )
    (folder / "setup.json").write_text(
        json.dumps({"simulation_start": "running_before_first_decision_v1"})
    )
    if status:
        (folder / "simulation-start.json").write_text(json.dumps({"status": status}))
    assert value.recover(folder, {}) is False
    assert not value.startup_pending
