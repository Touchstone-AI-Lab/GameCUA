"""Offline tests for Baba Is You slot-save parsing and predicate inputs."""

import signal
import subprocess
from pathlib import Path

from gamecua.games.baba_is_you.integration import running, signal_group
from gamecua.games.baba_is_you.progress import facts
from gamecua.games.baba_is_you.saves import read_save

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/baba-is-you/after-first-level.ba"
OPENING = b"[baba]\nintro=1\ntime=0\nfirsttime=1\n0level_intro=1\ntime_frames=0\nPrevious=0level\n"


def synthetic(levels, extra=""):
    rows = "".join(f"{name}=3\n" for name in levels)
    return f"[baba_prize]\ntotal={len(levels)}\n\n[baba]\n{rows}{extra}".encode()


def test_real_save_after_opening_level():
    data = read_save(FIXTURE.read_bytes())
    assert data["cleared"] == ["0level"]
    assert data["areas_complete"] == []
    assert data["prize_total"] == 1
    assert data["map_prizes"] == {"106level": 1}
    assert data["clears_total"] == 0


def test_opening_save_has_no_clears():
    assert read_save(OPENING)["cleared"] == []
    assert read_save(b"")["cleared"] == []


def test_unlocked_maps_and_path_tiles_are_not_clears():
    raw = synthetic(["0level", "106level"], "1level=2\n106level,11,16=3\nPrevious=0level\n")
    data = read_save(raw)
    assert data["cleared"] == ["0level"]
    assert data["areas_complete"] == ["106level"]


def test_only_save_evidence_produces_facts():
    levels = [f"{n}level" for n in range(12)]
    assert facts("history", synthetic(levels), read_save(OPENING)) == (set(), None)


def test_group_signal_needs_the_recorded_leader():
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        stat = Path(f"/proc/{child.pid}/stat").read_text()
        identity = {"pid": child.pid, "start_ticks": stat.rsplit(")", 1)[1].split()[19]}
        signal_group({**identity, "start_ticks": "0"}, signal.SIGTERM)
        assert child.poll() is None and running(identity)
        signal_group(identity, signal.SIGTERM)
        assert child.wait(timeout=5) == -signal.SIGTERM and not running(identity)
    finally:
        child.kill()
        child.wait()
