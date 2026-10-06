"""Scoring predicates use game-written save evidence, never playing-agent claims."""

from .saves import read_save

VERSION = "stardew-progress-6"
PLACES = {
    "bus_stop": "BusStop",
    "town": "Town",
    "beach": "Beach",
    "forest": "Forest",
    "mountain": "Mountain",
    "backwoods": "Backwoods",
    "general_store": "SeedShop",
    "blacksmith": "Blacksmith",
    "museum": "ArchaeologyHouse",
    "fish_shop": "FishShop",
    "ranch": "AnimalShop",
    "carpenter": "ScienceHouse",
    "community_center": "CommunityCenter",
    "wizard_tower": "WizardHouse",
}
SKILLS = {
    "farming": "farmingLevel",
    "fishing": "fishingLevel",
    "foraging": "foragingLevel",
    "mining": "miningLevel",
    "combat": "combatLevel",
}
FIRSTS = {
    "soil_tilled": "dirt_hoed",
    "seeds_sown": "seeds_sown",
    "crop_harvested": "farming_experience",
    "crop_shipped": "crops_shipped",
    "copper_ore_found": "copper_found",
    "furnace_crafted": "furnaces_crafted",
    "first_cast": "times_fished",
    "first_income": "totalMoneyEarned",
}
COUNTS = {
    "earned": ("totalMoneyEarned", (250, 500, 1000, 2500, 5000)),
    "seeds_sown": ("seeds_sown", (20, 50)),
    "crops_shipped": ("crops_shipped", (15,)),
    "quests_completed": ("quests_completed", (1, 3, 5)),
    "items_foraged": ("items_foraged", (1, 10, 30)),
    "monsters_killed": ("monsters_killed", (1, 10)),
    "gifts_given": ("gifts_given", (1, 5)),
    "museum_donations": ("museum_pieces", (1, 3, 5)),
}
COLLECTIONS = {
    "shipped_items": ("items_shipped", (3, 5, 8, 10, 15, 20)),
    "fish_species": ("fish_species", (2, 3, 8)),
    "minerals": ("minerals_found", (1, 3, 5)),
    "artifacts": ("artifacts_found", (1, 2)),
    "crafted_recipes": ("crafted_recipes", (1, 3, 5)),
}
TIERS = {
    "backpack_upgraded": ("maxItems", 24),
    "copper_tool": ("tool_level", 1),
    **{f"mine_level_{n}": ("deepestMineLevel", n) for n in (1, 5, 10, 15, 20, 30, 40)},
}
MAIL = {
    "junimo_scroll_seen": "seenJunimoNote",
    "junimo_text_readable": "canReadJunimoText",
    "cc_door_unlocked": "ccDoorUnlock",
}
VILLAGERS_MET = (3, 5, 10, 15, 20)
HEART = 250
PREDICATES = {
    *FIRSTS,
    *(f"{name}_{n}" for name, (_, steps) in COUNTS.items() for n in steps),
    *(f"{name}_{n}" for name, (_, steps) in COLLECTIONS.items() for n in steps),
    *TIERS,
    *MAIL,
    *(f"{skill}_level_{n}" for skill in SKILLS for n in (1, 2, 3)),
    *(f"visited_{place}" for place in PLACES),
    *(f"villagers_met_{n}" for n in VILLAGERS_MET),
    "first_fish",
    "fish_5_species",
    "first_bundle",
    "three_bundles",
    "first_room",
    "friend_1_heart",
    "friend_2_hearts",
    "friends_3_at_1_heart",
}


def facts(kind, raw, initial):
    """Return the predicates a save shows beyond the setup save, counting fields an older setup lacks from zero."""
    data = read_save(raw)
    result = {name for name, field in FIRSTS.items() if data[field] > initial[field]}
    for name, (field, steps) in COUNTS.items():
        result |= {f"{name}_{n}" for n in steps if data[field] - initial.get(field, 0) >= n}
    for name, (field, steps) in COLLECTIONS.items():
        gained = len(set(data[field]) - set(initial.get(field, ())))
        result |= {f"{name}_{n}" for n in steps if gained >= n}
    result |= {name for name, (field, n) in TIERS.items() if data[field] >= n > initial[field]}
    result |= {
        name
        for name, mail in MAIL.items()
        if mail in data["mail_received"] and mail not in initial["mail_received"]
    }
    for skill, field in SKILLS.items():
        result |= {
            f"{skill}_level_{n}"
            for n in (1, 2, 3)
            if data["skills"][field] >= n > initial["skills"][field]
        }
    visited = set(data["locations_visited"]) - set(initial.get("locations_visited", ()))
    result |= {f"visited_{place}" for place, name in PLACES.items() if name in visited}
    species = len(set(data["fish_species"]) - set(initial["fish_species"]))
    bundles = len(set(data["bundles_complete"]) - set(initial["bundles_complete"]))
    rooms = len(set(data["areas_complete"]) - set(initial["areas_complete"]))
    for name, gained, needed in (
        ("first_fish", species, 1),
        ("fish_5_species", species, 5),
        ("first_bundle", bundles, 1),
        ("three_bundles", bundles, 3),
        ("first_room", rooms, 1),
    ):
        if gained >= needed:
            result.add(name)
    before, points = initial["friendship_points"], data["friendship_points"]
    met = len(set(points) - set(before))
    result |= {f"villagers_met_{n}" for n in VILLAGERS_MET if met >= n}
    friends = [name for name, value in points.items() if value >= HEART > before.get(name, 0)]
    if friends:
        result.add("friend_1_heart")
    if len(friends) >= 3:
        result.add("friends_3_at_1_heart")
    if any(value >= 2 * HEART > before.get(name, 0) for name, value in points.items()):
        result.add("friend_2_hearts")
    return result, None
