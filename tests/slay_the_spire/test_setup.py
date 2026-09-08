"""Snapshot capture and per-profile evidence attribution."""

import json
import signal
import subprocess

from gamecua.games.slay_the_spire.integration import Backend, capture_snapshot
from gamecua.games.slay_the_spire.saves import encode_autosave


def test_snapshot_copies_state_and_records_the_encounter(tmp_path):
    source = tmp_path / "game"
    (source / "saves").mkdir(parents=True)
    (source / "preferences").mkdir()
    save = source / "saves/IRONCLAD.autosave"
    raw = encode_autosave({"seed": 42, "floor_num": 1})
    save.write_bytes(raw)
    target = capture_snapshot(source, tmp_path / "snapshot", "Cultist")
    assert (target / "saves/IRONCLAD.autosave").read_bytes() == raw
    golden = json.loads((target / "GOLDEN.json").read_text())
    assert golden["initial_state"] == {"encounter": "Cultist", "seed": 42}
    assert "GOLDEN.json" in json.loads((target / "snapshot.manifest.json").read_text())


def test_backend_attributes_only_its_new_profile_history(tmp_path):
    root = tmp_path / "trial"
    folder = root / "episodes/episode-001"
    (folder / "evidence").mkdir(parents=True)
    profile = tmp_path / "private"
    (profile / "runs/IRONCLAD").mkdir(parents=True)
    death = {
        "seed_played": "42",
        "character_chosen": "IRONCLAD",
        "victory": False,
        "floor_reached": 2,
        "killed_by": "Cultist",
    }
    (profile / "runs/IRONCLAD/foreign.run").write_text(json.dumps({**death, "seed_played": "99"}))
    (profile / "runs/IRONCLAD/partial.run").write_text('{"seed_played": "4')
    backend = object.__new__(Backend)
    backend.root, backend.folder, backend.profile = root, folder, profile
    backend.process, backend.terminal = None, None
    backend.initial, backend.seen, backend.log_offset = {"seed": 42}, {}, 0
    assert backend.poll(1) is None
    assert not (folder / "evidence.jsonl").exists()
    (profile / "runs/IRONCLAD/new.run").write_text(json.dumps(death))
    assert backend.poll(2) == "death"
    rows = (folder / "evidence.jsonl").read_text().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["kind"] == "history"


def test_stop_signals_only_the_recorded_process():
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        backend = object.__new__(Backend)
        backend.process, backend.pause_handle = None, None
        backend.identity = {"pid": child.pid, "start_ticks": "0"}
        backend.stop_process()
        assert child.poll() is None
        backend.identity = backend.checkpoint()
        backend.stop_process()
        assert child.wait(timeout=5) == -signal.SIGTERM
    finally:
        child.kill()
        child.wait()
