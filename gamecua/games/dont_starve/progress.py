"""Survival and collection milestones from preserved native observer records, never model claims."""

import json

VERSION = "dont-starve-native-observer-6"
SURVIVAL_SECONDS = tuple(range(48, 2401, 48))
COLLECTION = {
    "gathered": (
        "cutgrass",
        "twigs",
        "flint",
        "log",
        "rocks",
        "goldnugget",
        "nitre",
        "charcoal",
        "berries",
        "carrot",
        "seeds",
        "petals",
        "foliage",
        "cutreeds",
        "pinecone",
        "cutstone",
        "boards",
        "rope",
        "silk",
        "spidergland",
        "manure",
        "pigskin",
        "beefalowool",
        "meat",
    ),
    "crafted": (
        "axe",
        "pickaxe",
        "torch",
        "shovel",
        "hammer",
        "razor",
        "pitchfork",
        "backpack",
        "spear",
        "armorwood",
        "strawhat",
        "trap",
        "heatrock",
        "umbrella",
    ),
    "built": (
        "campfire",
        "firepit",
        "researchlab",
        "researchlab2",
        "cookpot",
        "treasurechest",
    ),
    "eaten": ("berries", "carrot", "seeds", "berries_cooked", "carrot_cooked", "meatballs"),
}
PREDICATES = {
    *(f"fine_alive_{seconds}_seconds" for seconds in SURVIVAL_SECONDS),
    *(f"fine_{counter}_{item}" for counter, items in COLLECTION.items() for item in items),
}


def facts(kind, raw, initial):
    if kind != "save":
        return set(), None
    found, terminal = set(), None
    for row in json.loads(raw):
        if row["health"] > 0:
            found.update(
                f"fine_alive_{seconds}_seconds"
                for seconds in SURVIVAL_SECONDS
                if row["age"] - initial["age"] >= seconds
                and row["cycles"] - initial["cycles"] >= seconds // 480
            )
        for counter, items in COLLECTION.items():
            current, baseline = row.get(counter) or {}, initial.get(counter) or {}
            found.update(
                f"fine_{counter}_{item}"
                for item in items
                if current.get(item, 0) > baseline.get(item, 0)
            )
        if row["kind"] == "death" and row["health"] <= 0:
            terminal = "death"
    return found, terminal
