"""Milestones come only from the game's own log of the verified seeded run."""

import json
import re
from pathlib import Path

VERSION = "isaac-native-log-4"
RUN_START = re.compile(r"\[INFO\] - RNG Start Seed: (\w{4} \w{4}) \((\d+)\)")
STAGE = re.compile(r"\[INFO\] - Level::Init m_Stage (\d+), m_StageType (\d+)(?: Seed (\d+))?")
ROOM = re.compile(r"\[INFO\] - Room (\d+)\.(\d+)\((.*)\)")
COLLECTIBLE = re.compile(r"\[INFO\] - Adding collectible (\d+) ")
MOM = re.compile(r"\[INFO\] - Mom clear time: (\d+)")
CUTSCENE = re.compile(r"\[INFO\] - playing cutscene (\d+) ")
DEATH = re.compile(r"\[INFO\] - Game Over\. Killed by")
PATTERNS = (RUN_START, STAGE, ROOM, COLLECTIBLE, MOM, CUTSCENE, DEATH)
STAGES = {
    "second_floor": 2,
    "caves": 3,
    "fourth_floor": 4,
    "depths": 5,
    "sixth_floor": 6,
    "seventh_floor": 7,
    "eighth_floor": 8,
}
FLOOR1 = json.loads((Path(__file__).with_name("floor1-mvsn-tfs1.json")).read_text())
FLOOR1_DISTANCE = {(r["type"], r["variant"]): r["distance"] for r in FLOOR1["rooms"]}
FLOOR1_ENEMY_ROOMS = {
    (r["type"], r["variant"]) for r in FLOOR1["rooms"] if r["type"] == 1 and r.get("enemies")
}
CLOSER = {
    f"floor1_closer_{k}": FLOOR1["start_distance"] - k
    for k in range(1, FLOOR1["start_distance"] + 1)
}
COLLECTIBLES = {f"collectible_{k}": k for k in range(1, 13)}
ROOMS = {f"rooms_{k}": k for k in (3, 5, 8, 12, 16, 20, 25, 30, 35, 40, 50)}
FLOOR1_NORMAL_ROOMS = {
    (r["type"], r["variant"])
    for r in FLOOR1["rooms"]
    if r["type"] == 1 and r["grid"] != FLOOR1["start_grid"]
}
SPECIAL = {
    "visited_shop": 2,
    "visited_treasure": 4,
    "visited_miniboss": 6,
    "visited_secret": 7,
    "visited_super_secret": 8,
    "visited_arcade": 9,
    "visited_challenge": 11,
    "visited_library": 12,
    "visited_devil": 14,
    "visited_angel": 15,
}
TREASURE_FLOORS = {f"treasure_floors_{k}": k for k in (2, 3, 4)}
CLEARS = {f"floor1_cleared_{k}": k for k in range(1, len(FLOOR1_ENEMY_ROOMS) + 1)}
PREDICATES = {
    "left_start_room",
    "mom_defeated",
    *STAGES,
    *CLOSER,
    *COLLECTIBLES,
    *CLEARS,
    *ROOMS,
    *SPECIAL,
    *TREASURE_FLOORS,
    "floor1_explored",
}


def project(text):
    return [line for line in text.splitlines() if any(p.match(line) for p in PATTERNS)]


def facts(kind, raw, initial):
    """Read floor, room, item and ending predicates from the first run in the log."""
    if kind != "save":
        return set(), None
    lines = json.loads(raw)["lines"]
    starts = [i for i, line in enumerate(lines) if RUN_START.match(line)]
    if not starts:
        return set(), None
    restarted = len(starts) > 1
    lines = lines[starts[0] : starts[1] if restarted else None]
    found, mom, stage, items, mapped = set(), False, 0, 0, False
    current, cleared, visited, treasure, explored = None, set(), set(), set(), set()
    for line in lines[1:]:
        if match := STAGE.match(line):
            stage, current = int(match.group(1)), None
            mapped = (stage, int(match.group(2)), match.group(3)) == (
                FLOOR1["stage"],
                FLOOR1["stage_type"],
                str(FLOOR1["level_seed"]),
            )
            for predicate, threshold in STAGES.items():
                if stage >= threshold:
                    found.add(predicate)
        elif match := ROOM.match(line):
            room = (int(match.group(1)), int(match.group(2)))
            if match.group(3) != "Start Room":
                found.add("left_start_room")
                visited.add((stage, *room))
                found.update(k for k, count in ROOMS.items() if len(visited) >= count)
            found.update(k for k, kind in SPECIAL.items() if room[0] == kind)
            if room[0] == SPECIAL["visited_treasure"]:
                treasure.add(stage)
                found.update(k for k, count in TREASURE_FLOORS.items() if len(treasure) >= count)
            if current in FLOOR1_ENEMY_ROOMS and current != room:
                cleared.add(current)
                found.update(k for k, count in CLEARS.items() if len(cleared) >= count)
            current = room if mapped else None
            if mapped and room in FLOOR1_NORMAL_ROOMS:
                explored.add(room)
                if explored == FLOOR1_NORMAL_ROOMS:
                    found.add("floor1_explored")
            distance = FLOOR1_DISTANCE.get(room)
            if mapped and distance is not None:
                found.update(k for k, limit in CLOSER.items() if distance <= limit)
        elif COLLECTIBLE.match(line):
            items += 1
            found.update(k for k, count in COLLECTIBLES.items() if items >= count)
        elif MOM.match(line):
            found.add("mom_defeated")
            mom = True
        elif CUTSCENE.match(line) and mom:
            return found, "victory"
        elif DEATH.match(line):
            return found, "death"
    return found, "death" if restarted else None
