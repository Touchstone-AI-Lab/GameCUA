"""Synthetic route panel scoring and native fixture checks, never benchmark results."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gamecua.catalog import Catalog
from gamecua.games.understand import progress
from gamecua.games.understand.native import GROUP_PANELS
from gamecua.games.understand.progress import SPINE, assess_endpoint, evaluate_history, facts

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/understand"
ZERO = (FIXTURES / "zero-progress.sav").read_bytes()
INITIAL = {"active_slot": 1}


@pytest.fixture(scope="module")
def rubric():
    return Catalog(ROOT / "benchmarks").rubrics["understand-route-panels-v4"]


class PathChecker:
    metadata = {"test_only": True}

    def evaluate(self, group, states):
        results = []
        for state in states:
            paths = state["lines"][group]
            passed = [len(path or []) == 2 for path in paths]
            passed.extend([False] * (GROUP_PANELS[group] - len(passed)))
            results.append({"id": state["id"], "passed": passed})
        return results


def saved(cleared=(), submitted=None, slot=1):
    data = json.loads(ZERO)
    if not data[slot]:
        data[slot] = json.loads(ZERO)[1]
    data[slot][0] = list(cleared)
    data[slot][3] = submitted or {}
    return json.dumps(data).encode()


def assess(tmp_path, rubric, checkpoints):
    folder = tmp_path / "episodes/episode-001"
    (folder / "evidence").mkdir(parents=True)
    rows = []
    for index, (elapsed, raw) in enumerate(checkpoints):
        path = folder / f"evidence/{index}.save"
        path.write_bytes(raw)
        rows.append(
            {
                "kind": "save",
                "path": str(path.relative_to(tmp_path)),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "elapsed": elapsed,
            }
        )
    spec = SimpleNamespace(total_seconds=10800)
    return assess_endpoint(tmp_path, folder, rows, INITIAL, spec, rubric), rows


def test_catalog_and_full_native_route_award_exactly_one_point_per_panel(tmp_path, rubric):
    expected = {
        f"panel-{group}-{panel}"
        for group, count in GROUP_PANELS.items()
        for panel in range(1, count + 1)
    }
    assert rubric.version == 4 and rubric.assessment == "endpoint"
    assert {milestone.id for milestone in rubric.milestones} == expected == progress.PREDICATES
    assert all(m.points == 1 and m.predicate == m.id for m in rubric.milestones)
    review, _ = assess(tmp_path, rubric, [(60, saved([*GROUP_PANELS, "1-5", "EX-10", "END"]))])
    assert review["complete"] and review["failures"] == []
    assert {award["milestone_id"] for award in review["awards"]} == expected
    assert len(review["awards"]) == 100


def test_earliest_verified_late_paths_survive_retries_and_a_later_reveal(
    tmp_path, rubric, monkeypatch
):
    monkeypatch.setattr(progress, "NativePanels", PathChecker)
    rejected = [{"x": 1, "y": 1}]
    accepted = [*rejected, {"x": 2, "y": 1}]
    path_3_1 = [None] * 6 + [accepted, rejected]
    review, rows = assess(
        tmp_path,
        rubric,
        [
            (7198, saved([], {"3-1": path_3_1, "4-1": [None] * 7 + [rejected]})),
            (7200, saved([], {"3-1": path_3_1, "4-1": [None] * 7 + [accepted]})),
            (7201, saved(["3-1"])),
        ],
    )
    assert review["complete"] and review["failures"] == []
    awards = {award["milestone_id"]: award for award in review["awards"]}
    assert len(review["awards"]) == len(awards) == 9
    assert review["episode"]["points_at_2h"] == 2
    first_path = awards["panel-3-1-7"]
    assert first_path["proof_method"] == "native-submitted-path"
    assert first_path["first_verified_seconds"] == 7198
    assert first_path["evidence"] == rows[0]["path"]
    assert first_path["evidence_sha256"] == rows[0]["sha256"]
    reveal = awards["panel-3-1-8"]
    assert reveal["proof_method"] == "native-group-reveal"
    assert reveal["first_verified_seconds"] == 7201
    last_path = awards["panel-4-1-8"]
    assert last_path["first_verified_seconds"] == 7200
    assert last_path["evidence_sha256"] == rows[1]["sha256"]


def test_endpoint_counts_deadline_evidence_and_ignores_later_progress(tmp_path, rubric):
    review, _ = assess(tmp_path, rubric, [(10800, saved(["2-9"])), (10800.01, saved(["4-1"]))])
    assert review["complete"]
    assert {award["milestone_id"] for award in review["awards"]} == {
        f"panel-2-9-{panel}" for panel in range(1, 9)
    }
    assert review["episode"]["points_at_2h"] == 0


def test_no_in_budget_save_is_an_incomplete_assessment(tmp_path, rubric):
    review, _ = assess(tmp_path, rubric, [(10800.01, saved(["4-1"]))])
    assert not review["complete"] and review["awards"] == []
    assert review["failures"] == [{"reason": "missing_native_history"}]


def test_other_slots_do_not_pool_and_model_claims_are_ignored(tmp_path, rubric):
    review, rows = assess(tmp_path, rubric, [(1, saved(SPINE, slot=2))])
    assert review["awards"] == []
    assert facts("history", b"model claims victory", INITIAL) == (set(), None)


def test_missing_runtime_is_unresolved_instead_of_silently_zero():
    def unavailable():
        raise ValueError("missing licensed runtime")

    snapshot = ({"elapsed": 1, "path": "1.save", "sha256": "0"}, set(), {"1-1": [[{"x": 1}]]})
    review = evaluate_history([snapshot], unavailable)
    assert not review["complete"]
    assert review["failures"][0]["reason"] == "native_panel_assessment_unavailable"


def test_native_ending_needs_the_complete_spine_in_the_active_slot():
    assert facts("save", saved(SPINE), INITIAL) == (set(), "victory")
    assert facts("save", saved(SPINE[:-1]), INITIAL) == (set(), None)
    assert facts("save", saved(["EX-10", "END"]), INITIAL) == (set(), None)
    assert facts("save", saved(SPINE, slot=2), INITIAL) == (set(), None)
    for name in ("invalid-line.sav", "one-panel.sav", "completed-group.sav"):
        assert facts("save", (FIXTURES / name).read_bytes(), INITIAL) == (set(), None)


def test_native_fixture_provenance_and_hashes():
    origin = json.loads((FIXTURES / "origin.json").read_text())
    assert origin["autonomous_game_actions"] == 0
    for name, checksum in origin["files_sha256"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == checksum
