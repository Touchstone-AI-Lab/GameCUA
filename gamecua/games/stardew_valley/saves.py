"""Native Stardew Valley XML save reader; extracted state stays evaluator-private."""

import xml.etree.ElementTree as ET

SKILLS = ("farmingLevel", "fishingLevel", "foragingLevel", "miningLevel", "combatLevel")
INTEGERS = ("totalMoneyEarned", "deepestMineLevel", "maxItems")
TOOLS = ("Axe", "Hoe", "Pickaxe", "WateringCan")
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
STATISTICS = {
    "crops_shipped": "cropsShipped",
    "dirt_hoed": "dirtHoed",
    "seeds_sown": "seedsSown",
    "copper_found": "copperFound",
    "times_fished": "timesFished",
    "quests_completed": "questsCompleted",
    "monsters_killed": "monstersKilled",
    "items_foraged": "itemsForaged",
    "gifts_given": "giftsGiven",
}


def child(node, name):
    """Return the first child element with this local name."""
    if node is None:
        return None
    return next((e for e in node if e.tag.rsplit("}", 1)[-1] == name), None)


def text(node, name, default=None):
    """Return the stripped text of a named child."""
    element = child(node, name)
    return element.text.strip() if element is not None and element.text else default


def children(node, name):
    """Return the elements inside a named child."""
    element = child(node, name)
    return list(element) if element is not None else []


def strings(node, name):
    """Return the sorted non-empty strings of a named list."""
    return sorted(e.text.strip() for e in children(node, name) if e.text and e.text.strip())


def dictionary(node, name, value_type):
    """Read a serialized dictionary with string keys."""
    return {
        text(child(item, "key"), "string"): text(child(item, "value"), value_type)
        for item in children(node, name)
    }


def dictionary_keys(node, name):
    """Return the sorted first-element keys of a serialized dictionary."""
    keys = []
    for item in children(node, name):
        value = next(iter(child(item, "key")), None)
        if value is not None and value.text:
            keys.append(value.text.strip())
    return sorted(keys)


def location(root, name):
    """Return the named game location."""
    return next((e for e in children(root, "locations") if text(e, "name") == name), None)


def completed_bundles(root):
    """Return the Community Center bundles whose required slots are all donated."""
    requirements = {}
    for key, value in dictionary(root, "bundleData", "string").items():
        fields = value.split("/")
        ingredients = len(fields[2].split()) // 3
        slots = fields[4].strip() if len(fields) > 4 else ""
        requirements[int(key.rsplit("/", 1)[-1])] = (
            ingredients,
            int(slots) if slots else ingredients,
        )
    done = []
    for item in children(location(root, "CommunityCenter"), "bundles"):
        ingredients, slots = requirements[int(text(child(item, "key"), "int"))]
        flags = [(f.text or "").strip() for f in children(child(item, "value"), "ArrayOfBoolean")]
        if slots and flags[:ingredients].count("true") >= slots:
            done.append(int(text(child(item, "key"), "int")))
    return sorted(done)


def read_save(raw: bytes) -> dict:
    """Extract the scored progress fields of a native save."""
    root = ET.fromstring(raw)
    player = child(root, "player")
    statistics = {
        text(child(item, "key"), "string"): text(child(item, "value"), "unsignedInt")
        or text(child(item, "value"), "int")
        for item in children(child(player, "stats"), "Values")
    }
    recipes = {
        name: int(count) for name, count in dictionary(player, "craftingRecipes", "int").items()
    }
    areas = children(location(root, "CommunityCenter"), "areasComplete")
    return {
        **{name: int(text(player, name)) for name in INTEGERS},
        "skills": {name: int(text(player, name)) for name in SKILLS},
        **{key: int(statistics.get(name) or 0) for key, name in STATISTICS.items()},
        "mail_received": strings(player, "mailReceived"),
        "items_shipped": dictionary_keys(player, "basicShipped"),
        "farming_experience": int(children(player, "experiencePoints")[0].text),
        "furnaces_crafted": recipes.get("Furnace", 0),
        "crafted_recipes": sorted(name for name, count in recipes.items() if count > 0),
        "locations_visited": strings(player, "locationsVisited"),
        "minerals_found": dictionary_keys(player, "mineralsFound"),
        "artifacts_found": dictionary_keys(player, "archaeologyFound"),
        "museum_pieces": len(children(location(root, "ArchaeologyHouse"), "museumPieces")),
        "friendship_points": {
            text(child(item, "key"), "string"): int(
                text(child(child(item, "value"), "Friendship"), "Points")
            )
            for item in children(player, "friendshipData")
        },
        "fish_species": dictionary_keys(player, "fishCaught"),
        "tool_level": max(
            (
                int(text(e, "upgradeLevel", "0"))
                for e in root.iter()
                if e.get(XSI_TYPE) in TOOLS and text(e, "upgradeLevel", "0").isdigit()
            ),
            default=0,
        ),
        "bundles_complete": completed_bundles(root),
        "areas_complete": [
            i for i, flag in enumerate(areas) if (flag.text or "").strip() == "true"
        ],
    }
