"""Offline synthetic Trial lifecycle through the real native polling and endpoint scoring."""

import copy
import json
import threading
from pathlib import Path

import pytest
from PIL import Image

from gamecua.catalog import Catalog
from gamecua.evidence import export, score
from gamecua.execution import MEMORY_LIMIT, NEW_ATTEMPT
from gamecua.games.art_of_rally.integration import Backend
from gamecua.games.art_of_rally.progress import Writer
from gamecua.trials import Trial

from .fixtures import Recorder, Stream, encoded


def stream_for(outcome, number):
    stream = Stream(size=40, binding=f"synthetic-episode-{number:03d}")
    if outcome == "death":
        stream.die("retirement")
    else:
        stream.rally()
    return stream


class SyntheticBackend(Backend):
    def __init__(self, streams, workspace):
        self.streams, self.workspace = streams, workspace
        self.desktop = self.adapter = self
        self.pause = self.process = None
        self.prepared = self.executed = self.released = 0
        self.deadlines = []

    def prepare(self, folder, stop, deadline):
        self.stream = self.streams[self.prepared]
        self.prepared += 1
        self.folder, self.initial = folder, self.stream.initial
        self.deadlines.append(self.trial.state["deadline"])
        (folder / "evidence").mkdir()
        self.native = self.workspace / f"native-{self.prepared}.local.jsonl"
        self.native.write_bytes(encoded(self.stream.rows[:1]))
        self.offset = 0
        self.writer = Writer(self.root, folder, self.initial)
        return {"verified": True, "initial": self.initial}

    def checkpoint(self):
        return {"binding": self.initial["binding"]}

    def capture(self):
        return Image.new("RGB", (80, 45))

    def execute(self, action, **kwargs):
        with self.native.open("ab") as output:
            output.write(encoded(self.stream.rows[1:]))
        self.executed += 1

    def release_all(self):
        self.released += 1

    def close(self, **kwargs):
        self.release_all()


@pytest.mark.parametrize("model", ["deepseek", "jev"])
@pytest.mark.parametrize("first_outcome", ["death", "victory"])
def test_shared_trial_native_outcomes_context_budget_and_export(tmp_path, model, first_outcome):
    catalog = Catalog(Path("benchmarks"))
    trial_id = (
        f"art-of-rally-five-stage-integer-v8-{model}-live-{'3h' if model == 'deepseek' else '1h'}"
    )
    spec = catalog.trials[trial_id].model_copy(update={"total_seconds": 60})
    outcomes = [first_outcome]
    if first_outcome == "death" and model == "deepseek":
        outcomes.append("victory")
    backend = SyntheticBackend(
        [stream_for(outcome, index) for index, outcome in enumerate(outcomes, 1)], tmp_path
    )
    received, bound, prompts = [], [], []
    note = "Own uncertain observation about steering. " * 60

    class Agent:
        def __init__(self, *args, model_spec, prompt, **kwargs):
            self.model_id = model_spec.id
            prompts.append(prompt)

        def bind_context(self, directory, initial):
            bound.append(copy.deepcopy(initial))
            self.directory = directory
            directory.mkdir()
            self.context = initial or {
                "items": [],
                "compactions": 0,
                "pending_request": False,
                "inheritance": False,
            }
            (directory / "latest.json").write_text(json.dumps(self.context))

        def decide(self, image, memory, history, stop, deadline):
            received.append((self.model_id, memory, copy.deepcopy(history)))
            return {
                "observation": "Synthetic screen observation",
                "hypothesis": "Uncertain steering response",
                "memory": note,
                "action": {"type": "wait", "seconds": 0.01},
            }, {}

        def close(self):
            pass

    trial = Trial(
        tmp_path / "trial",
        spec,
        catalog.rubrics[spec.rubric_id],
        catalog.games[spec.game_id],
        catalog.models[spec.model_id],
        backend,
        agent_factory=Agent,
        recorder=Recorder,
        inputs=catalog.inputs[spec.inputs_id],
    )
    backend.trial, backend.root = trial, trial.root
    trial.state["eligible"] = False
    trial.persist()
    trial.run(install_signals=False, acquire_lease=False)
    assert trial.state["status"] == "completed"
    assert trial.state["reason"] == (
        "death_without_memory" if outcomes == ["death"] else "verified_run_completion"
    )
    assert [episode["reason"] for episode in trial.state["episodes"]] == outcomes
    assert backend.prepared == backend.executed == len(outcomes)
    assert backend.deadlines == [None] + [trial.state["deadline"]] * (len(outcomes) - 1)
    assert bound[0] is None
    assert received[0][1:] == ("", [])
    assert all(item[0] == spec.model_id for item in received)
    if len(outcomes) == 2:
        assert received[1][1:] == (note[:MEMORY_LIMIT], [])
        assert NEW_ATTEMPT in prompts[1]
    _, result = score(trial.root, episode_limit=1)
    assert result["score"] == (0 if first_outcome == "death" else 100)
    assert result["scoreable"] and result["completion_status"] == "completed"
    assert result["comparison_eligible"] == (len(outcomes) == 2)
    assert not result["failures"]
    assert [episode["outcome"] for episode in result["episodes"]] == [first_outcome]
    target = export(trial.root, tmp_path / "export")
    assert score(target, episode_limit=1)[1] == result
    assert not any(target.rglob("*.local.jsonl"))


class FakePause:
    def __init__(self, ack):
        self.last_ack, self.thawed = ack, 0

    def thaw(self):
        self.thawed += 1


@pytest.mark.parametrize(
    "frozen,ack,armed",
    [
        (True, {"disposition": "driving"}, True),
        (True, {"disposition": "transition_process_frozen"}, False),
        (False, {"disposition": "driving"}, False),
    ],
)
def test_thaw_arms_native_steps_only_for_frozen_driving(frozen, ack, armed):
    backend = Backend.__new__(Backend)
    backend.pause, backend.frozen, backend.step_seconds = FakePause(ack), frozen, 1.0
    backend.wait_stop = threading.Event()
    backend.native_step = backend.executing_native_step = None
    backend.thaw()
    assert (backend.native_step is not None) == armed
    assert backend.pause.thawed == int(not armed)
