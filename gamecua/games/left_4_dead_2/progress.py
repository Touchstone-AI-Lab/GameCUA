"""Read-only native event telemetry; teammates never earn player combat points."""

import json
import math
from pathlib import Path

VERSION = "l4d2-native-events-3"
MAPS = ("c1m1_hotel", "c1m2_streets")
ROUTE = json.loads(Path(__file__).with_name("route.json").read_text())
RADIUS = 150
HEIGHT = 100
COUNTERS = {
    "kills": (10, 20, 35, 50, 75, 100, 150, 200, 300),
    "specials": (1, 2, 3, 5, 8, 12, 16),
    "heals": (1, 2, 3, 4),
    "revives": (1, 2),
    "shots": (25, 100, 300),
}
SURVIVAL_MINUTES = (2, 5, 10, 15, 20)
PREDICATES = {
    *(f"route_{percent}" for percent in range(1, 100)),
    "chapter_complete",
    *(f"{key}_{n}" for key, steps in COUNTERS.items() for n in steps),
    *(f"survive_{n}" for n in SURVIVAL_MINUTES),
}


def route_progress(x, y, z):
    """Return the furthest route distance whose corridor contains the position."""
    best = None
    for leg in ROUTE["legs"]:
        for a, b in zip(leg, leg[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = dx * dx + dy * dy
            t = 0 if length == 0 else max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / length))
            px, py, pz = a[0] + t * dx, a[1] + t * dy, a[2] + t * (b[2] - a[2])
            if math.hypot(x - px, y - py) <= RADIUS and abs(z - pz) <= HEIGHT:
                distance = a[3] + t * (b[3] - a[3])
                best = distance if best is None else max(best, distance)
    return best


def percent(distance, start):
    return max(0, min(99, int(100 * (distance - start) / (ROUTE["length"] - start))))


def facts(kind, raw, initial):
    if kind != "history":
        return set(), None
    start = route_progress(initial["x"], initial["y"], initial["z"]) or 0
    found, terminal = set(), None
    for row in json.loads(raw):
        if row["human_alive"] and row["map"] == MAPS[0]:
            distance = route_progress(row["x"], row["y"], row["z"])
            if distance is not None:
                found.update(f"route_{k}" for k in range(1, percent(distance, start) + 1))
            for key, steps in COUNTERS.items():
                found.update(
                    f"{key}_{n}" for n in steps if row.get(key, 0) - initial.get(key, 0) >= n
                )
            minutes = (row["time"] - initial["time"]) / 60
            found.update(f"survive_{n}" for n in SURVIVAL_MINUTES if minutes >= n)
        if row["kind"] == "chapter_complete" and row["map"] == MAPS[0] and row["human_alive"]:
            found.update(f"route_{k}" for k in range(1, 100))
            found.add("chapter_complete")
            terminal = "victory"
        if row["kind"] in ("human_death", "mission_lost"):
            terminal = "death"
    return found, terminal
