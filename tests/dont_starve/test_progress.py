"""Synthetic native observer records check the v6 rubric, never model performance."""

import copy
import json
from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.evidence import score
from gamecua.games.dont_starve.progress import COLLECTION, PREDICATES, SURVIVAL_SECONDS, facts
from gamecua.storage import sha256, write_json
from gamecua.trials import Trial

CATALOG = Catalog(Path(__file__).resolve().parents[2] / "benchmarks")
INITIAL = dict(
    schema_version=1,
    episode_id="episode-001",
    snapshot_sha256="synthetic",
    world_seed=123,
    character="wilson",
    sequence=1,
    kind="initial",
    age=1.0,
    health=150,
    cycles=0,
    phase="day",
    inventory={},
    gathered={},
    crafted={},
    built={},
    eaten={},
)


def found(initial=INITIAL, **changes):
    row = {**copy.deepcopy(initial), "sequence": 2, "kind": "sample", **changes}
    return facts("save", json.dumps([row]).encode(), initial)


def alive(seconds, cycles=0, health=150):
    return found(age=INITIAL["age"] + seconds, cycles=cycles, health=health)[0]


def test_rubric_v6_uses_one_point_for_each_native_predicate():
    rubric = CATALOG.rubrics["dont-starve-survival-collection-v6"]
    assert len(PREDICATES) == len(rubric.milestones) == 100
    assert {m.predicate for m in rubric.milestones} == PREDICATES
    assert all(m.points == 1 and not m.prerequisites for m in rubric.milestones)
    assert list(SURVIVAL_SECONDS) == list(range(48, 2401, 48))
    assert sum(len(items) for items in COLLECTION.values()) == 50


def test_survival_needs_native_age_whole_cycles_and_a_living_player():
    assert "fine_alive_48_seconds" not in alive(47.9)
    assert "fine_alive_48_seconds" in alive(48)
    assert "fine_alive_48_seconds" not in alive(48, health=0)
    assert "fine_alive_480_seconds" not in alive(480)
    assert "fine_alive_480_seconds" in alive(480, cycles=1)
    assert "fine_alive_2400_seconds" not in alive(2400, cycles=4)
    assert "fine_alive_2400_seconds" in alive(2400, cycles=5)
    assert found(initial={**INITIAL, "age": 10000.0, "cycles": 20}) == (set(), None)


def test_collection_counters_must_increase_over_the_setup_baseline():
    assert found(gathered={"cutgrass": 0})[0] == set()
    assert found(gathered={"cutgrass": 1})[0] == {"fine_gathered_cutgrass"}
    baseline = {**INITIAL, "gathered": {"twigs": 3}}
    assert found(baseline, gathered={"twigs": 3})[0] == set()
    assert found(baseline, gathered={"twigs": 4})[0] == {"fine_gathered_twigs"}
    assert found(crafted={"axe": 1}, built={"campfire": 1}, eaten={"berries_cooked": 1})[0] == {
        "fine_crafted_axe",
        "fine_built_campfire",
        "fine_eaten_berries_cooked",
    }


def test_possession_unknown_items_and_model_claims_earn_nothing():
    assert found(inventory={"axe": 1, "torch": 1}, eaten=[])[0] == set()
    assert found(gathered={"dragonfly_scale": 1})[0] == set()
    assert found(detail={"model_claim": "I crafted an axe"})[0] == set()
    assert facts("history", b"model claims", INITIAL) == (set(), None)


def test_only_a_native_death_ends_the_episode():
    assert found(kind="death", health=0, cycles=3) == (set(), "death")
    assert found(health=0, cycles=3) == (set(), None)


def trial_at(root, name="dont-starve-survival-v5-jev-live-2h"):
    spec = CATALOG.trials[name]
    return Trial(
        root,
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
        inputs=CATALOG.inputs[spec.inputs_id],
    )


def episode(trial, number, updates, died=False):
    name = f"episode-{number:03d}"
    folder = trial.root / "episodes" / name
    folder.mkdir(parents=True)
    initial = {**copy.deepcopy(INITIAL), "episode_id": name}
    write_json(folder / "setup.json", {"verified": True, "initial": initial})
    rows = [
        {**initial, **changes, "sequence": i + 2, "kind": "sample"}
        for i, changes in enumerate(updates)
    ]
    if died:
        rows.append({**rows[-1], "sequence": len(rows) + 2, "kind": "death", "health": 0})
    lines = []
    for index, row in enumerate(rows, 1):
        path = folder / f"{index}.json"
        write_json(path, [row])
        lines.append(
            {
                "kind": "save",
                "path": str(path.relative_to(trial.root)),
                "sha256": sha256(path),
                "elapsed": float(index),
            }
        )
    (folder / "evidence.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    trial.state["episodes"].append(
        {
            "id": name,
            "status": "completed",
            "reason": "death" if died else "deadline",
            "segments": [],
        }
    )


def test_canonical_scorer_awards_each_first_verified_milestone_once(tmp_path):
    trial = trial_at(tmp_path / "trial")
    episode(
        trial,
        1,
        [
            {"gathered": {"cutgrass": 1}},
            {"age": 49.0, "gathered": {"cutgrass": 2}, "crafted": {"torch": 1}},
        ],
        died=True,
    )
    trial.budget.start()
    trial.finish("completed", "death")
    result = score(trial.root)[1]
    awards = {award["milestone_id"]: award for award in result["awards"]}
    assert set(awards) == {"gathered-cutgrass", "crafted-torch", "alive-0048s"}
    assert awards["gathered-cutgrass"]["first_verified_seconds"] == 1
    assert result["score"] == 3 and result["episodes"][0]["outcome"] == "death"


@pytest.mark.parametrize(
    "name",
    [
        "dont-starve-gpt-6-astra-frozen-3h",
        "dont-starve-opus-live-0714-240s",
        "dont-starve-survival-v5-jev-frozen-2h",
    ],
)
def test_rubric_stays_out_of_the_playing_prompt(tmp_path, name):
    trial = trial_at(tmp_path / "trial", name)
    playing = (trial.root / "system_prompt.txt").read_text()
    assert trial.game.introduction not in playing
    assert all(m.description not in playing for m in trial.rubric.milestones)
