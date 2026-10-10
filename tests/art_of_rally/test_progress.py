"""Synthetic native streams test V9 checkpoint and finish scoring, never real achievements."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from gamecua.evidence import score
from gamecua.games.art_of_rally.progress import PREDICATES, Writer, assess_endpoint
from gamecua.games.art_of_rally.route import selection
from gamecua.specs import Rubric, TrialSpec
from gamecua.storage import write_json

from .fixtures import Stream

RUBRIC = Path("benchmarks/rubrics/art-of-rally/five-stage-checkpoints-v9.json")


@pytest.fixture
def rubric():
    return Rubric.model_validate_json(RUBRIC.read_text())


def bundle(tmp_path, stream, elapsed=100):
    root = tmp_path / "run"
    folder = root / "episodes/episode-001"
    (folder / "evidence").mkdir(parents=True)
    Writer(root, folder, stream.initial).append(stream.rows[1:], elapsed)
    rows = [json.loads(line) for line in (folder / "evidence.jsonl").read_text().splitlines()]
    spec = TrialSpec(
        id="synthetic-checkpoints",
        game_id="art-of-rally",
        rubric_id="art-of-rally-five-stage-checkpoints-v9",
        total_seconds=10800,
        action_execution="live",
    )
    return root, folder, rows, spec


def assess(tmp_path, stream, rubric, elapsed=100):
    root, folder, rows, spec = bundle(tmp_path, stream, elapsed)
    return assess_endpoint(root, folder, rows, stream.initial, spec, rubric)


def test_rubric_uses_only_known_predicates(rubric):
    assert {m.predicate for m in rubric.milestones} == PREDICATES


@pytest.mark.parametrize("forward", [False, True])
def test_geometry_selection_is_directional_unique_and_independent_of_play(forward):
    stream = Stream(forward=forward)
    before = selection(stream.initial["baseline"])
    assert before == tuple(range(4, 95, 5))
    stream.recover(50)
    stream.drive(80)
    assert selection(stream.initial["baseline"]) == before


def test_selection_uses_arc_length_instead_of_waypoint_count():
    anchor = copy.deepcopy(Stream().initial["baseline"])
    geometry = json.loads(anchor["coverage"]["geometry"])
    for index, point in enumerate(geometry["points"]):
        point["x"] = 0 if index == 0 else 100 + 2 * (index - 1)
    raw = json.dumps(geometry)
    anchor["coverage"].update(geometry=raw, geometry_hash=hashlib.sha256(raw.encode()).hexdigest())
    selected = selection(anchor)
    assert selected[0] == 0
    assert len(set(selected)) == 19
    assert selected != tuple(range(4, 95, 5))


def test_recovery_skips_no_credit_but_later_checkpoints_and_finish_count(tmp_path, rubric):
    stream = Stream()
    stream.drive(20)
    stream.recover(50)
    stream.drive(100)
    stream.finish()
    result = assess(tmp_path, stream, rubric)
    keys = {a["milestone_id"] for a in result["awards"]}
    assert result["complete"]
    assert keys == {f"s1-route-{i:02d}" for i in [1, 2, 3, 4, *range(11, 20)]} | {"s1-finish"}
    finish = next(a for a in result["awards"] if a["milestone_id"] == "s1-finish")
    assert finish["native_sequences"] == [stream.rows[-1]["sequence"]]
    assert result["episode"]["outcome"] == "unknown"


def test_all_stages_have_distinct_points_and_native_victory(tmp_path, rubric):
    stream = Stream()
    stream.rally()
    result = assess(tmp_path, stream, rubric)
    assert len(result["awards"]) == 100
    assert sum(a["points"] for a in result["awards"]) == 100
    assert result["episode"]["outcome"] == "victory"


@pytest.mark.parametrize("signal", ["damage", "retirement", "reset", "restart"])
def test_first_death_stops_credit_even_if_evidence_contains_another_life(tmp_path, rubric, signal):
    stream = Stream()
    stream.drive(20)
    terminal = stream.die(signal)
    stream.start(0)
    stream.drive(100)
    stream.finish()
    result = assess(tmp_path, stream, rubric)
    assert len(result["awards"]) == 4
    assert result["episode"]["outcome"] == "death"
    assert result["episode"]["native_records_replayed"] == terminal["sequence"]


def test_finish_at_native_timer_cap_counts(tmp_path, rubric):
    stream = Stream(size=40)
    stream.drive(40)
    stream.finish(seconds=3599)
    result = assess(tmp_path, stream, rubric)
    assert "s1-finish" in {a["milestone_id"] for a in result["awards"]}


def test_foreign_gate_and_unrecorded_result_do_not_finish(tmp_path, rubric):
    stream = Stream()
    stream.drive(100)
    stream.emit("sample", source="StageTimerManager.OnStageOver", status=5)
    stream.emit("sample", source="TimingGate.OnTriggerEnter", status=5, finish_gate=True)
    result = assess(tmp_path, stream, rubric)
    assert "s1-finish" not in {a["milestone_id"] for a in result["awards"]}


def test_backward_driving_and_repeated_passes_do_not_duplicate_points(tmp_path, rubric):
    stream = Stream()
    stream.drive(20)
    stream.drive(1)
    stream.drive(20)
    assert len(assess(tmp_path, stream, rubric)["awards"]) == 4


def test_budget_cut_does_not_count_late_chunks(tmp_path, rubric):
    stream = Stream()
    stream.drive(100)
    result = assess(tmp_path, stream, rubric, elapsed=10801)
    assert not result["complete"]
    assert result["awards"] == []


def test_missing_chunks_leave_the_episode_unscored(tmp_path, rubric):
    stream = Stream()
    stream.drive(20)
    root, folder, rows, spec = bundle(tmp_path, stream)
    result = assess_endpoint(root, folder, [], stream.initial, spec, rubric)
    assert not result["complete"] and not result["awards"]
    assert result["failures"] == [{"reason": "missing_native_checkpoint_chunks"}]


def test_canonical_score_uses_the_endpoint_assessment(tmp_path, rubric):
    stream = Stream()
    stream.drive(20)
    root, folder, _, spec = bundle(tmp_path, stream)
    write_json(root / "trial.spec.json", spec.model_dump())
    write_json(root / "rubric.json", json.loads(RUBRIC.read_text()))
    write_json(root / "model.json", {"provider": "openai_compatible"})
    write_json(
        root / "trial.json",
        {
            "schema_version": 1,
            "id": "synthetic-native-checkpoints",
            "status": "completed",
            "reason": "deadline",
            "started_at": 1.0,
            "elapsed_seconds": 10800.0,
            "chargeable_seconds": 10800.0,
            "episodes": [{"id": "episode-001", "reason": "deadline"}],
        },
    )
    write_json(folder / "setup.json", {"verified": True, "initial": stream.initial})
    _, result = score(root)
    assert result["score"] == 4
    assert result["comparison_eligible"]
