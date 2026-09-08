import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fake_clients import SdkShapedClient
from PIL import Image

from gamecua.catalog import Catalog
from gamecua.evidence import export, score
from gamecua.games.slay_the_spire.progress import facts
from gamecua.games.slay_the_spire.saves import encode_autosave
from gamecua.provider import VisionAgent
from gamecua.specs import TrialRecord, TrialSpec
from gamecua.storage import write_json
from gamecua.trials import Budget, Trial

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Catalog(ROOT / "benchmarks")
INITIAL = {
    "seed": 42,
    "act_num": 1,
    "floor_num": 1,
    "current_health": 80,
    "monsters_killed": 0,
    "metric_damage_taken": [],
}


def make_trial(root, seconds=10):
    spec = TrialSpec(
        id="test-trial",
        game_id="slay-the-spire",
        model_id="deepseek-flash",
        rubric_id="sts-progress-pilot",
        total_seconds=seconds,
    )
    return Trial(
        root,
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
    )


def add_episode(trial, name, observations):
    folder = trial.root / "episodes" / name
    folder.mkdir(parents=True)
    initial = folder / "initial.autosave"
    initial.write_bytes(encode_autosave(INITIAL))
    write_json(
        folder / "setup.json",
        {
            "verified": True,
            "initial": INITIAL,
            "initial_evidence": str(initial.relative_to(trial.root)),
            "initial_sha256": hashlib.sha256(initial.read_bytes()).hexdigest(),
        },
    )
    trial.state["episodes"].append(
        {"id": name, "status": "completed", "reason": "deadline", "segments": []}
    )
    rows = []
    for i, (kind, data, elapsed) in enumerate(observations):
        path = folder / f"{i}.{'autosave' if kind == 'save' else 'run'}"
        path.write_bytes(encode_autosave(data) if kind == "save" else json.dumps(data).encode())
        rows.append(
            {
                "kind": kind,
                "path": str(path.relative_to(trial.root)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "elapsed": elapsed,
            }
        )
    (folder / "evidence.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))


def completed(trial):
    trial.budget.start()
    trial.finish("completed", "deadline")


def combat(**fields):
    return {
        **INITIAL,
        "post_combat": True,
        "monsters_killed": 1,
        "metric_damage_taken": [{"floor": 1, "enemies": "Cultist"}],
        **fields,
    }


def test_budget_survives_restart_and_charges_downtime():
    clock = [100.0]
    ticks = [500.0]
    state = TrialRecord(id="trial").model_dump()
    budget = Budget(state, 30, lambda: clock[0], lambda: ticks[0])
    budget.start()
    clock[0] = 107
    ticks[0] = 507
    budget.touch()
    saved = json.loads(json.dumps(state))
    clock[0] = 125
    ticks[0] = 1000
    restored = Budget(saved, 30, lambda: clock[0], lambda: ticks[0])
    assert restored.remaining() == 5
    restored.start()
    assert saved["deadline"] == 130
    clock[0] = 132
    ticks[0] = 1007
    restored.touch()
    assert restored.remaining() == 0 and saved["chargeable_seconds"] == 30
    assert saved["elapsed_seconds"] == 32


def test_duplicate_credit_and_offline_portability(tmp_path):
    trial = make_trial(tmp_path / "trial")
    add_episode(
        trial,
        "episode-001",
        [
            ("save", combat(), 1.0),
            ("save", combat(), 2.0),
            (
                "history",
                {
                    "seed_played": "42",
                    "character_chosen": "IRONCLAD",
                    "floor_reached": 2,
                    "victory": False,
                    "killed_by": "Cultist",
                },
                2.5,
            ),
        ],
    )
    trial.state["episodes"][0]["reason"] = "death"
    add_episode(trial, "episode-002", [("save", combat(), 3.0)])
    completed(trial)
    first_path, first = score(trial.root)
    _, second = score(trial.root)
    assert first_path.exists() and first["score"] == second["score"] == 10
    assert first["awards"][0]["episode_id"] == "episode-001"
    assert first["episodes"][0]["outcome"] == "death"
    target = export(trial.root, tmp_path / "portable")
    assert score(target)[1]["score"] == 10
    assert len(list((trial.root / "scores").glob("*.json"))) == 2
    assert not (target / "runtime.local.json").exists()


def test_prerequisites_stay_within_one_episode(tmp_path):
    trial = make_trial(tmp_path / "trial")
    add_episode(trial, "episode-001", [("save", {**INITIAL, "act_num": 2}, 1.0)])
    add_episode(
        trial,
        "episode-002",
        [("save", {**INITIAL, "act_num": 2}, 2.0), ("save", {**INITIAL, "act_num": 3}, 3.0)],
    )
    completed(trial)
    result = score(trial.root)[1]
    assert result["score"] == 40
    assert {a["milestone_id"] for a in result["awards"]} == {"act-one", "act-two"}
    assert result["awards"][1]["episode_id"] == "episode-002"
    assert "first-elite" not in {a["milestone_id"] for a in result["awards"]}


def test_late_evidence_is_not_scored(tmp_path):
    trial = make_trial(tmp_path / "trial")
    add_episode(trial, "episode-001", [("save", combat(), 11.0)])
    completed(trial)
    assert score(trial.root)[1]["score"] == 0


def test_setup_failure_has_no_model_score(tmp_path):
    trial = make_trial(tmp_path / "trial")
    folder = trial.root / "episodes/episode-001"
    folder.mkdir(parents=True)
    write_json(folder / "setup.json", {"verified": False})
    trial.state["episodes"].append({"id": "episode-001", "status": "setup_failure"})
    trial.finish("interrupted", "setup_unverified")
    assert not score(trial.root)[1]["scoreable"]


def test_death_and_victory_need_game_history():
    history = {
        "seed_played": "42",
        "character_chosen": "IRONCLAD",
        "floor_reached": 1,
        "victory": False,
        "killed_by": "Cultist",
    }
    assert facts("history", json.dumps(history).encode(), INITIAL)[1] == "death"
    assert facts("save", encode_autosave(combat()), INITIAL)[1] is None
    with pytest.raises(ValueError):
        facts("history", json.dumps({**history, "seed_played": "43"}).encode(), INITIAL)


class FakeRecorder:
    def __init__(self, *args):
        pass

    def close(self):
        pass


class FakeBackend:
    def __init__(self, root):
        self.root, self.adapter = root, self
        self.actions = []
        self.preparations = 0

    def prepare(self, folder, stop, deadline):
        self.preparations += 1
        path = folder / "initial.autosave"
        path.write_bytes(encode_autosave(INITIAL))
        return {
            "verified": True,
            "initial": INITIAL,
            "initial_evidence": str(path.relative_to(self.root)),
            "initial_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def checkpoint(self):
        return {"fixture": True}

    def recover(self, *args):
        return True

    def capture(self):
        return Image.new("RGB", (1280, 720))

    def execute(self, action, **kwargs):
        self.actions.append(action)

    def poll(self, elapsed):
        return None

    def release_all(self):
        pass

    def close(self, **kwargs):
        pass


class InterruptedAgent:
    contexts = []

    def __init__(self, *args, **kwargs):
        pass

    def decide(self, image, memory, history, stop, deadline):
        self.contexts.append((memory, history.copy()))
        stop.set()
        return {
            "observation": "screen",
            "hypothesis": "guess",
            "memory": "notes",
            "terminal_candidate": True,
            "action": {"type": "wait", "seconds": 0.1},
        }, {}

    def close(self):
        pass


def test_recovery_is_same_episode_and_budget(tmp_path):
    trial = make_trial(tmp_path / "trial")
    backend = FakeBackend(trial.root)
    trial.backend, trial.agent_factory, trial.recorder = backend, InterruptedAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    deadline = trial.state["deadline"]
    episode_id = trial.state["episodes"][0]["id"]
    resumed = Trial(
        trial.root, backend=backend, agent_factory=InterruptedAgent, recorder=FakeRecorder
    )
    resumed.run(install_signals=False, acquire_lease=False)
    assert resumed.state["deadline"] == deadline
    assert resumed.state["episodes"][0]["id"] == episode_id
    assert len(resumed.state["episodes"]) == 1 and backend.preparations == 1
    assert len(resumed.state["episodes"][0]["segments"]) == 2
    assert not backend.actions
    assert all(memory == "" and history == [] for memory, history in InterruptedAgent.contexts)


def test_pending_action_prevents_unverified_recovery(tmp_path):
    trial = make_trial(tmp_path / "trial")
    backend = FakeBackend(trial.root)
    trial.backend, trial.agent_factory, trial.recorder = backend, InterruptedAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    path = next(trial.root.glob("episodes/*/segments/*/[0-9]*.json"))
    row = json.loads(path.read_text())
    row["execution_status"] = "pending"
    write_json(path, row)
    resumed = Trial(trial.root, backend=backend)
    resumed.run(install_signals=False, acquire_lease=False)
    assert resumed.state["reason"] == "recovery_unverifiable" and not resumed.state["eligible"]
    assert backend.actions == []


class LateAgent(InterruptedAgent):
    def decide(self, image, memory, history, stop, deadline):
        time.sleep(0.3)
        return {
            "observation": "screen",
            "hypothesis": "guess",
            "memory": "notes",
            "terminal_candidate": False,
            "action": {"type": "wait", "seconds": 0.1},
        }, {}


def test_late_request_is_preserved_without_executing(tmp_path):
    trial = make_trial(tmp_path / "trial", seconds=0.2)
    backend = FakeBackend(trial.root)
    trial.backend, trial.agent_factory, trial.recorder = backend, LateAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert trial.state["status"] == "completed" and trial.state["reason"] == "deadline"
    assert backend.actions == []
    row = json.loads(next(trial.root.glob("episodes/*/segments/*/[0-9]*.json")).read_text())
    assert row["execution_status"] == "rejected"


def test_independent_trials_have_fresh_context(tmp_path):
    InterruptedAgent.contexts.clear()
    trials = []
    for name in ("trial-a", "trial-b"):
        trial = make_trial(tmp_path / name)
        trial.backend = FakeBackend(trial.root)
        trial.agent_factory, trial.recorder = InterruptedAgent, FakeRecorder
        trial.run(install_signals=False, acquire_lease=False)
        trials.append(trial)
    assert trials[0].state["id"] != trials[1].state["id"]
    assert InterruptedAgent.contexts == [("", []), ("", [])]


def test_death_restarts_episode_without_resetting_budget(tmp_path):
    class DeathBackend(FakeBackend):
        def poll(self, elapsed):
            return "death" if self.preparations == 1 else None

    trial = make_trial(tmp_path / "trial")
    trial.backend = DeathBackend(trial.root)
    trial.agent_factory, trial.recorder = InterruptedAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    episodes = trial.state["episodes"]
    assert len(episodes) == 2 and episodes[0]["reason"] == "death"
    assert episodes[0]["trial_id"] == episodes[1]["trial_id"] == trial.state["id"]
    assert trial.state["deadline"] - trial.state["started_at"] == pytest.approx(10, abs=0.01)


def test_typed_model_death_ends_the_trial_without_a_new_episode(tmp_path):
    class DeathBackend(FakeBackend):
        def poll(self, elapsed):
            return "death"

    spec = TrialSpec(
        id="typed-death",
        game_id="slay-the-spire",
        model_id="jev-1-14",
        rubric_id="sts-victory-v3",
        total_seconds=10,
        inputs_id="sts-grid-v3",
    )
    trial = Trial(
        tmp_path / "trial",
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
        inputs=CATALOG.inputs[spec.inputs_id],
    )
    trial.backend = DeathBackend(trial.root)
    trial.agent_factory, trial.recorder = InterruptedAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert len(trial.state["episodes"]) == 1
    assert (trial.state["status"], trial.state["reason"]) == ("completed", "death_without_memory")
    _, result = score(trial.root)
    assert result["completion_status"] == "completed"


def test_invalid_model_output_consumes_budget_without_disqualifying(tmp_path):
    from gamecua.provider import ProviderFailure

    class InvalidAgent(InterruptedAgent):
        def decide(self, image, memory, history, stop, deadline):
            time.sleep(0.04)
            raise ProviderFailure("Malformed decision", "model_output")

    trial = make_trial(tmp_path / "trial", seconds=0.12)
    trial.backend = FakeBackend(trial.root)
    trial.agent_factory, trial.recorder = InvalidAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert trial.state["reason"] == "deadline" and trial.state["eligible"]
    assert trial.state["chargeable_seconds"] == pytest.approx(0.12)
    assert not trial.backend.actions


def test_stale_observation_is_rejected_by_current_executor(tmp_path):
    class ChangedBackend(FakeBackend):
        captures = 0

        def capture(self):
            self.captures += 1
            return Image.new("RGB", (1280, 720), "black" if self.captures == 1 else "white")

    class Agent(InterruptedAgent):
        calls = 0

        def decide(self, *args):
            self.calls += 1
            if self.calls == 2:
                args[3].set()
            return {
                "observation": "screen",
                "hypothesis": "guess",
                "memory": "notes",
                "terminal_candidate": False,
                "action": {"type": "wait", "seconds": 0.1},
            }, {}

    trial = make_trial(tmp_path / "trial")
    trial.backend = ChangedBackend(trial.root)
    trial.agent_factory, trial.recorder = Agent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    row = json.loads(next(trial.root.glob("episodes/*/segments/*/00001.json")).read_text())
    assert row["reason"] == "stale_observation" and not row["executed"]
    assert trial.backend.actions == []


def _threshold_trial(tmp_path, timing, second_color, **spec_update):
    class Backend(FakeBackend):
        captures = 0

        def capture(self):
            self.captures += 1
            return Image.new("RGB", (1280, 720), "black" if self.captures == 1 else second_color)

    class Agent(InterruptedAgent):
        calls = 0

        def decide(self, *args):
            self.calls += 1
            if self.calls == 2:
                args[3].set()
            return {
                "observation": "screen",
                "hypothesis": "guess",
                "memory": "notes",
                "terminal_candidate": False,
                "action": {"type": "wait", "seconds": 0.1},
            }, {}

    trial = make_trial(tmp_path / "trial")
    trial.game = trial.game.model_copy(update={"timing": timing})
    trial.spec = trial.spec.model_copy(update=spec_update)
    trial.backend, trial.agent_factory, trial.recorder = Backend(trial.root), Agent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    row = json.loads(next(trial.root.glob("episodes/*/segments/*/00001.json")).read_text())
    return trial, row


def test_realtime_observation_age_limit_comes_from_the_trial_spec(tmp_path):
    trial, row = _threshold_trial(
        tmp_path / "strict", "realtime", "black", observation_age_limit_seconds=1e-9
    )
    assert row["reason"] == "observation_age_limit" and not row["executed"]
    assert trial.backend.actions == []
    trial, row = _threshold_trial(tmp_path / "default", "realtime", "black")
    assert row["executed"] and len(trial.backend.actions) == 1


def test_turn_based_stale_pixel_delta_comes_from_the_trial_spec(tmp_path):
    trial, row = _threshold_trial(
        tmp_path / "loose", "turn_based", "white", stale_pixel_delta=255.0
    )
    assert row["executed"] and row["pre_execution_pixel_delta"] == 255
    trial, row = _threshold_trial(tmp_path / "default", "turn_based", "white")
    assert row["reason"] == "stale_observation" and not row["executed"]


def test_default_thresholds_are_not_serialized_and_overrides_are():
    base = TrialSpec(id="test-trial", game_id="g", rubric_id="r", total_seconds=10.0)
    assert "observation_age_limit_seconds" not in base.model_dump()
    assert "stale_pixel_delta" not in base.model_dump()
    changed = base.model_validate(
        {**base.model_dump(), "observation_age_limit_seconds": 90.0, "stale_pixel_delta": 20}
    )
    assert changed.model_dump()["observation_age_limit_seconds"] == 90.0
    assert changed.model_dump()["stale_pixel_delta"] == 20
    assert changed.observation_age_limit_seconds == 90.0


def test_model_terminal_claim_does_not_end_gameplay_as_a_win(tmp_path):
    class Backend(FakeBackend):
        def poll(self, elapsed):
            if self.actions:
                trial.stop.set()
            return None

    class Claimant(InterruptedAgent):
        def decide(self, *args):
            return {
                "observation": "screen",
                "hypothesis": "guess",
                "memory": "notes",
                "terminal_candidate": True,
                "action": {"type": "wait", "seconds": 0.1},
            }, {}

    trial = make_trial(tmp_path / "trial")
    trial.backend = Backend(trial.root)
    trial.agent_factory, trial.recorder = Claimant, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert len(trial.backend.actions) == 1
    assert trial.state["status"] == "interrupted"
    assert trial.state["episodes"][0]["reason"] != "victory"


@pytest.mark.parametrize("reason", ["ProviderFailure", "model_output", "execution_failure"])
def test_earned_score_survives_later_failure(tmp_path, reason):
    trial = make_trial(tmp_path / reason)
    add_episode(trial, "episode-001", [("save", combat(), 1.0)])
    trial.budget.start()
    trial.state["eligible"] = False
    trial.finish("interrupted", reason)
    path, result = score(trial.root)
    before = path.read_bytes()
    assert result["score"] == 10 and result["scoreable"]
    assert result["completion_status"] == "incomplete" and not result["comparison_eligible"]
    assert result["trial_reason"] == reason
    score(trial.root)
    assert path.read_bytes() == before


def test_death_memory_is_bounded_and_drops_old_actions(tmp_path):
    from gamecua.execution import MEMORY_LIMIT, NEW_ATTEMPT, inherited_context

    episodes = [
        {"id": "episode-001", "reason": "death", "segments": [{"id": "segment-001"}]},
        {"id": "episode-002", "reason": None, "segments": []},
    ]
    segment = tmp_path / "episodes/episode-001/segments/segment-001"
    segment.mkdir(parents=True)
    write_json(
        segment / "00001.json",
        {
            "step": 1,
            "execution_status": "completed",
            "decision": {
                "memory": "I observed a button respond. " * 200,
                "action": {"type": "press", "key": "Return"},
            },
        },
    )
    write_json(
        segment / "00002.json",
        {
            "step": 2,
            "execution_status": "pending",
            "decision": {
                "memory": "Uncertain state must not be inherited",
                "action": {"type": "press", "key": "Escape"},
            },
        },
    )
    context = inherited_context(tmp_path, episodes[-1], episodes, "trial_memory")
    assert len(context["memory"]) == MEMORY_LIMIT
    assert context["history"] == [] and context["attempt_notice"] == NEW_ATTEMPT
    assert context["provenance"]["source"].endswith("segment-001")
    assert "Uncertain" not in context["memory"]
    assert not {"rubric", "setup", "seed", "milestones"} & context.keys()
    fresh = inherited_context(tmp_path, episodes[0], [episodes[0]], "fresh")
    assert fresh["provenance"]["kind"] == "recovery"
    assert fresh["history"][0]["action"]["key"] == "Return"
    independent = inherited_context(tmp_path, {"id": "new", "segments": []}, [], "trial_memory")
    assert independent["memory"] == "" and independent["history"] == []


def test_incomplete_scores_are_excluded_from_series(tmp_path):
    from gamecua.trials import run_series

    def create(root):
        trial = make_trial(root)
        add_episode(trial, "episode-001", [("save", combat(), 1.0)])

        def run():
            trial.budget.start()
            trial.finish("interrupted", "ProviderFailure")

        trial.run = run
        return trial

    report = run_series(tmp_path / "series", 2, create)
    assert report["valid_count"] == 0 and report["score_mean"] is None
    assert report["incomplete_trials"][0]["score"] == 10


def test_realtime_world_changes_do_not_reject_ordinary_input(tmp_path):
    class Backend(FakeBackend):
        captures = 0

        def capture(self):
            self.captures += 1
            return Image.new("RGB", (1280, 720), "black" if self.captures == 1 else "white")

        def poll(self, elapsed):
            if self.actions:
                trial.stop.set()
            return None

    class Agent(InterruptedAgent):
        def decide(self, *args):
            return {
                "observation": "changing screen",
                "hypothesis": "unknown",
                "memory": "own observation",
                "terminal_candidate": False,
                "action": {"type": "wait", "seconds": 0.1},
            }, {"latency_seconds": 0.2}

    trial = make_trial(tmp_path / "trial")
    trial.game = trial.game.model_copy(update={"timing": "realtime"})
    trial.backend, trial.agent_factory, trial.recorder = Backend(trial.root), Agent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert len(trial.backend.actions) == 1
    row = json.loads(next(trial.root.glob("episodes/*/segments/*/00001.json")).read_text())
    assert row["executed"] and row["pre_execution_pixel_delta"] == 255


def test_executor_inherits_own_notes_after_verified_death(tmp_path):
    contexts = []

    class Backend(FakeBackend):
        def poll(self, elapsed):
            if self.preparations == 1 and self.actions and not getattr(self, "reported", False):
                self.reported = True
                return "death"
            return None

    class Agent(InterruptedAgent):
        def decide(self, image, memory, history, stop, deadline):
            contexts.append((memory, history.copy()))
            if memory:
                stop.set()
            return {
                "observation": "own rendered observation",
                "hypothesis": "unverified",
                "memory": "I observed a response to Return.",
                "terminal_candidate": False,
                "action": {"type": "press", "key": "Return"},
            }, {}

    trial = make_trial(tmp_path / "trial")
    trial.backend, trial.agent_factory, trial.recorder = Backend(trial.root), Agent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert contexts == [("", []), ("I observed a response to Return.", [])]
    assert len(trial.state["episodes"]) == 2 and len(trial.backend.actions) == 1
    inherited = json.loads(
        (
            trial.root / "episodes/episode-002/segments/segment-001/initial_agent_context.json"
        ).read_text()
    )
    assert inherited["provenance"]["kind"] == "death_inheritance"


def test_series_reports_unscoreable_evidence_without_model_zero(tmp_path):
    from gamecua.trials import run_series

    def create(root):
        trial = make_trial(root)
        add_episode(trial, "episode-001", [("save", combat(), 1.0)])

        def run():
            completed(trial)
            (trial.root / "episodes/episode-001/0.autosave").write_bytes(b"corrupt")

        trial.run = run
        return trial

    report = run_series(tmp_path / "series", 1, create)
    assert report["trials"][0]["score"] is None
    assert report["trials"][0]["failure"] == "evidence_unscoreable"
    assert report["valid_count"] == 0


@pytest.mark.parametrize("expires", [False, True])
def test_provider_timeout_before_or_at_the_deadline(tmp_path, expires):
    from gamecua.provider import ProviderFailure

    clock, ticks = [100.0], [500.0]
    trial = make_trial(tmp_path / "trial")
    trial.budget = Budget(trial.state, 10, lambda: clock[0], lambda: ticks[0])

    class RollbackAgent(InterruptedAgent):
        calls = 0

        def decide(self, image, memory, history, stop, deadline):
            self.calls += 1
            if self.calls == 1:
                clock[0], ticks[0] = 102, 502
                return {
                    "observation": "screen",
                    "hypothesis": "guess",
                    "memory": "notes",
                    "terminal_candidate": False,
                    "action": {"type": "wait", "seconds": 0.1},
                }, {}
            elapsed = 10.002 if expires else 5.002
            clock[0], ticks[0] = 100 + elapsed, 500 + elapsed
            trial.event("provider_error", error_type="TimeoutError")
            raise ProviderFailure("Provider retry budget exhausted")

    backend = FakeBackend(trial.root)
    trial.backend, trial.agent_factory, trial.recorder = backend, RollbackAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert len(backend.actions) == 1
    assert trial.state["status"] == ("completed" if expires else "interrupted")
    assert trial.state["reason"] == ("deadline" if expires else "ProviderFailure")
    assert trial.state["eligible"] is expires
    assert trial.state["deadline"] == 110
    assert trial.state["protocol_failures"] == []
    if expires:
        assert trial.state["chargeable_seconds"] == 10
    times = [
        json.loads(line)["elapsed"]
        for line in (trial.root / "events.jsonl").read_text().splitlines()
    ]
    assert times == sorted(times)


def test_total_provider_outage_at_deadline_is_not_a_valid_zero(tmp_path):
    from gamecua.provider import ProviderFailure

    class OutageAgent(InterruptedAgent):
        def decide(self, image, memory, history, stop, deadline):
            time.sleep(0.3)
            raise ProviderFailure("Transport unavailable", "provider")

    trial = make_trial(tmp_path / "trial", seconds=0.2)
    trial.backend = FakeBackend(trial.root)
    trial.agent_factory, trial.recorder = OutageAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    result = score(trial.root)[1]
    assert result["completion_status"] == "completed"
    assert not result["comparison_eligible"]
    assert result["protocol_failures"] == [{"reason": "provider_unavailable", "scope": "trial"}]
    assert result["score"] == 0


def test_cancellation_during_provider_request_keeps_stop_reason(tmp_path):
    from gamecua.provider import ProviderFailure

    trial = make_trial(tmp_path / "trial")

    class CancelledAgent(InterruptedAgent):
        def decide(self, image, memory, history, stop, deadline):
            (trial.root / "STOP").touch()
            stop.set()
            raise ProviderFailure("Stopped")

    trial.backend = FakeBackend(trial.root)
    trial.agent_factory, trial.recorder = CancelledAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    result = score(trial.root)[1]
    assert trial.state["status"] == "cancelled"
    assert trial.state["reason"] == "stop_file"
    assert not result["comparison_eligible"]
    assert not result["manual_stop"]


def test_jev_manual_stop_is_a_completed_comparable_trial(tmp_path):
    from gamecua.provider import ProviderFailure

    trial = make_trial(tmp_path / "trial")

    class StoppedAgent(InterruptedAgent):
        def decide(self, image, memory, history, stop, deadline):
            (trial.root / "STOP").touch()
            stop.set()
            raise ProviderFailure("Stopped")

    trial.backend = FakeBackend(trial.root)
    trial.agent_factory, trial.recorder = StoppedAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    model = json.loads((trial.root / "model.json").read_text())
    (trial.root / "model.json").write_text(json.dumps(model | {"provider": "typesafe"}))
    result = score(trial.root)[1]
    assert (trial.state["status"], trial.state["reason"]) == ("cancelled", "stop_file")
    assert result["manual_stop"]
    assert result["completion_status"] == "completed"
    assert result["comparison_eligible"]
    assert result["failures"] == []


def test_signal_during_provider_request_keeps_signal_reason(tmp_path):
    from gamecua.provider import ProviderFailure

    trial = make_trial(tmp_path / "trial")

    class SignalledAgent(InterruptedAgent):
        def decide(self, image, memory, history, stop, deadline):
            stop.set()
            raise ProviderFailure("Stopped")

    trial.backend = FakeBackend(trial.root)
    trial.agent_factory, trial.recorder = SignalledAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert trial.state["status"] == "interrupted"
    assert trial.state["reason"] == "signal_interruption"
    assert trial.state["eligible"]
    assert trial.state["protocol_failures"] == []


def test_sdk_session_recovers_history_without_replaying_rejected_action(tmp_path):
    calls = []
    decision = {
        "observation": "A fixture room",
        "hypothesis": "Return may open a door",
        "memory": "",
        "terminal_candidate": False,
        "action": {"type": "press", "key": "Return"},
    }

    def create(**kwargs):
        calls.append(kwargs["messages"])
        return SimpleNamespace(
            model=kwargs["model"],
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(decision)),
                )
            ],
            usage=None,
        )

    transport = SdkShapedClient(create)

    class Agent(VisionAgent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, client=transport, **kwargs)

        def decide(self, image, memory, history, stop, deadline):
            result = super().decide(image, memory, history, stop, deadline)
            stop.set()
            return result

    trial = make_trial(tmp_path / "trial")
    backend = FakeBackend(trial.root)
    trial.backend, trial.agent_factory, trial.recorder = backend, Agent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    deadline = trial.state["deadline"]
    resumed = Trial(trial.root, backend=backend, agent_factory=Agent, recorder=FakeRecorder)
    resumed.run(install_signals=False, acquire_lease=False)
    assert resumed.state["deadline"] == deadline
    assert len(resumed.state["episodes"]) == 1
    assert len(resumed.state["episodes"][0]["segments"]) == 2
    assert len(calls[1]) > len(calls[0])
    assert "A fixture room" in json.dumps(calls[1])
    assert any(
        "rejected" in item.get("content", "")
        for item in calls[1]
        if isinstance(item.get("content"), str)
    )
    assert not backend.actions


def make_frozen_trial(root, seconds=10, step=0.2):
    spec = TrialSpec(
        id="test-frozen-trial",
        game_id="slay-the-spire",
        model_id="deepseek-flash",
        rubric_id="sts-progress-pilot",
        total_seconds=seconds,
        action_execution="frozen_steps",
        step_seconds=step,
    )
    return Trial(
        root,
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
    )


def test_frozen_steps_pause_during_decisions_and_run_one_fixed_step(tmp_path):
    log = []

    class PausableBackend(FakeBackend):
        def freeze(self):
            log.append("freeze")

        def thaw(self):
            log.append("thaw")

        def execute(self, action, **kwargs):
            log.append(("execute", action))
            super().execute(action)

    class Agent(InterruptedAgent):
        def decide(self, *args):
            log.append("decide")
            args[3].set() if log.count("decide") == 2 else None
            return {
                "observation": "screen",
                "hypothesis": "guess",
                "memory": "",
                "terminal_candidate": False,
                "action": {"type": "hold", "key": "d", "duration": 2.5},
            }, {}

    trial = make_frozen_trial(tmp_path / "trial")
    trial.backend = PausableBackend(trial.root)
    trial.agent_factory, trial.recorder = Agent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert log[:5] == [
        "freeze",
        "decide",
        "thaw",
        (
            "execute",
            {
                "type": "control",
                "keys": ["d"],
                "buttons": [],
                "dx": 0.0,
                "dy": 0.0,
                "duration": 0.2,
            },
        ),
        "freeze",
    ]
    assert log[-1] == "thaw"
    row = json.loads(next(trial.root.glob("episodes/*/segments/*/00001.json")).read_text())
    assert row["frozen_step"]["action_clamped"]
    assert row["frozen_step"]["host_seconds"] == pytest.approx(0.2, abs=0.1)
    assert "game_seconds" not in row["frozen_step"]
    prompt = (trial.root / "system_prompt.txt").read_text()
    assert "nominal 0.2 s host-time step" in prompt


@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("failure", [None, "cancel", "timeout"])
def test_render_boundary_is_charged_released_and_never_replayed(tmp_path, failure, frozen):
    log = []

    class Backend(FakeBackend):
        def freeze(self):
            log.append("freeze")

        def thaw(self):
            log.append("thaw")

        def release_all(self):
            log.append("release")

        def settle_action(self, stop, deadline):
            assert log[-1] == "release"
            assert deadline <= time.monotonic() + trial.budget.remaining() + 0.01
            log.append("settle")
            if failure == "cancel":
                stop.set()
                raise InterruptedError("cancelled")
            if failure == "timeout":
                raise RuntimeError("render timeout")
            time.sleep(0.04)
            return {"host_seconds": 0.04, "method": "synthetic"}

    class Agent(InterruptedAgent):
        def decide(self, *args):
            if trial.backend.actions:
                args[3].set()
            return {
                "observation": "screen",
                "hypothesis": "guess",
                "memory": "",
                "terminal_candidate": False,
                "action": {"type": "wait", "seconds": 0.1},
            }, {}

    trial = make_frozen_trial(tmp_path / "trial") if frozen else make_trial(tmp_path / "trial")
    trial.backend = Backend(trial.root)
    trial.agent_factory, trial.recorder = Agent, FakeRecorder
    if failure == "timeout":
        with pytest.raises(RuntimeError, match="render timeout"):
            trial.run(install_signals=False, acquire_lease=False)
    else:
        trial.run(install_signals=False, acquire_lease=False)
    if frozen:
        assert log[log.index("settle") + 1 : log.index("settle") + 3] == ["release", "freeze"]
    row = json.loads(next(trial.root.glob("episodes/*/segments/*/00001.json")).read_text())
    assert len(trial.backend.actions) == 1
    if failure:
        assert row["execution_status"] == "pending"
        assert not trial.recover(trial.state["episodes"][0])
        assert len(trial.backend.actions) == 1
    else:
        assert row["execution_status"] == "completed"
        if frozen:
            assert row["frozen_step"]["host_seconds"] >= 0.24
            assert row["frozen_step"]["render_boundary"]["method"] == "synthetic"
        else:
            assert row["action_seconds"] >= 0.04
            assert row["render_boundary"]["method"] == "synthetic"


def test_episode_limit_ends_the_trial_after_the_last_allowed_death(tmp_path):
    class DeathBackend(FakeBackend):
        def poll(self, elapsed):
            return "death"

    spec = TrialSpec(
        id="attempt-limit",
        game_id="slay-the-spire",
        model_id="deepseek-flash",
        rubric_id="sts-progress-pilot",
        total_seconds=10,
        episode_limit=2,
    )
    trial = Trial(
        tmp_path / "trial",
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
    )
    trial.backend = DeathBackend(trial.root)
    trial.agent_factory, trial.recorder = InterruptedAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    episodes = trial.state["episodes"]
    assert [e["reason"] for e in episodes] == ["death", "death"]
    assert (trial.state["status"], trial.state["reason"]) == ("completed", "episode_limit")
    notices = [
        json.loads(p.read_text())["attempt_notice"]
        for p in sorted(trial.root.glob("episodes/*/segments/*/initial_agent_context.json"))
    ]
    assert notices[0] == "Attempt 1 of 2."
    assert notices[1].startswith("A new attempt has started.")
    assert notices[1].endswith("Attempt 2 of 2.")
    _, result = score(trial.root)
    assert result["completion_status"] == "completed" and result["comparison_eligible"]


def test_episode_limit_is_omitted_when_unset():
    spec = TrialSpec(id="plain", game_id="g", rubric_id="r", total_seconds=10)
    assert "episode_limit" not in spec.model_dump(mode="json")
    with pytest.raises(ValueError):
        TrialSpec(id="zero", game_id="g", rubric_id="r", total_seconds=10, episode_limit=0)
