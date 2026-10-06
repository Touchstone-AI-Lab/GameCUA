"""Offline tests for Stardew Valley save parsing and milestone predicates on synthetic saves."""

from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.games.stardew_valley.progress import PLACES, PREDICATES, facts
from gamecua.games.stardew_valley.saves import read_save
from gamecua.specs import Rubric

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = {
    0: ("Pantry/0", "Spring Crops/O 465 20/24 1 0 188 1 0 190 1 0 192 1 0/0///Spring Crops", 4),
    13: (
        "Crafts Room/13",
        "Spring Foraging/O 495 30/16 1 0 18 1 0 20 1 0 22 1 0/0///Spring Foraging",
        4,
    ),
    17: (
        "Crafts Room/17",
        "Construction/BO 114 1/388 99 0 388 99 0 390 99 0 709 10 0/1///Construction",
        4,
    ),
    22: (
        "Boiler Room/22",
        "Adventurer's/R 518 1/766 99 0 767 10 0 768 1 0 769 1 0/1/2//Adventurer's",
        4,
    ),
    23: ("Vault/23", "2,500g/O 220 3/-1 2500 2500/4///2,500g", 1),
}


def synthetic_save(
    game_id="123456789",
    year=1,
    season="spring",
    day=1,
    money=500,
    earned=0,
    mine=0,
    max_items=12,
    farming=0,
    mail=(),
    shipped=(),
    crops=0,
    fish=(),
    tool_levels=(0, 0, 0, 0),
    donated=None,
    hoed=0,
    sown=0,
    farming_xp=0,
    friends=None,
    copper=0,
    casts=0,
    furnaces=0,
    areas=(),
    visited=(),
    stats=None,
    skills=None,
    minerals=(),
    artifacts=(),
    museum=0,
    crafted=None,
):
    donated = donated or {}
    skills = {"farming": farming, **(skills or {})}
    visited_xml = "".join(f"<string>{place}</string>" for place in visited)
    found_xml = {
        name: "".join(
            f"<item><key><string>{key}</string></key><value><int>1</int></value></item>"
            for key in keys
        )
        for name, keys in (("minerals", minerals), ("artifacts", artifacts))
    }
    museum_xml = "".join(
        f"<item><key><Vector2><X>{n}</X><Y>1</Y></Vector2></key><value><string>{n}</string></value></item>"
        for n in range(museum)
    )
    friends = {"Lewis": 0, "Robin": 0} if friends is None else friends
    mail_xml = "".join(f"<string>{m}</string>" for m in mail)
    shipped_xml = "".join(
        f"<item><key><string>{s}</string></key><value><int>1</int></value></item>" for s in shipped
    )
    fish_xml = "".join(
        f"<item><key><string>{f}</string></key><value><ArrayOfInt><int>1</int><int>5</int></ArrayOfInt></value></item>"
        for f in fish
    )
    tools_xml = "".join(
        f'<Item xsi:type="{kind}"><name>{kind}</name><upgradeLevel>{level}</upgradeLevel></Item>'
        for kind, level in zip(("Axe", "Hoe", "Pickaxe", "WateringCan"), tool_levels)
    )
    values = "".join(
        f"<item><key><string>{key}</string></key><value><unsignedInt>{count}</unsignedInt></value></item>"
        for key, count in (
            ("cropsShipped", crops),
            ("dirtHoed", hoed),
            ("seedsSown", sown),
            ("copperFound", copper),
            ("timesFished", casts),
            *(stats or {}).items(),
        )
        if count
    )
    experience_xml = "".join(f"<int>{xp}</int>" for xp in (farming_xp, 0, 0, 0, 0, 0))
    recipes_xml = "".join(
        f"<item><key><string>{name}</string></key><value><int>{count}</int></value></item>"
        for name, count in (("Chest", 0), ("Furnace", furnaces), *(crafted or {}).items())
    )
    friends_xml = "".join(
        f"<item><key><string>{name}</string></key><value><Friendship><Points>{points}</Points></Friendship></value></item>"
        for name, points in friends.items()
    )
    bundle_data = "".join(
        f"<item><key><string>{key}</string></key><value><string>{value}</string></value></item>"
        for key, value, _ in BUNDLES.values()
    )
    bundle_state = "".join(
        f"<item><key><int>{index}</int></key><value><ArrayOfBoolean>"
        + "".join(
            f"<boolean>{'true' if donated.get(index) == 'all' or slot < (donated.get(index) or 0) else 'false'}</boolean>"
            for slot in range(count * 3)
        )
        + "</ArrayOfBoolean></value></item>"
        for index, (_, _, count) in BUNDLES.items()
    )
    areas_xml = "".join(
        f"<boolean>{'true' if index in areas else 'false'}</boolean>" for index in range(6)
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<SaveGame xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <player>
    <name>Farmer</name>
    <items>{tools_xml}</items>
    <money>{money}</money>
    <totalMoneyEarned>{earned}</totalMoneyEarned>
    <deepestMineLevel>{mine}</deepestMineLevel>
    <maxItems>{max_items}</maxItems>
    <houseUpgradeLevel>0</houseUpgradeLevel>
    <farmingLevel>{skills["farming"]}</farmingLevel>
    <fishingLevel>{skills.get("fishing", 0)}</fishingLevel>
    <foragingLevel>{skills.get("foraging", 0)}</foragingLevel>
    <miningLevel>{skills.get("mining", 0)}</miningLevel>
    <combatLevel>{skills.get("combat", 0)}</combatLevel>
    <experiencePoints>{experience_xml}</experiencePoints>
    <friendshipData>{friends_xml}</friendshipData>
    <craftingRecipes>{recipes_xml}</craftingRecipes>
    <mailReceived>{mail_xml}</mailReceived>
    <basicShipped>{shipped_xml}</basicShipped>
    <fishCaught>{fish_xml}</fishCaught>
    <locationsVisited>{visited_xml}</locationsVisited>
    <mineralsFound>{found_xml["minerals"]}</mineralsFound>
    <archaeologyFound>{found_xml["artifacts"]}</archaeologyFound>
    <stats><Values>{values}</Values><cropsShipped xsi:nil="true" /></stats>
  </player>
  <locations>
    <GameLocation><name>Farm</name></GameLocation>
    <GameLocation xsi:type="LibraryMuseum"><name>ArchaeologyHouse</name><museumPieces>{museum_xml}</museumPieces></GameLocation>
    <GameLocation xsi:type="CommunityCenter"><name>CommunityCenter</name><bundles>{bundle_state}</bundles><areasComplete>{areas_xml}</areasComplete></GameLocation>
  </locations>
  <currentSeason>{season}</currentSeason>
  <dayOfMonth>{day}</dayOfMonth>
  <year>{year}</year>
  <uniqueIDForThisGame>{game_id}</uniqueIDForThisGame>
  <bundleData>{bundle_data}</bundleData>
</SaveGame>""".encode()


def test_reads_progress_fields():
    data = read_save(
        synthetic_save(
            season="summer",
            day=3,
            earned=40,
            shipped=["24"],
            crops=2,
            fish=["(O)145", "(O)142"],
            tool_levels=(1, 0, 0, 0),
            donated={13: "all", 22: "all", 0: 3},
            hoed=7,
            sown=4,
            farming_xp=16,
            friends={"Lewis": 20, "Pierre": -2},
            copper=12,
            casts=3,
            furnaces=1,
            areas=(2,),
        )
    )
    assert data["totalMoneyEarned"] == 40 and data["items_shipped"] == ["24"]
    assert data["crops_shipped"] == 2
    assert data["fish_species"] == ["(O)142", "(O)145"]
    assert data["tool_level"] == 1
    assert data["bundles_complete"] == [13, 22]
    assert data["areas_complete"] == [2]
    assert (data["dirt_hoed"], data["seeds_sown"], data["farming_experience"]) == (7, 4, 16)
    assert data["friendship_points"] == {"Lewis": 20, "Pierre": -2}
    assert (data["copper_found"], data["times_fished"], data["furnaces_crafted"]) == (12, 3, 1)


def test_initial_save_and_passing_days_earn_nothing():
    initial = read_save(synthetic_save(day=2))
    assert facts("save", synthetic_save(day=2), initial) == (set(), None)
    assert facts("save", synthetic_save(day=9, money=450), initial) == (set(), None)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"earned": 499}, {"first_income", "earned_250"}),
        ({"earned": 2500}, {"first_income"} | {f"earned_{n}" for n in (250, 500, 1000, 2500)}),
        ({"mine": 1}, {"mine_level_1"}),
        ({"mine": 29}, {f"mine_level_{n}" for n in (1, 5, 10, 15, 20)}),
        ({"copper": 1}, {"copper_ore_found"}),
        ({"furnaces": 1}, {"furnace_crafted", "crafted_recipes_1"}),
        ({"casts": 1}, {"first_cast"}),
        ({"mail": ["seenJunimoNote"]}, {"junimo_scroll_seen"}),
        ({"mail": ["canReadJunimoText"]}, {"junimo_text_readable"}),
        ({"mail": ["ccDoorUnlock"]}, {"cc_door_unlocked"}),
        ({"fish": ["(O)1"]}, {"first_fish"}),
        (
            {"fish": [f"(O){n}" for n in range(5)]},
            {"first_fish", "fish_5_species", "fish_species_2", "fish_species_3"},
        ),
        ({"hoed": 1}, {"soil_tilled"}),
        ({"sown": 49}, {"seeds_sown", "seeds_sown_20"}),
        ({"farming_xp": 8}, {"crop_harvested"}),
        ({"crops": 15}, {"crop_shipped", "crops_shipped_15"}),
        ({"donated": {0: 3, 22: 1}}, set()),
        ({"donated": {22: 2}}, {"first_bundle"}),
        ({"donated": {23: 1}}, {"first_bundle"}),
        ({"donated": {13: "all", 17: "all", 22: "all"}}, {"first_bundle", "three_bundles"}),
        ({"tool_levels": (0, 0, 2, 0)}, {"copper_tool"}),
        ({"max_items": 24}, {"backpack_upgraded"}),
        ({"areas": (0, 1, 4)}, {"first_room"}),
        ({"visited": ["Town", "Mine", "Temp"]}, {"visited_town"}),
        ({"skills": {"mining": 2}}, {"mining_level_1", "mining_level_2"}),
        ({"stats": {"questsCompleted": 4}}, {"quests_completed_1", "quests_completed_3"}),
        ({"stats": {"itemsForaged": 9}}, {"items_foraged_1"}),
        ({"stats": {"monstersKilled": 9, "giftsGiven": 1}}, {"monsters_killed_1", "gifts_given_1"}),
        ({"shipped": ["16", "18", "20", "22"]}, {"shipped_items_3"}),
        (
            {"minerals": ["60", "62", "64"], "artifacts": ["96"]},
            {"minerals_1", "minerals_3", "artifacts_1"},
        ),
        ({"museum": 4}, {"museum_donations_1", "museum_donations_3"}),
        ({"crafted": {"Torch": 1, "Scarecrow": 2, "Chest": 0}}, {"crafted_recipes_1"}),
        (
            {"friends": {"Lewis": 249, "Robin": 0, "Pierre": 0, "Willy": 0, "Clint": 0}},
            {"villagers_met_3"},
        ),
        ({"friends": {"Lewis": 250, "Robin": 499}}, {"friend_1_heart"}),
        (
            {"friends": {"Lewis": 500, "Robin": 250, "Pierre": 250}},
            {"friend_1_heart", "friend_2_hearts", "friends_3_at_1_heart"},
        ),
    ],
)
def test_thresholds(kwargs, expected):
    initial = read_save(synthetic_save(day=2))
    assert facts("save", synthetic_save(day=3, **kwargs), initial)[0] == expected


def test_purchased_vault_bundle_counts_like_the_game():
    data = read_save(synthetic_save(donated={23: 1, 0: 3}))
    assert data["bundles_complete"] == [23]


def test_rooms_restored_before_setup_are_not_awarded_again():
    initial = read_save(synthetic_save(day=2, areas=(0, 1, 2)))
    assert facts("save", synthetic_save(day=5, areas=(0, 1, 2, 3)), initial)[0] == {"first_room"}
    assert facts("save", synthetic_save(day=5, areas=(0, 1, 2)), initial)[0] == set()


@pytest.mark.parametrize(
    "start, later",
    [
        ({"tool_levels": (1, 0, 0, 0)}, {"tool_levels": (2, 0, 0, 0)}),
        ({"tool_levels": (1, 0, 0, 0)}, {"tool_levels": (1, 1, 0, 0)}),
        ({"max_items": 24}, {"max_items": 36}),
    ],
    ids=["copper-to-steel", "second-copper-tool", "second-backpack"],
)
def test_first_tier_milestones_are_not_awarded_for_later_tiers(start, later):
    initial = read_save(synthetic_save(day=2, **start))
    assert facts("save", synthetic_save(day=5, **later), initial)[0] == set()


EARLY_GAME = ROOT / "benchmarks/rubrics/stardew-valley/early-game-v1.json"
EVERYTHING = dict(
    earned=5000,
    mine=40,
    max_items=24,
    farming=3,
    mail=["ccDoorUnlock", "seenJunimoNote", "wizardJunimoNote", "canReadJunimoText"],
    crops=15,
    fish=[f"(O){n}" for n in range(130, 138)],
    shipped=[str(n) for n in range(20)],
    tool_levels=(1, 0, 0, 0),
    donated={13: "all", 17: "all", 22: "all"},
    hoed=1,
    sown=50,
    farming_xp=10,
    friends={
        "Lewis": 500,
        "Robin": 250,
        "Pierre": 250,
        **{f"Villager{n}": 0 for n in range(20)},
    },
    copper=1,
    casts=1,
    furnaces=1,
    areas=(1,),
    visited=list(PLACES.values()),
    stats={
        "questsCompleted": 5,
        "itemsForaged": 30,
        "monstersKilled": 10,
        "giftsGiven": 5,
    },
    skills={"fishing": 3, "foraging": 3, "mining": 3, "combat": 3},
    minerals=["60", "62", "64", "66", "68"],
    artifacts=["96", "97"],
    museum=5,
    crafted={"Torch": 1, "Scarecrow": 1, "Wood Path": 1, "Basic Fertilizer": 1},
)


def early_game():
    return Rubric.model_validate_json(EARLY_GAME.read_text())


def test_early_game_rubric_has_100_one_point_milestones():
    rubric = early_game()
    assert len(rubric.milestones) == 100
    assert {m.points for m in rubric.milestones} == {1}
    assert {m.predicate for m in rubric.milestones} == PREDICATES


def test_one_save_can_reach_every_early_game_milestone():
    initial = read_save(synthetic_save(day=2))
    found = facts("save", synthetic_save(day=14, **EVERYTHING), initial)[0]
    assert found == PREDICATES


def test_progress_before_setup_is_not_awarded_again():
    existing = {
        key: value for key, value in EVERYTHING.items() if key not in ("mail", "donated", "areas")
    }
    initial = read_save(synthetic_save(day=2, **existing))
    assert facts("save", synthetic_save(day=5, **existing), initial)[0] == set()
    later = synthetic_save(day=5, **{**existing, "fish": [*existing["fish"], "(O)1"]})
    assert facts("save", later, initial)[0] == {"first_fish"}


def test_a_baseline_recorded_before_the_finer_fields_counts_them_from_zero():
    initial = read_save(synthetic_save(day=2))
    for name in (
        "locations_visited",
        "minerals_found",
        "artifacts_found",
        "museum_pieces",
        "quests_completed",
        "monsters_killed",
        "items_foraged",
        "gifts_given",
        "crafted_recipes",
    ):
        initial.pop(name)
    later = synthetic_save(day=3, visited=["Town"], museum=1, stats={"questsCompleted": 1})
    assert facts("save", later, initial)[0] == {
        "visited_town",
        "museum_donations_1",
        "quests_completed_1",
    }


def test_every_trial_uses_the_early_game_rubric():
    catalog = Catalog(ROOT / "benchmarks")
    trials = [t for t in catalog.trials.values() if t.game_id == "stardew-valley"]
    assert len(trials) == 12
    for spec in trials:
        assert spec.rubric_id == "stardew-early-game-v1"
        jev = spec.model_id == "jev-1-14"
        assert spec.total_seconds == (3600 if jev else 10800)
