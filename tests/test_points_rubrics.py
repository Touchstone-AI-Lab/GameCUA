import importlib
import json
from pathlib import Path

import pytest

from gamecua.games.slay_the_spire.saves import encode_autosave
from gamecua.specs import Rubric

ROOT = Path(__file__).resolve().parents[1]
RUBRICS = {
    "slay_the_spire": ("slay-the-spire", "points-v1"),
    "left_4_dead_2": ("left-4-dead-2", "points-v1"),
}


def load(game):
    folder, name = RUBRICS[game]
    rubric = Rubric.model_validate_json(
        (ROOT / "benchmarks" / "rubrics" / folder / f"{name}.json").read_text()
    )
    progress = importlib.import_module(f"gamecua.games.{game}.progress")
    return rubric, progress


@pytest.mark.parametrize("game", RUBRICS)
def test_points_rubric_has_two_groups_of_scoring_points(game):
    rubric, progress = load(game)
    assert len(rubric.milestones) > 50
    assert {m.predicate for m in rubric.milestones} <= progress.PREDICATES
    assert len({m.predicate for m in rubric.milestones}) == len(rubric.milestones)
    assert sum(m.points for m in rubric.milestones) == 100


STS_INITIAL = {
    "seed": "7",
    "floor_num": 1,
    "act_num": 1,
    "monsters_killed": 1,
    "gold_gained": 0,
    "metric_damage_taken": [],
}


def sts_save(**changes):
    state = {
        **STS_INITIAL,
        "current_health": 60,
        "max_health": 80,
        "post_combat": False,
        "current_room": "com.megacrit.cardcrawl.rooms.MonsterRoom",
        "relics": ["Burning Blood"],
        "cards": [{"id": "Strike_R", "upgrades": 0, "misc": 0}] * 11,
        **changes,
    }
    return encode_autosave(state)


def test_sts_collection_points_come_from_the_autosave():
    _, progress = load("slay_the_spire")
    found, _ = progress.facts("save", sts_save(), STS_INITIAL)
    assert not {f for f in found if f.startswith(("relics_", "deck_", "upgrades_"))}
    cards = [{"id": "Offering", "upgrades": 1, "misc": 0}] * 4 + [
        {"id": "Inflame", "upgrades": 0, "misc": 0}
    ] * 10
    found, _ = progress.facts(
        "save",
        sts_save(
            floor_num=8,
            cards=cards,
            relics=["Burning Blood", "Anchor", "Vajra"],
            gold_gained=320,
            max_health=91,
            monsters_killed=12,
            metric_potions_obtained=[{"floor": 2, "key": "Fire Potion"}],
            metric_campfire_choices=[{"floor": 6, "key": "REST"}, {"floor": 9, "key": "SMITH"}],
            metric_items_purged=["Strike_R"],
            metric_damage_taken=[{"damage": 0, "enemies": "Cultist", "floor": 2}],
        ),
        STS_INITIAL,
    )
    assert {
        "depth_8",
        "relics_3",
        "gold_gained_300",
        "max_hp_90",
        "deck_13",
        "upgrades_1",
        "rare_card",
        "uncommon_card",
        "potions_1",
        "rested",
        "smithed",
        "card_removed",
        "kills_10",
        "flawless_combat",
    } <= found
    assert "relics_4" not in found and "upgrades_5" not in found


def test_sts_history_maps_the_same_collection_facts():
    _, progress = load("slay_the_spire")
    history = {
        "seed_played": "7",
        "character_chosen": "IRONCLAD",
        "victory": False,
        "killed_by": "Gremlin Nob",
        "floor_reached": 9,
        "master_deck": ["Strike_R", "Bash+1", "Offering", "Inflame"] * 4,
        "relics": ["Burning Blood", "Anchor"],
        "gold_per_floor": [99, 120, 100, 160],
        "max_hp_per_floor": [80, 80, 86],
        "potions_obtained": [{"floor": 3, "key": "Fire Potion"}],
        "campfire_choices": [{"floor": 6, "key": "SMITH"}],
        "damage_taken": [],
    }
    found, outcome = progress.facts("history", json.dumps(history).encode(), STS_INITIAL)
    assert outcome == "death"
    assert {"relics_2", "max_hp_85", "deck_16", "upgrades_1", "rare_card", "smithed"} <= found


L4D2_INITIAL = {
    "session": "s",
    "x": 518.0,
    "y": 5631.93,
    "z": 2849.72,
    "time": 40.0,
    "kills": 0,
    "specials": 0,
    "heals": 0,
    "revives": 0,
}


def l4d2_row(kind="sample", **changes):
    return {
        "schema": 1,
        "session": "s",
        "map": "c1m1_hotel",
        "mode": "coop",
        "difficulty": "Easy",
        "cheats": 0,
        "human_alive": True,
        "kind": kind,
        "time": 40.0,
        "x": 518.0,
        "y": 5631.93,
        "z": 2849.72,
        "kills": 0,
        "specials": 0,
        "heals": 0,
        "revives": 0,
        "shots": 0,
        **changes,
    }


def test_l4d2_counter_and_survival_points():
    _, progress = load("left_4_dead_2")
    rows = [
        l4d2_row(),
        l4d2_row(time=40 + 6 * 60, kills=40, specials=3, heals=1, shots=130),
    ]
    found, outcome = progress.facts(
        "history", json.dumps(rows).encode(), {**L4D2_INITIAL, "shots": 0}
    )
    assert outcome is None
    assert {"kills_35", "specials_3", "heals_1", "shots_100", "survive_5"} <= found
    assert not {"kills_50", "specials_5", "survive_10", "chapter_complete"} & found


def test_l4d2_counters_after_death_do_not_count():
    _, progress = load("left_4_dead_2")
    rows = [
        l4d2_row(kills=12),
        l4d2_row(kind="human_death", human_alive=False, time=400, kills=80),
    ]
    found, outcome = progress.facts(
        "history", json.dumps(rows).encode(), {**L4D2_INITIAL, "shots": 0}
    )
    assert outcome == "death"
    assert "kills_10" in found and "kills_50" not in found and "survive_5" not in found
