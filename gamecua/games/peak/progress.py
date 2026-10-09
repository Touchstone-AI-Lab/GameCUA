"""PEAK ascent milestones from preserved native runtime samples of one expedition."""

import json

VERSION = "peak-native-progress-4"
ASCENT_HEIGHTS = {f"ascent_{height:03d}m": height for height in range(1, 101)}
PREDICATES = set(ASCENT_HEIGHTS)


def playable(row):
    """Return whether a sample shows the local character on the island with readable stats."""
    return (
        not row.get("error")
        and row["character_present"]
        and row["stats_initialized"]
        and not row["in_airport"]
    )


def facts(kind, raw, initial):
    """Return ascent heights reached above the run-start anchor before any native terminal state."""
    if kind != "save":
        return set(), None
    evidence = json.loads(raw)
    anchor = evidence.get("run_start")
    if anchor is None:
        return set(), None
    found = set()
    for row in evidence["rows"]:
        if row["sequence"] < anchor["sequence"] or not playable(row):
            continue
        if row["won"]:
            return found, "victory"
        if row["lost"]:
            return found, "death"
        if row["dead"] or row["passed_out"] or not row["run_started"]:
            continue
        rise = row["height_meters"] - anchor["height_meters"]
        found.update(predicate for predicate, height in ASCENT_HEIGHTS.items() if rise >= height)
    return found, None
