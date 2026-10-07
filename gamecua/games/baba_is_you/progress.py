"""Scoring predicates use game-written slot saves, never playing-agent claims."""

from .saves import read_save

VERSION = "baba-progress-6"
NUMBERED_AREAS = frozenset(
    {
        "177level",
        "207level",
        "206level",
        "16level",
        "169level",
        "87level",
        "180level",
        "182level",
        "179level",
        "232level",
    }
)
LAKE = "177level"
MAIN_BRANCHES = ("189level", "3level", "2level", "90level", "5level", "6level")
LAKE_LEVELS = (
    "20level",
    "212level",
    "10level",
    "4level",
    "93level",
    "209level",
    "15level",
    "8level",
    "236level",
    "210level",
    "136level",
    "30level",
    "166level",
)
ISLAND_LEVELS = ("310level", "205level", "218level", "171level", "172level", "234level", "107level")
CHOICE_LEVELS = MAIN_BRANCHES + LAKE_LEVELS + ISLAND_LEVELS
THRESHOLDS = {
    "areas_entered": (1, 2, 3, 4),
    "lake_levels": (1, 2, 3, 4, 5, 6, 7),
    "area_levels": (10, 12, 15),
    "other_area_levels": (1, 4),
    "levels": (8, 16, 24, 30),
}
PREDICATES = (
    {"level_0", "level_1", "opening_3", "opening_4", "lake_complete", "second_area_complete"}
    | {f"{kind}_{n}" for kind, values in THRESHOLDS.items() for n in values}
    | {f"cleared_{level}" for level in CHOICE_LEVELS}
)


def facts(kind, raw, initial):
    if kind != "save":
        return set(), None
    state = read_save(raw)
    cleared = set(state["cleared"]) - set(initial["cleared"])
    areas = set(state["areas_complete"]) - set(initial.get("areas_complete", []))
    before = initial.get("map_prizes", {})
    gained = sum(
        max(0, state["map_prizes"].get(area, 0) - before.get(area, 0)) for area in NUMBERED_AREAS
    )
    completed = len(areas & NUMBERED_AREAS)
    opening = {"0level", "1level"} <= cleared and cleared & {"189level", "3level"}
    result = set()
    if "0level" in cleared:
        result.add("level_0")
    if {"0level", "1level"} <= cleared:
        result.add("level_1")
    if opening:
        result.add("opening_3")
    if opening and cleared & {"5level", "6level"}:
        result.add("opening_4")
    entered = set(state.get("entered", [])) - set(initial.get("entered", []))
    lake = max(0, state["map_prizes"].get(LAKE, 0) - before.get(LAKE, 0))
    counts = {
        "areas_entered": len(entered & NUMBERED_AREAS),
        "lake_levels": lake,
        "area_levels": gained,
        "other_area_levels": gained - lake,
        "levels": len(cleared),
    }
    for kind, values in THRESHOLDS.items():
        result |= {f"{kind}_{n}" for n in values if counts[kind] >= n}
    if LAKE in areas:
        result.add("lake_complete")
    if completed >= 2:
        result.add("second_area_complete")
    result |= {f"cleared_{level}" for level in CHOICE_LEVELS if level in cleared}
    return result, None
