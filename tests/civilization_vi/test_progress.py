"""Base-development milestones come from attributed native checkpoints inside the allowance."""

import copy
import json
from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.evidence import score
from gamecua.games.civilization_vi import progress
from gamecua.storage import write_json
from gamecua.trials import Trial

CATALOG = Catalog(Path(__file__).resolve().parents[2] / "benchmarks")
RUBRIC = CATALOG.rubrics["civilization-vi-base-development-v1"]


@pytest.fixture
def state():
    return {
        "source": "official_game_read_only_tuner",
        "turn": 2,
        "native_player_id": 0,
        "team_id": 0,
        "cities": 0,
        "alive": True,
        "winning_team": -1,
        "victory_type": "NONE",
        "technologies": [],
        "city_inventory": [],
        "buildings": [],
        "districts": [],
        "units": [
            {"id": 65536, "owner": 0, "type": "UNIT_SETTLER"},
            {"id": 131073, "owner": 0, "type": "UNIT_WARRIOR"},
        ],
    }


def test_current_rubric_uses_exactly_the_native_predicates():
    assert {m.predicate for m in RUBRIC.milestones} == progress.PREDICATES
    assert len(progress.PREDICATES) == 52
    assert sum(m.points for m in RUBRIC.milestones) == 100


def test_undeveloped_start_earns_nothing(state):
    assert progress.achieved(state) == set()
    assert progress.outcome(state) is None


def test_incomplete_or_pillaged_construction_earns_nothing(state):
    state.update(cities=1, city_inventory=[{"id": 1, "owner": 0}])
    state["buildings"] = [{"city": 1, "owner": 0, "type": "BUILDING_LIBRARY", "pillaged": True}]
    state["districts"] = [
        {"city": 1, "owner": 0, "type": "DISTRICT_CAMPUS", "complete": False, "pillaged": False}
    ]
    assert progress.achieved(state) == {"base-city"}
    state["buildings"][0]["pillaged"] = False
    state["districts"][0]["complete"] = True
    assert progress.achieved(state) == {
        "base-city",
        "base-building-library",
        "base-district-campus",
    }


def test_native_outcomes(state):
    assert progress.outcome({**state, "winning_team": 0}) == "victory"
    assert progress.outcome({**state, "winning_team": 1}) == "death"
    assert progress.outcome({**state, "alive": False}) == "death"


def checkpoints(root, folder, state, samples):
    (folder / "evidence").mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (elapsed, technologies) in enumerate(samples):
        current = copy.deepcopy(state)
        current["technologies"] = technologies
        current["turn"] += index
        path = folder / f"evidence/state-{index}.json"
        write_json(path, {"episode_id": "episode", "native_state": current})
        rows.append({"kind": "save", "path": path.relative_to(root).as_posix(), "elapsed": elapsed})
    return rows


def test_endpoint_uses_original_budget_and_keeps_earlier_earnings(tmp_path, state):
    folder = tmp_path / "episodes/episode-001"
    rows = checkpoints(
        tmp_path,
        folder,
        state,
        ((10, ["TECH_MINING"]), (20, []), (10801, ["TECH_MINING", "TECH_WRITING"])),
    )
    spec = CATALOG.trials["civilization-vi-base-opus-5-5-high-live-one-life-3h"]
    result = progress.assess_endpoint(tmp_path, folder, rows, {}, spec, RUBRIC)
    assert result["complete"]
    assert result["awards"] == [
        {
            "milestone_id": "base-tech-mining",
            "points": 1,
            "first_verified_seconds": 10,
            "evidence": rows[0]["path"],
        }
    ]
    assert result["episode"]["endpoint_evidence"] == rows[1]["path"]
    assert not progress.assess_endpoint(tmp_path, folder, [], {}, spec, RUBRIC)["complete"]


def test_paper_trial_is_created_and_scored_from_preserved_checkpoints(tmp_path, state):
    spec = CATALOG.trials["civilization-vi-deepseek-flash-base-live-one-life-3h"]
    trial = Trial(
        tmp_path / "trial",
        spec=spec,
        rubric=RUBRIC,
        game=CATALOG.games[spec.game_id],
        model=CATALOG.models[spec.model_id],
        backend=object(),
        inputs=CATALOG.inputs[spec.inputs_id],
    )
    folder = trial.root / "episodes/episode-001"
    rows = checkpoints(trial.root, folder, state, ((5, ["TECH_POTTERY", "TECH_SAILING"]),))
    (folder / "evidence.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    write_json(folder / "setup.json", {"verified": True, "initial": {"native_state": state}})
    trial.state.update(
        status="completed",
        reason="deadline",
        started_at=100,
        deadline=100 + spec.total_seconds,
        elapsed_seconds=spec.total_seconds,
        chargeable_seconds=spec.total_seconds,
        episodes=[{"id": "episode-001", "segments": []}],
    )
    write_json(trial.root / "trial.json", trial.state)
    result = score(trial.root)[1]
    assert result["score"] == 3
    assert result["scoreable"]
    assert result["evaluator_version"] == progress.VERSION
