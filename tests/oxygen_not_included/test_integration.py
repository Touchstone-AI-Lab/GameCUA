"""Offline preparation, save collection and recovery of the ONI backend."""

import json
import threading
import time
from types import SimpleNamespace

import pytest
from PIL import Image

from gamecua.games.oxygen_not_included import integration
from gamecua.games.oxygen_not_included.integration import Backend
from gamecua.games.oxygen_not_included.native import read_save
from gamecua.games.oxygen_not_included.setup import config_dir

from .test_native import synthetic_save


def test_prepare_preserves_the_snapshot_save_as_the_baseline(tmp_path, monkeypatch):
    backend = Backend.__new__(Backend)
    backend.root = tmp_path / "trial"
    folder = backend.root / "episodes/episode-001"
    folder.mkdir(parents=True)
    backend.snapshot = tmp_path / "snapshot"
    backend.installation = tmp_path / "installation"
    backend.identity = None
    backend.release_pause = lambda: None
    raw = synthetic_save()

    def install(snapshot, profile):
        profile.mkdir(parents=True)
        return raw

    monkeypatch.setattr(integration, "verify_cached_session", lambda: None)
    monkeypatch.setattr(integration, "install_profile", install)
    monkeypatch.setattr(integration, "stage_launcher", lambda *args: None)
    monkeypatch.setattr(integration, "link_steam_runtime", lambda *args: None)
    monkeypatch.setattr(integration, "command", lambda *args: ["synthetic"])
    monkeypatch.setattr(integration, "environment", lambda *args: {})
    monkeypatch.setattr(
        integration.subprocess, "Popen", lambda *args, **kwargs: SimpleNamespace(pid=123)
    )
    backend.process_identity = lambda: {"pid": 123, "start_ticks": "456"}
    backend.enter_save = lambda *args: Image.new("RGB", (1280, 720))
    setup = backend.prepare(folder, threading.Event(), time.monotonic() + 10)
    assert setup["verified"] and setup["initial"] == read_save(raw)
    assert (backend.root / setup["initial_evidence"]).read_bytes() == raw
    assert backend.startup_pending
    local = json.loads((backend.root / "runtime.local.json").read_text())
    assert local["process"] == {"pid": 123, "start_ticks": "456"}


def backend_fixture(tmp_path):
    """Return a backend polling a private profile that holds the initial save."""
    backend = Backend.__new__(Backend)
    backend.root = tmp_path / "trial"
    backend.folder = backend.root / "episodes/synthetic"
    (backend.folder / "evidence").mkdir(parents=True)
    backend.profile = tmp_path / "private-profile"
    source = config_dir(backend.profile) / "save_files/benchmark/benchmark.sav"
    source.parent.mkdir(parents=True)
    raw = synthetic_save()
    source.write_bytes(raw)
    backend.initial = read_save(raw)
    backend.seen = {backend.initial["sha256"]}
    backend.terminal = None
    backend.assert_runtime = lambda: None
    (backend.profile / "Player.local.log").write_text(f"Loading save file: {source}\n")
    backend.adapter = SimpleNamespace(capture=lambda **kwargs: Image.new("RGB", (1280, 720)))
    return backend, source


def rows(backend):
    """Return the episode's evidence index."""
    index = backend.folder / "evidence.jsonl"
    return [json.loads(line) for line in index.read_text().splitlines()]


def test_poll_preserves_exact_native_bytes_once(tmp_path):
    backend, source = backend_fixture(tmp_path)
    assert backend.poll(0) is None
    assert not (backend.folder / "evidence.jsonl").exists()
    raw = synthetic_save([("Bed", 1)], cycle=1)
    source.write_bytes(raw)
    backend.poll(5)
    backend.poll(6)
    [row] = rows(backend)
    assert row["elapsed"] == 5 and row["kind"] == "save"
    preserved = backend.root / row["path"]
    assert preserved.read_bytes() == raw
    source.write_bytes(b"subsequent game write")
    assert preserved.read_bytes() == raw


def test_partial_save_is_skipped_until_complete(tmp_path):
    backend, source = backend_fixture(tmp_path)
    raw = synthetic_save([("Bed", 1)], cycle=1)
    for partial in (b"", b"incomplete", raw[: len(raw) // 2]):
        source.write_bytes(partial)
        assert backend.poll(1) is None
        assert not (backend.folder / "evidence.jsonl").exists()
    source.write_bytes(raw)
    assert backend.poll(2) is None
    assert (backend.root / rows(backend)[0]["path"]).read_bytes() == raw


def test_death_is_returned_after_its_save_is_preserved(tmp_path):
    backend, source = backend_fixture(tmp_path)
    source.write_bytes(synthetic_save(dead=1, cycle=1))
    assert backend.poll(1) is None
    raw = synthetic_save(dead=3, cycle=2)
    source.write_bytes(raw)
    assert backend.poll(2) == "death"
    assert len(rows(backend)) == 2
    assert (backend.root / rows(backend)[-1]["path"]).read_bytes() == raw
    assert backend.poll(3) == "death"


def test_loading_another_save_is_refused(tmp_path):
    backend, _ = backend_fixture(tmp_path)
    with (backend.profile / "Player.local.log").open("a") as log:
        log.write("Loading save file: other.sav\n")
    with pytest.raises(RuntimeError, match="another save"):
        backend.poll(1)


def test_recovery_restores_death_from_preserved_evidence(tmp_path):
    backend, source = backend_fixture(tmp_path)
    source.write_bytes(synthetic_save(dead=3, cycle=1))
    assert backend.poll(1) == "death"
    (backend.folder / "setup.json").write_text(json.dumps({"initial": backend.initial}))
    (backend.folder / "simulation-start.json").write_text(json.dumps({"status": "completed"}))
    process = {"pid": 123, "start_ticks": "456"}
    (backend.root / "runtime.local.json").write_text(
        json.dumps(
            {
                "profile": str(backend.profile),
                "snapshot": str(tmp_path / "snapshot"),
                "installation": str(tmp_path / "installation"),
                "process": process,
            }
        )
    )
    backend.adapter = SimpleNamespace(release_all=lambda **kwargs: None, find=lambda: None)
    backend.process_identity = lambda: process
    assert backend.recover(backend.folder, {"process": process})
    assert backend.terminal == "death"
    assert backend.recover(backend.folder, {"process": {"pid": 1}}) is False


def test_waits_respect_cancel_and_deadline():
    backend = Backend.__new__(Backend)
    stop = threading.Event()
    stop.set()
    with pytest.raises(InterruptedError):
        backend.wait(1, stop, time.monotonic() + 5)
    with pytest.raises(InterruptedError):
        backend.wait(1, threading.Event(), time.monotonic() - 1)


def test_cleanup_stops_only_when_not_preserving():
    backend = Backend.__new__(Backend)
    calls = []
    backend.adapter = SimpleNamespace(close=lambda: calls.append("release"))
    backend.stop_process = lambda: calls.append("stop")
    backend.close(preserve=True)
    assert calls == ["release"]
    backend.close()
    assert calls == ["release", "release", "stop"]


def preparing_backend(tmp_path, log="Active Mods (0):\n"):
    """Return a backend in the startup menus with the given game log."""
    backend = Backend.__new__(Backend)
    backend.profile = tmp_path
    backend.process = None
    backend.assert_runtime = lambda: None
    (tmp_path / "Player.local.log").write_text(log)
    return backend


def test_enabled_mods_are_refused(tmp_path, monkeypatch):
    backend = preparing_backend(tmp_path, "Active Mods (1):\n")
    backend.adapter = SimpleNamespace(capture=lambda: object())
    monkeypatch.setattr(integration, "preparation_action", lambda image: ("loaded", None))
    with pytest.raises(RuntimeError, match="mods must remain disabled"):
        backend.enter_save(threading.Event(), time.monotonic() + 5)


@pytest.mark.parametrize("ignored", [1, 2, 3])
def test_base_resume_is_retried_a_bounded_number_of_times(tmp_path, monkeypatch, ignored):
    backend = preparing_backend(tmp_path)
    actions = []
    clock = [0]
    frame = object()
    backend.adapter = SimpleNamespace(
        capture=lambda: frame, execute=lambda action, **kwargs: actions.append(action)
    )
    backend.wait = lambda seconds, *args: clock.__setitem__(0, clock[0] + seconds)
    monkeypatch.setattr(integration.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        integration,
        "preparation_action",
        lambda image: ("base_resume", "resume") if len(actions) <= ignored else ("loaded", None),
    )
    if ignored == 3:
        with pytest.raises(RuntimeError, match="did not reach"):
            backend.enter_save(threading.Event(), 30)
    else:
        assert backend.enter_save(threading.Event(), 30) is frame
    assert actions == ["resume"] * min(ignored + 1, 3)
