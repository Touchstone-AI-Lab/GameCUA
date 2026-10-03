"""Base-development milestones scored from preserved native checkpoints, never agent claims."""

import json

from ...evidence import time_allowance
from ...storage import local_file

VERSION = "civ6-native-statistics-5-science-1-development-1-science-route-3"
TECHNOLOGIES = (
    "POTTERY",
    "MINING",
    "ANIMAL_HUSBANDRY",
    "SAILING",
    "ASTROLOGY",
    "IRRIGATION",
    "WRITING",
    "ARCHERY",
    "MASONRY",
    "BRONZE_WORKING",
    "THE_WHEEL",
    "CURRENCY",
    "HORSEBACK_RIDING",
    "IRON_WORKING",
    "CONSTRUCTION",
    "ENGINEERING",
    "CELESTIAL_NAVIGATION",
    "MATHEMATICS",
    "SHIPBUILDING",
    "APPRENTICESHIP",
    "MACHINERY",
    "EDUCATION",
    "MILITARY_ENGINEERING",
    "CASTLES",
    "STIRRUPS",
    "MILITARY_TACTICS",
)
BUILDINGS = (
    "MONUMENT",
    "GRANARY",
    "WATER_MILL",
    "LIBRARY",
    "SHRINE",
    "WALLS",
    "BARRACKS",
    "STABLE",
    "LIGHTHOUSE",
    "MARKET",
    "WORKSHOP",
    "UNIVERSITY",
    "TEMPLE",
    "ARENA",
)
DISTRICTS = ("CAMPUS", "COMMERCIAL_HUB", "INDUSTRIAL_ZONE", "HARBOR", "HOLY_SITE", "ENCAMPMENT")
UNITS = ("BUILDER", "TRADER", "ARCHER", "SPEARMAN", "GALLEY")


def criteria(kind, prefix, names):
    """Map each predicate id to the native inventory kind and type name it requires."""
    return {
        f"base-{kind}-" + name.lower().replace("_", "-"): (kind, prefix + name) for name in names
    }


CRITERIA = {
    **criteria("tech", "TECH_", TECHNOLOGIES),
    "base-city": ("city", "CITY"),
    **criteria("building", "BUILDING_", BUILDINGS),
    **criteria("district", "DISTRICT_", DISTRICTS),
    **criteria("unit", "UNIT_", UNITS),
}
PREDICATES = set(CRITERIA)


def achieved(state):
    """Return the predicates a native checkpoint satisfies for the human player."""
    found = {
        "tech": set(state["technologies"]),
        "city": {"CITY"} if state["cities"] else set(),
        "building": {row["type"] for row in state["buildings"] if not row["pillaged"]},
        "district": {
            row["type"] for row in state["districts"] if row["complete"] and not row["pillaged"]
        },
        "unit": {row["type"] for row in state["units"]},
    }
    return {key for key, (kind, name) in CRITERIA.items() if name in found[kind]}


def outcome(state):
    """Return the native terminal outcome of a checkpoint, if any."""
    if state["winning_team"] == state["team_id"]:
        return "victory"
    if not state["alive"] or state["winning_team"] >= 0:
        return "death"
    return None


def assess_endpoint(root, folder, rows, initial, spec, rubric):
    """Award each milestone at its first preserved checkpoint inside the charged allowance."""
    allowance = time_allowance(root, spec)
    checkpoints = []
    for row in rows:
        if row["kind"] != "save" or row.get("baseline") or not 0 <= row["elapsed"] <= allowance:
            continue
        item = json.loads(local_file(root, row["path"]).read_text())
        checkpoints.append((row, item, achieved(item["native_state"])))
    if not checkpoints:
        return {
            "complete": False,
            "awards": [],
            "failures": [{"reason": "missing_base_game_endpoint"}],
            "episode": {
                "outcome": "unknown",
                "milestones": [],
                "unresolved": ["missing_base_game_endpoint"],
            },
        }
    last_row, endpoint, _ = checkpoints[-1]
    awards = []
    for milestone in rubric.milestones:
        evidence = next(
            (row for row, _, found in checkpoints if milestone.predicate in found), None
        )
        if evidence is not None:
            awards.append(
                {
                    "milestone_id": milestone.id,
                    "points": milestone.points,
                    "first_verified_seconds": evidence["elapsed"],
                    "evidence": evidence["path"],
                }
            )
    return {
        "complete": True,
        "awards": awards,
        "failures": [],
        "episode": {
            "outcome": outcome(endpoint["native_state"]) or "unknown",
            "milestones": [award["milestone_id"] for award in awards],
            "endpoint_evidence": last_row["path"],
            "unresolved": [],
        },
    }
