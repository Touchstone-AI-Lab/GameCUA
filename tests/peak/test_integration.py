"""Offline replays of preserved PEAK native samples through polling and the Trial loop."""

import json
from pathlib import Path

import pytest
from PIL import Image

from gamecua.catalog import Catalog
from gamecua.games.peak.integration import Backend
from gamecua.games.peak.progress import facts
from gamecua.storage import write_json
from gamecua.trials import Trial


def replay_backend(root, prepare_folder=True):
    """Build a backend that replays the preserved native fixture."""
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures/peak/native-segment-regression.json").read_text()
    )
    backend = object.__new__(Backend)
    backend.root = root
    backend.folder = root / "episodes/episode-001"
    if prepare_folder:
        (backend.folder / "evidence").mkdir(parents=True)
    backend.initial = fixture["initial"]
    backend.binding = backend.initial["binding"]
    backend.process_id = {"pid": 42}
    backend.process_identity = lambda: backend.process_id
    backend.offset = 0
    backend.run_start = None
    backend.profile = backend.snapshot = backend.installation = Path("/offline-replay")
    backend.proton = Path("/offline-replay/proton")
    backend.rows = lambda: [item["row"] for item in fixture["samples"]]
    return backend


def test_poll_preserves_real_numeric_anchor_and_returns_native_death(tmp_path):
    backend = replay_backend(tmp_path)
    assert backend.poll(elapsed=100) == "death"
    assert backend.run_start["segment"] == "0"
    saved = json.loads((backend.folder / "evidence.jsonl").read_text())
    found, terminal = facts("save", (backend.root / saved["path"]).read_bytes(), backend.initial)
    assert (found, terminal) == ({f"ascent_{n:03d}m" for n in range(1, 11)}, "death")
    assert backend.offset == 3


def test_real_native_loss_reaches_canonical_episode_restart_with_same_deadline(tmp_path):
    catalog = Catalog(Path(__file__).resolve().parents[2] / "benchmarks")
    spec = catalog.trials["peak-progress-v2-deepseek-live"].model_copy(update={"total_seconds": 10})
    trial = Trial(
        tmp_path / "trial",
        spec,
        catalog.rubrics[spec.rubric_id],
        catalog.games[spec.game_id],
        catalog.models[spec.model_id],
        inputs=catalog.inputs[spec.inputs_id],
    )
    backend = replay_backend(trial.root, prepare_folder=False)
    native_rows = backend.rows()
    preparations = []

    def prepare(folder, stop, deadline):
        preparations.append(deadline)
        backend.folder = folder
        (folder / "evidence").mkdir()
        baseline = folder / "evidence/initial.json"
        write_json(baseline, {"kind": "offline_replay_setup", "benchmark_result": False})
        backend.offset, backend.run_start = 0, None
        backend.rows = lambda: native_rows if len(preparations) == 1 else []
        return {
            "verified": True,
            "initial": backend.initial,
            "initial_evidence": str(baseline.relative_to(trial.root)),
        }

    class OfflineDesktop:
        def capture(self):
            return Image.new("RGB", (1280, 720))

        def release_all(self):
            pass

    class CancelAgent:
        def __init__(self, *args, **kwargs):
            pass

        def decide(self, image, memory, history, stop, deadline):
            stop.set()
            return {
                "observation": "offline replay",
                "hypothesis": "cancel test",
                "memory": "",
                "terminal_candidate": False,
                "action": {"type": "wait", "seconds": 0.1},
            }, {}

        def close(self):
            pass

    class OfflineRecorder:
        def __init__(self, *args):
            pass

        def close(self):
            pass

    backend.adapter = OfflineDesktop()
    backend.prepare = prepare
    backend.checkpoint = lambda: {"offline_replay": True}
    backend.close = lambda **kwargs: None
    trial.backend, trial.agent_factory, trial.recorder = backend, CancelAgent, OfflineRecorder
    trial.run(install_signals=False, acquire_lease=False)
    first, second = trial.state["episodes"]
    assert first["status"] == "completed" and first["reason"] == "death"
    assert first["trial_id"] == second["trial_id"] == trial.state["id"]
    assert trial.state["deadline"] - trial.state["started_at"] == pytest.approx(10)
    assert trial.state["infrastructure_downtime_seconds"] == 0
    assert len(preparations) == 2 and preparations[1] < float("inf")
