"""Development v7 endpoint scoring and native death detection for ONI."""

import json
from collections import Counter

from ...evidence import time_allowance
from .metrics import BATTERIES, CROPS, snapshot
from .native import read_save

VERSION = "oni-native-progress-15"
BUILDINGS = {
    "build_cot": ("Bed",),
    "build_outhouse": ("Outhouse",),
    "build_wash_basin": ("WashBasin",),
    "build_mess_table": ("DiningTable",),
    "build_storage_bin": ("StorageLocker",),
    "build_ration_box": ("RationBox",),
    "build_ladder": ("Ladder",),
    "build_tile": ("Tile",),
    "build_pneumatic_door": ("Door",),
    "build_pitcher_pump": ("LiquidPumpingStation",),
    "build_research_station": ("ResearchCenter",),
    "build_super_computer": ("AdvancedResearchCenter",),
    "build_manual_generator": ("ManualGenerator",),
    "build_coal_generator": ("Generator",),
    "build_battery": tuple(sorted(BATTERIES)),
    "build_wire": ("Wire",),
    "build_oxygen_diffuser": ("MineralDeoxidizer",),
    "build_refrigerator": ("Refrigerator",),
    "build_electrolyzer": ("Electrolyzer",),
    "build_planter_box": ("PlanterBox",),
}
FACILITIES = {
    "gas_handling_facilities": {"GasPump": 1, "GasFilter": 1},
    "water_treatment_facilities": {"WaterPurifier": 1, "LiquidPump": 1},
    "plumbed_sanitation_facilities": {"FlushToilet": 1, "WashSink": 1},
    "conductive_power_infrastructure": {"PowerTransformer": 1, "WireRefined": 10},
    "atmo_suit_facilities": {"SuitFabricator": 1, "SuitLocker": 2, "SuitMarker": 1},
    "ranching_facilities": {
        "RanchStation": 1,
        "CreatureFeeder": 1,
        "CreatureDeliveryPoint": 1,
        "EggIncubator": 1,
    },
    "automation_infrastructure": {
        "LogicTemperatureSensor": 1,
        "LogicPressureSensorGas": 1,
        "LogicWire": 10,
    },
}
GENERATORS = (
    "ManualGenerator",
    "Generator",
    "HydrogenGenerator",
    "MethaneGenerator",
    "PetroleumGenerator",
    "WoodGasGenerator",
    "SolarPanel",
    "SolarPanelModule",
    "SteamTurbine",
    "SteamTurbine2",
    "PeatGenerator",
    "ReefGenerator",
)
BASIC_TECHNOLOGIES = {
    "AdvancedFiltration",
    "AdvancedResearch",
    "Artistry",
    "BasicRefinement",
    "Combustion",
    "FarmingTech",
    "FineDining",
    "GasPiping",
    "ImprovedOxygen",
    "InteriorDecor",
    "Jobs",
    "LiquidPiping",
    "LogicControl",
    "MedicineI",
    "MedicineII",
    "PortableGasses",
    "PowerRegulation",
    "PressureManagement",
    "SanitationSciences",
}
CRITERIA = (
    set(BUILDINGS)
    | set(FACILITIES)
    | {
        "power_produced",
        "oxygen_produced",
        "food_produced",
        "battery_charged",
        "power_used",
        "crop_planted",
        "manufactured_food",
        "water_in_pipes",
        "research_started",
        "refined_stock",
        "advanced_research",
        "coal_generation",
        "any_new_generator_100kj",
        "research_breadth",
        "water_storage_infrastructure",
        "cooking_capacity",
        "metal_workshop",
        "charged_smart_battery",
        "diverse_crops",
        "smart_battery_bank",
        "steel_inventory",
        "hydroponic_expansion",
        "plastic_inventory",
    }
)
PREDICATES = {"replacement_" + key for key in CRITERIA}


def production(current, initial, first_day):
    """Sum native energy, oxygen and calorie production since setup."""
    totals = {"energy_j": 0.0, "oxygen_kg": 0.0, "calories": 0.0}
    for metrics, sign in ((current, 1), (initial, -1)):
        for entries in metrics["production_by_day"].values():
            for key in totals:
                totals[key] += sign * entries[key]
        for day, value in metrics["manufactured_calories_by_day"].items():
            if sign < 0 and day not in current["manufactured_calories_by_day"]:
                continue
            if int(day) >= first_day:
                totals["calories"] += sign * value
    return totals


def evaluate(current, initial):
    """Return the v7 criteria met by a save and those that cannot be attributed."""
    data, baseline = current["native"], initial["native"]
    metrics, old_metrics = current["metrics"], initial["metrics"]
    extra, old_extra = current["extended"], initial["extended"]
    found, unresolved = set(), {}

    def added(*prefabs):
        return sum(data["groups"].get(p, 0) - baseline["groups"].get(p, 0) for p in prefabs)

    found.update(key for key, prefabs in BUILDINGS.items() if added(*prefabs) > 0)
    found.update(
        key
        for key, requirements in FACILITIES.items()
        if all(added(prefab) >= count for prefab, count in requirements.items())
    )
    totals = production(metrics, old_metrics, baseline["cycle"] + 1)
    for key, metric, minimum in (
        ("power_produced", "energy_j", 10000),
        ("oxygen_produced", "oxygen_kg", 20),
        ("food_produced", "calories", 1000000),
    ):
        if totals[metric] >= minimum:
            found.add(key)
    completed = set(metrics["completed_technologies"]) - set(old_metrics["completed_technologies"])
    advanced = len(completed - BASIC_TECHNOLOGIES)
    for key, count, minimum in (
        ("research_started", 2, 0),
        ("advanced_research", 4, 1),
        ("research_breadth", 8, 3),
    ):
        if len(completed) >= count and advanced >= minimum:
            found.add(key)
    smart, crops = [], Counter()
    for identity, item in extra["objects"].items():
        old = old_extra["objects"].get(identity)
        if item["prefab"] in BATTERIES and not old:
            if item["joules"] > 0:
                found.add("battery_charged")
            if item["prefab"] == "BatterySmart":
                smart.append(item["joules"])
        if item["prefab"] in CROPS and item["planted"] and not (old and old["planted"]):
            crops[item["prefab"]] += 1
    if sum(crops.values()) >= 3:
        found.add("crop_planted")
    if any(joules >= 10000 for joules in smart):
        found.add("charged_smart_battery")
    if len(smart) >= 2 and sum(smart) >= 20000:
        found.add("smart_battery_bank")
    if sum(count >= 3 for count in crops.values()) >= 2:
        found.add("diverse_crops")
    if added("HydroponicFarm") >= 6 and crops["PrickleFlower"] >= 6:
        found.add("hydroponic_expansion")
    consumed = sum(extra["consumed_j_by_day"].values())
    if consumed - sum(old_extra["consumed_j_by_day"].values()) >= 1000:
        found.add("power_used")
    stock, old_stock = extra["stock_kg"], old_extra["stock_kg"]
    if stock["refined_metal"] - old_stock["refined_metal"] >= 100:
        found.add("refined_stock")
    if added("RockCrusher") >= 1 and stock["refined_metal"] - old_stock["refined_metal"] >= 200:
        found.add("metal_workshop")
    for resource in ("steel", "plastic"):
        if stock[resource] - old_stock[resource] >= 100:
            found.add(resource + "_inventory")
    water = extra["pipe_water_kg"] - old_extra["pipe_water_kg"]
    if added("LiquidPump") > 0 and water > 0:
        found.add("water_in_pipes")
    if added("LiquidReservoir") >= 1 and water >= 100:
        found.add("water_storage_infrastructure")
    manufactured = sum(
        value - old_metrics["manufactured_calories_by_day"].get(day, 0)
        for day, value in metrics["manufactured_calories_by_day"].items()
        if int(day) >= baseline["cycle"] + 1
    )
    if manufactured >= 1000000:
        found.add("manufactured_food")
    if added("CookingStation") >= 1 and manufactured >= 4000000:
        found.add("cooking_capacity")
    old_generation, new_generation = initial["generation"], current["generation"]
    for key, prefabs, minimum in (
        ("coal_generation", ("Generator",), 50000),
        ("any_new_generator_100kj", GENERATORS, 100000),
    ):
        if any(baseline["groups"].get(p, 0) for p in prefabs):
            unresolved[key] = "Initial generators prevent attributing type totals to new devices."
            continue
        generated = sum(new_generation.get(p, 0) - old_generation.get(p, 0) for p in prefabs)
        if generated >= minimum and added(*prefabs) > 0:
            found.add(key)
    return found, unresolved


def terminal(population):
    """Return death once no duplicant is alive."""
    return "death" if population["living"] == 0 and population["dead"] > 0 else None


def facts(kind, raw, initial):
    """Return no points and the terminal outcome shown by one evidence file."""
    return set(), "death" if kind == "history" else terminal(read_save(raw)["population"])


def assess_endpoint(root, folder, rows, initial, spec, rubric):
    """Award each v7 milestone first met by a preserved save before death or the time limit."""
    setup = json.loads((folder / "setup.json").read_text())
    baseline = snapshot((root / setup["initial_evidence"]).read_bytes())
    awards, unresolved, outcome, count = {}, {}, "unknown", 0
    horizon = time_allowance(root, spec)
    for row in rows:
        if row["kind"] not in ("save", "history") or row.get("baseline"):
            continue
        elapsed = row["elapsed"]
        if not 0 <= elapsed <= horizon:
            continue
        ended = "death"
        if row["kind"] == "save":
            state = snapshot((root / row["path"]).read_bytes())
            ended = terminal(state["native"]["population"])
            found, unresolved = evaluate(state, baseline)
            count += 1
            for milestone in rubric.milestones:
                if milestone.predicate.removeprefix("replacement_") in found:
                    awards.setdefault(
                        milestone.id,
                        {
                            "milestone_id": milestone.id,
                            "points": milestone.points,
                            "first_verified_seconds": elapsed,
                            "evidence": row["path"],
                        },
                    )
        if ended:
            outcome = ended
            break
    statuses = [
        {
            "id": m.id,
            "status": "verified"
            if m.id in awards
            else "unavailable"
            if (m.id in unresolved or not count)
            else "not_observed",
            "reason": "Verified from preserved native evidence."
            if m.id in awards
            else unresolved.get(m.id, "No qualifying preserved native evidence."),
        }
        for m in rubric.milestones
    ]
    complete = bool(count) and not unresolved
    return {
        "complete": complete,
        "awards": list(awards.values()),
        "failures": [] if complete else [{"reason": "selected_rubric_native_evidence_incomplete"}],
        "episode": {
            "outcome": outcome,
            "milestones": sorted(awards),
            "criteria": statuses,
            "unavailable": unresolved,
            "preserved_save_count": count,
        },
    }
