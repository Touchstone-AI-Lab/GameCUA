"""Native Baba Is You slot save reader."""

import re

WORLD = "baba"
COMPLETED = "3"
LEVEL = re.compile(r"[a-z]?\d+level")
MAPS = frozenset(
    {
        "106level",
        "304level",
        "283level",
        "264level",
        "200level",
        "177level",
        "207level",
        "169level",
        "16level",
        "87level",
        "179level",
        "206level",
        "182level",
        "180level",
        "232level",
    }
)


def sections(raw):
    """Parse the INI-like slot save into a dict of sections."""
    result = {}
    current = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            current = result.setdefault(line[1:-1], {})
        elif current is not None and "=" in line:
            key, value = line.split("=", 1)
            current[key] = value
    return result


def read_save(raw):
    """Extract cleared levels, completed areas, prize counts and entered areas."""
    data = sections(raw)
    world = data.get(WORLD, {})
    prizes = {key: int(value) for key, value in data.get(f"{WORLD}_prize", {}).items()}
    completed = {key for key, value in world.items() if value == COMPLETED and LEVEL.fullmatch(key)}
    return {
        "cleared": sorted(completed - MAPS),
        "areas_complete": sorted(completed & MAPS),
        "prize_total": prizes.pop("total", 0),
        "map_prizes": prizes,
        "clears_total": int(data.get(f"{WORLD}_clears", {}).get("total", "0")),
        "entered": sorted(
            key.removesuffix("_intro")
            for key, value in world.items()
            if value == "1"
            and key.endswith("_intro")
            and LEVEL.fullmatch(key.removesuffix("_intro"))
        ),
    }
