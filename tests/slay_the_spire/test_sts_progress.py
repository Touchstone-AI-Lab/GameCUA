"""Floor, boss and act predicates read from synthetic autosave mutations."""

import json
from pathlib import Path

import pytest

from gamecua.games.slay_the_spire.progress import PREDICATES, facts
from gamecua.games.slay_the_spire.saves import decode_autosave, encode_autosave
from gamecua.specs import Rubric

ROOT = Path(__file__).parents[2]
RAW = (ROOT / "tests/fixtures/slay-the-spire/IRONCLAD.autosave").read_bytes()
INITIAL = decode_autosave(RAW)


def mutated(**fields):
    return encode_autosave({**INITIAL, **fields})


@pytest.mark.parametrize(
    "path",
    [
        "benchmarks/rubrics/slay-the-spire/points-v1.json",
        "tests/fixtures/catalog/rubrics/sts-victory-v3.json",
        "tests/fixtures/catalog/rubrics/sts-progress-pilot.json",
    ],
)
def test_rubric_predicates_are_supported(path):
    rubric = Rubric.model_validate_json((ROOT / path).read_text())
    assert {m.predicate for m in rubric.milestones} <= PREDICATES


def test_baseline_awards_nothing():
    assert facts("save", RAW, INITIAL)[0] == set()


def test_floor_steps_need_a_living_player_on_that_floor():
    found = facts("save", mutated(floor_num=12, act_num=1), INITIAL)[0]
    assert {"floor_5", "floor_7", "floor_9", "floor_11"} <= found
    assert "floor_13" not in found
    assert not any(
        n.startswith("floor_")
        for n in facts("save", mutated(floor_num=30, current_health=0), INITIAL)[0]
    )


def test_skipping_elites_still_completes_act_one():
    result = facts("save", mutated(floor_num=20, act_num=2), INITIAL)[0]
    assert {"act_1_boss_reached", "act_1_complete"} <= result
    assert "elite_victory" not in result


def test_other_run_evidence_is_rejected():
    with pytest.raises(ValueError):
        facts("save", mutated(seed=1, floor_num=16), INITIAL)


def test_boss_floors_match_observed_autosaves():
    reached = facts("save", mutated(floor_num=16), INITIAL)[0]
    assert "act_1_boss_reached" in reached and "act_2_boss_reached" not in reached
    assert "act_1_boss_reached" not in facts("save", mutated(floor_num=15), INITIAL)[0]
    assert "act_2_boss_reached" in facts("save", mutated(floor_num=33, act_num=2), INITIAL)[0]
    assert (
        "act_1_boss_reached"
        not in facts("save", mutated(floor_num=16, current_health=0), INITIAL)[0]
    )


def test_history_threshold_counts_the_first_floor_of_the_next_act():
    history = {
        "seed_played": str(INITIAL["seed"]),
        "character_chosen": "IRONCLAD",
        "victory": False,
        "killed_by": "Cultist",
        "floor_reached": 17,
    }
    found = facts("history", json.dumps(history).encode(), INITIAL)[0]
    assert "act_1_complete" in found and "act_1_boss_reached" in found
    history["floor_reached"] = 16
    assert "act_1_complete" not in facts("history", json.dumps(history).encode(), INITIAL)[0]
    history["floor_reached"] = 10
    found = facts("history", json.dumps(history).encode(), INITIAL)[0]
    assert {"floor_5", "floor_9"} <= found and "floor_11" not in found
