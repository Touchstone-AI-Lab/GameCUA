"""Offline replay checks for raw evidence, partial writes and recovery."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from gamecua.games.understand import integration
from gamecua.games.understand.integration import Backend, initial_menu
from gamecua.games.understand.progress import SPINE
from gamecua.storage import sha256, write_json

FIXTURES = Path(__file__).parents[1] / "fixtures/understand"


def replay(tmp_path):
    backend = object.__new__(Backend)
    backend.root = tmp_path / "trial"
    backend.folder = backend.root / "episodes/episode-001"
    (backend.folder / "evidence").mkdir(parents=True)
    backend.profile = backend.root.parent / ".profiles" / backend.root.name / backend.folder.name
    backend.game.mkdir(parents=True)
    (backend.game / "understand.sav").write_bytes((FIXTURES / "zero-progress.sav").read_bytes())
    backend.identity = {"pid": 42, "start_ticks": "10"}
    backend.process = None
    backend.process_identity = lambda: backend.identity
    backend.quit_restarts = SimpleNamespace(before_poll=lambda: False)
    backend.adapter = SimpleNamespace(release_all=lambda **kwargs: None)
    backend.initial = {"active_slot": 1}
    backend.seen = sha256(backend.game / "understand.sav")
    return backend


def rows(backend):
    return [
        json.loads(line) for line in (backend.folder / "evidence.jsonl").read_text().splitlines()
    ]


def test_opening_menu_gate_accepts_real_fresh_menu_and_rejects_puzzle():
    assert initial_menu(Image.open(FIXTURES / "opening-menu.png"))
    assert not initial_menu(Image.open(FIXTURES / "puzzle-panel.png"))
    assert not initial_menu(Image.new("RGB", (1280, 720), (221, 221, 221)))


def test_raw_native_evidence_is_immutable_indexed_and_not_duplicated(tmp_path):
    backend = replay(tmp_path)
    assert backend.poll(0) is None
    assert not (backend.folder / "evidence.jsonl").exists()
    value = (FIXTURES / "completed-group.sav").read_bytes()
    (backend.game / "understand.sav").write_bytes(value)
    assert backend.poll(15.5) is None
    assert len(rows(backend)) == 1 and rows(backend)[0]["elapsed"] == 15.5
    evidence = backend.root / rows(backend)[0]["path"]
    assert evidence.read_bytes() == value
    assert sha256(evidence) == rows(backend)[0]["sha256"]
    backend.poll(16)
    assert len(rows(backend)) == 1
    (backend.game / "understand.sav").write_bytes(b"changed mutable output")
    assert evidence.read_bytes() == value


def test_partial_save_is_skipped_without_dropping_the_next_valid_save(tmp_path):
    backend = replay(tmp_path)
    (backend.game / "understand.sav").write_bytes(b"[")
    assert backend.poll(1) is None
    assert not (backend.folder / "evidence.jsonl").exists()
    (backend.game / "understand.sav").write_bytes((FIXTURES / "completed-group.sav").read_bytes())
    backend.poll(2)
    assert len(rows(backend)) == 1


@pytest.mark.parametrize("same_process", [True, False])
def test_recovery_requires_the_original_live_process(tmp_path, same_process):
    backend = replay(tmp_path)
    write_json(backend.folder / "setup.json", {"initial": backend.initial})
    write_json(
        backend.root / "runtime.local.json",
        {
            "profile": str(backend.profile),
            "snapshot": str(tmp_path / "snapshot"),
            "installation": str(tmp_path / "installation"),
            "process": backend.identity,
        },
    )
    checkpoint = backend.checkpoint()
    if not same_process:
        backend.process_identity = lambda: {"pid": 42, "start_ticks": "11"}
    backend.seen = None
    assert backend.recover(backend.folder, checkpoint) is same_process
    assert backend.seen == checkpoint["save_sha256"]


def test_preserve_close_never_stops_a_running_episode(tmp_path):
    backend = replay(tmp_path)
    calls = []
    backend.adapter.close = lambda: calls.append("adapter")
    backend.stop_process = lambda: calls.append("stop")
    backend.close(preserve=True)
    assert calls == ["adapter"]
    backend.close()
    assert calls == ["adapter", "adapter", "stop"]


def test_cleanup_does_not_signal_a_reused_process_id(tmp_path, monkeypatch):
    backend = replay(tmp_path)
    backend.process_identity = lambda: {"pid": 42, "start_ticks": "reused"}
    calls = []
    monkeypatch.setattr(integration.os, "killpg", lambda *args: calls.append(args))
    backend.stop_process()
    assert calls == []


def test_verified_native_ending_is_reported_on_new_and_unchanged_evidence(tmp_path):
    backend = replay(tmp_path)
    data = json.loads((FIXTURES / "zero-progress.sav").read_bytes())
    data[1][0] = list(SPINE)
    (backend.game / "understand.sav").write_text(json.dumps(data))
    assert backend.poll(10) == "victory"
    assert backend.poll(11) == "victory"
    assert len(rows(backend)) == 1
