"""Development v7 criteria boundaries and canonical endpoint scoring on synthetic states."""

import copy
import json
from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.evidence import score
from gamecua.games.oxygen_not_included import progress
from gamecua.games.oxygen_not_included.progress import BASIC_TECHNOLOGIES, evaluate
from gamecua.storage import write_json
from gamecua.trials import Trial

CATALOG = Catalog(Path(__file__).resolve().parents[2] / "benchmarks")
RUBRIC = CATALOG.rubrics["oni-development-v7"]
ADVANCED = ["Acoustics", "Agriculture", "AnimalControl"]


def state():
    """Return an empty decoded save state."""
    return {
        "native": {"cycle": 0, "groups": {}, "population": {"living": 3, "dead": 0}},
        "metrics": {
            "completed_technologies": [],
            "production_by_day": {"1": dict(energy_j=0.0, oxygen_kg=0.0, calories=0.0)},
            "manufactured_calories_by_day": {},
        },
        "extended": {
            "objects": {},
            "stock_kg": dict(refined_metal=0, plastic=0, steel=0),
            "pipe_water_kg": 0,
            "consumed_j_by_day": {"1": 0},
        },
        "generation": {},
    }


def complete_state():
    """Return a state that meets every v7 criterion from an empty start."""
    current = state()
    groups = current["native"]["groups"]
    for prefabs in progress.BUILDINGS.values():
        groups[prefabs[0]] = 1
    for requirements in progress.FACILITIES.values():
        groups.update(requirements)
    groups.update(LiquidReservoir=1, CookingStation=1, RockCrusher=1, HydroponicFarm=6)
    current["generation"] = {"Generator": 100000}
    current["metrics"]["completed_technologies"] = ADVANCED + sorted(BASIC_TECHNOLOGIES)[:5]
    current["metrics"]["production_by_day"]["1"] = dict(
        energy_j=100000, oxygen_kg=20, calories=1000000
    )
    current["metrics"]["manufactured_calories_by_day"] = {"1": 4000000}
    extra = current["extended"]
    extra.update(pipe_water_kg=100, consumed_j_by_day={"1": 1000})
    extra["stock_kg"] = dict(refined_metal=200, steel=100, plastic=100)
    extra["objects"] = {
        "1": {"prefab": "BatterySmart", "joules": 10000},
        "2": {"prefab": "BatterySmart", "joules": 10000},
        **{str(i): {"prefab": "PrickleFlower", "planted": True} for i in range(3, 9)},
        **{str(i): {"prefab": "BasicSingleHarvestPlant", "planted": True} for i in range(9, 12)},
    }
    return current


def test_rubric_uses_exactly_the_implemented_predicates():
    assert len(RUBRIC.milestones) == 50
    assert all(m.points == 2 and not m.prerequisites for m in RUBRIC.milestones)
    assert {m.predicate for m in RUBRIC.milestones} == progress.PREDICATES
    assert RUBRIC.assessment == "endpoint"


def test_complete_state_meets_every_criterion():
    found, unresolved = evaluate(complete_state(), state())
    assert {"replacement_" + key for key in found} == progress.PREDICATES
    assert unresolved == {}
    assert evaluate(state(), state()) == (set(), {})


@pytest.mark.parametrize("key,prefabs", progress.BUILDINGS.items())
def test_initial_buildings_and_blueprints_do_not_count(key, prefabs):
    start = state()
    start["native"]["groups"][prefabs[0]] = 1
    current = copy.deepcopy(start)
    current["native"]["groups"][prefabs[0] + "UnderConstruction"] = 1
    assert key not in evaluate(current, start)[0]
    current["native"]["groups"][prefabs[0]] = 2
    assert key in evaluate(current, start)[0]


@pytest.mark.parametrize("key,requirements", progress.FACILITIES.items())
def test_every_facility_part_is_required_and_initial_parts_do_not_count(key, requirements):
    initial, current = state(), complete_state()
    for prefab, count in requirements.items():
        missing = copy.deepcopy(current)
        missing["native"]["groups"][prefab] = count - 1
        assert key not in evaluate(missing, initial)[0]
        existing = copy.deepcopy(initial)
        existing["native"]["groups"][prefab] = 1
        assert key not in evaluate(current, existing)[0]


@pytest.mark.parametrize(
    "resource,key,minimum",
    [
        ("steel", "steel_inventory", 100),
        ("plastic", "plastic_inventory", 100),
        ("refined_metal", "metal_workshop", 200),
        ("refined_metal", "refined_stock", 100),
    ],
)
def test_resource_thresholds_subtract_the_start(resource, key, minimum):
    initial, current = state(), complete_state()
    initial["extended"]["stock_kg"][resource] = 20
    current["extended"]["stock_kg"][resource] = 20 + minimum - 0.5
    assert key not in evaluate(current, initial)[0]
    current["extended"]["stock_kg"][resource] += 0.5
    assert key in evaluate(current, initial)[0]


@pytest.mark.parametrize(
    "metric,key,minimum",
    [
        ("energy_j", "power_produced", 10000),
        ("oxygen_kg", "oxygen_produced", 20),
        ("calories", "food_produced", 1000000),
    ],
)
def test_production_thresholds_subtract_the_start(metric, key, minimum):
    initial, current = state(), state()
    initial["metrics"]["production_by_day"]["1"][metric] = 5
    current["metrics"]["production_by_day"]["1"][metric] = 5 + minimum - 1
    assert key not in evaluate(current, initial)[0]
    current["metrics"]["production_by_day"]["2"] = dict(energy_j=0, oxygen_kg=0, calories=0)
    current["metrics"]["production_by_day"]["2"][metric] = 1
    assert key in evaluate(current, initial)[0]


def test_water_requires_a_pump_or_reservoir_and_net_pipe_mass():
    initial, current = state(), complete_state()
    initial["extended"]["pipe_water_kg"] = 1
    assert "water_storage_infrastructure" not in evaluate(current, initial)[0]
    current["extended"]["pipe_water_kg"] = 101
    assert "water_storage_infrastructure" in evaluate(current, initial)[0]
    current["native"]["groups"].update(LiquidReservoir=0, LiquidPump=0)
    found = evaluate(current, initial)[0]
    assert not {"water_storage_infrastructure", "water_in_pipes"} & found


def test_cooking_excludes_initial_manufacturing_and_raw_food():
    initial, current = state(), complete_state()
    initial["metrics"]["manufactured_calories_by_day"] = {"1": 1}
    assert "cooking_capacity" not in evaluate(current, initial)[0]
    current["metrics"]["manufactured_calories_by_day"]["1"] += 1
    assert {"cooking_capacity", "manufactured_food"} <= evaluate(current, initial)[0]
    current["metrics"]["manufactured_calories_by_day"] = {}
    current["metrics"]["production_by_day"]["1"]["calories"] = 100000000
    found = evaluate(current, initial)[0]
    assert "food_produced" in found
    assert not {"cooking_capacity", "manufactured_food"} & found


def test_smart_batteries_require_new_objects_and_the_smart_type():
    initial, current = state(), complete_state()
    current["extended"]["objects"]["1"]["joules"] = 9999
    current["extended"]["objects"]["2"]["joules"] = 9999
    found = evaluate(current, initial)[0]
    assert "battery_charged" in found
    assert not {"charged_smart_battery", "smart_battery_bank"} & found
    current["extended"]["objects"]["1"]["joules"] = 20000
    initial["extended"]["objects"]["1"] = copy.deepcopy(current["extended"]["objects"]["1"])
    assert "smart_battery_bank" not in evaluate(current, initial)[0]
    current["extended"]["objects"]["1"]["prefab"] = "BatteryMedium"
    assert "smart_battery_bank" not in evaluate(current, state())[0]


def test_crops_exclude_wild_and_initially_planted_plants():
    initial, current = state(), complete_state()
    current["extended"]["objects"]["9"]["planted"] = False
    assert "diverse_crops" not in evaluate(current, initial)[0]
    initial["extended"]["objects"]["3"] = copy.deepcopy(current["extended"]["objects"]["3"])
    assert "hydroponic_expansion" not in evaluate(current, initial)[0]
    start, plants = state(), state()
    plants["extended"]["objects"] = {
        str(i): {"prefab": "PrickleFlower", "planted": i < 2} for i in range(3)
    }
    assert "crop_planted" not in evaluate(plants, start)[0]
    plants["extended"]["objects"]["2"]["planted"] = True
    assert "crop_planted" in evaluate(plants, start)[0]


@pytest.mark.parametrize("delta,achieved", [(999, False), (1000, True)])
def test_consumed_energy_boundary(delta, achieved):
    start = state()
    start["extended"]["consumed_j_by_day"]["1"] = 1500
    current = copy.deepcopy(start)
    current["extended"]["consumed_j_by_day"]["1"] += delta
    assert ("power_used" in evaluate(current, start)[0]) == achieved


def test_research_thresholds_count_new_and_advanced_technologies():
    start, current = state(), state()
    basic = sorted(BASIC_TECHNOLOGIES)
    current["metrics"]["completed_technologies"] = ADVANCED[:1] + basic[:2]
    found = evaluate(current, start)[0]
    assert "research_started" in found and "advanced_research" not in found
    current["metrics"]["completed_technologies"] += basic[2:3]
    assert "advanced_research" in evaluate(current, start)[0]
    current["metrics"]["completed_technologies"] = ADVANCED + basic[:5]
    assert "research_breadth" in evaluate(current, start)[0]
    start["metrics"]["completed_technologies"] = ADVANCED[:1]
    assert "research_breadth" not in evaluate(current, start)[0]


def test_generation_is_unresolved_when_generators_existed_at_setup():
    start, current = state(), state()
    current["native"]["groups"]["Generator"] = 1
    current["generation"] = {"Generator": 100000, "DebugPower": 10**7}
    found, _ = evaluate(current, start)
    assert {"coal_generation", "any_new_generator_100kj"} <= found
    current["generation"] = {"DebugPower": 10**7}
    assert "any_new_generator_100kj" not in evaluate(current, start)[0]
    start["native"]["groups"]["Generator"] = 1
    current["native"]["groups"]["Generator"] = 2
    current["generation"] = {"Generator": 100000}
    found, unresolved = evaluate(current, start)
    assert set(unresolved) == {"coal_generation", "any_new_generator_100kj"}
    assert not found & unresolved.keys()


def endpoint(tmp_path, monkeypatch, rows, states, spec=None):
    """Assess synthetic evidence rows whose files map to decoded states."""
    folder = tmp_path / "episodes/episode-001"
    (folder / "evidence").mkdir(parents=True)
    (folder / "setup.json").write_text(
        json.dumps({"initial_evidence": "episodes/episode-001/evidence/initial"})
    )
    for name in states:
        (folder / "evidence" / name).write_text(name)
    for row in rows:
        row["path"] = f"episodes/episode-001/evidence/{row['path']}"
    monkeypatch.setattr(progress, "snapshot", lambda raw: states[raw.decode()])
    spec = spec or CATALOG.trials["oni-kimi-v7-live-20261115"]
    return progress.assess_endpoint(tmp_path, folder, rows, None, spec, RUBRIC)


def test_endpoint_stops_at_death_and_ignores_late_evidence(tmp_path, monkeypatch):
    built = state()
    built["native"]["groups"]["Bed"] = 1
    rows = [
        {"kind": "save", "path": "late", "elapsed": 10800.5},
        {"kind": "save", "path": "built", "elapsed": 10},
        {"kind": "history", "path": "loss", "elapsed": 20},
        {"kind": "save", "path": "unread", "elapsed": 30},
    ]
    states = {"initial": state(), "late": complete_state(), "built": built}
    review = endpoint(tmp_path, monkeypatch, rows, states)
    assert review["episode"]["outcome"] == "death"
    assert review["episode"]["preserved_save_count"] == 1
    assert [a["milestone_id"] for a in review["awards"]] == ["build_cot"]
    assert review["awards"][0]["first_verified_seconds"] == 10
    assert review["complete"]
    statuses = {x["id"]: x["status"] for x in review["episode"]["criteria"]}
    assert statuses["build_cot"] == "verified"
    assert statuses["build_outhouse"] == "not_observed"


def test_dying_save_is_scored_before_the_episode_ends(tmp_path, monkeypatch):
    dying = complete_state()
    dying["native"]["population"] = {"living": 0, "dead": 3}
    rows = [
        {"kind": "save", "path": "dying", "elapsed": 10},
        {"kind": "save", "path": "unread", "elapsed": 20},
    ]
    review = endpoint(tmp_path, monkeypatch, rows, {"initial": state(), "dying": dying})
    assert review["episode"]["outcome"] == "death"
    assert len(review["awards"]) == 50


def test_endpoint_without_saves_is_incomplete(tmp_path, monkeypatch):
    review = endpoint(tmp_path, monkeypatch, [], {"initial": state()})
    assert not review["complete"] and review["awards"] == []
    assert {x["status"] for x in review["episode"]["criteria"]} == {"unavailable"}


@pytest.mark.parametrize("credit", [0, 600])
def test_canonical_score_reaches_one_hundred_within_the_credited_time(
    tmp_path, monkeypatch, credit
):
    root = tmp_path / "trial"
    spec = CATALOG.trials["oni-astra-v7-live-20261116"]
    trial = Trial(
        root,
        spec,
        RUBRIC,
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
        inputs=CATALOG.inputs.get(spec.inputs_id),
    )
    folder = root / "episodes/episode-001"
    (folder / "evidence").mkdir(parents=True)
    (folder / "evidence/initial").write_text("initial")
    (folder / "evidence/after").write_text("after")
    write_json(
        folder / "setup.json",
        {
            "verified": True,
            "initial": {},
            "initial_evidence": "episodes/episode-001/evidence/initial",
        },
    )
    row = {"kind": "save", "path": "episodes/episode-001/evidence/after", "elapsed": 10800 + credit}
    (folder / "evidence.jsonl").write_text(json.dumps(row) + "\n")
    states = {"initial": state(), "after": complete_state()}
    monkeypatch.setattr(progress, "snapshot", lambda raw: states[raw.decode()])
    trial.state["episodes"].append(
        {"id": folder.name, "status": "completed", "reason": "deadline", "segments": []}
    )
    trial.budget.start()
    trial.finish("completed", "deadline")
    if credit:
        record = json.loads((root / "trial.json").read_text())
        record["provider_recovery"] = {"timeout_count": 1, "timeout_credit_seconds": credit}
        write_json(root / "trial.json", record)
        with (root / "events.jsonl").open("a") as events:
            events.write(json.dumps({"type": "provider_timeout_credit", "seconds": 600}) + "\n")
    result = score(root)[1]
    assert result["score"] == result["confirmed_subtotal"] == 100
