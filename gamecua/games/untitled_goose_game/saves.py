"""Completed main-story task flags from Untitled Goose Game BinaryFormatter slot saves."""

from .binaryformatter import loads

GOALS = frozenset(
    {
        "goalGarden",
        "goalWet",
        "goalKeys",
        "goalHat",
        "goalRake",
        "goalPicnic",
        "goalHammering",
        "goalBroom",
        "goalPhonebooth",
        "goalWrongGlasses",
        "goalBuyBack",
        "goalGetInShop",
        "goalShopping",
        "goalGarage",
        "goalBreakVase",
        "goalDressStatue",
        "goalBell",
        "goalRibbon",
        "goalBarefoot",
        "goalWashing",
        "goalPrune",
        "goalIntoPub",
        "goalOldMan1",
        "goalBoat",
        "goalOldMan2",
        "goalFlower",
        "goalPintGlass",
        "goalSetTable",
        "goalBucket",
        "goalModelVillage",
        "goalStealBell",
        "goalFinale",
    }
)


class SaveFormatError(ValueError):
    """Raised for a slot save that cannot be parsed, such as one still being written."""


def read_save(raw):
    """Return the main-story goals that a native slot save marks complete."""
    try:
        values = {row["key"]: row["boolValue"] for row in loads(raw)["entries"]}
    except Exception as exc:
        raise SaveFormatError("Unreadable native Untitled Goose Game save") from exc
    return {"completed": sorted(goal for goal in GOALS if values.get(goal) is True)}
