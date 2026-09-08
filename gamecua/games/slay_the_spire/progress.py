"""Scoring predicates read from the game-written autosave and run history."""

import json

from .saves import decode_autosave

VERSION = "sts-progress-5"
BOSS_FLOORS = (16, 33, 50)
FLOOR_STEPS = (5, 7, 9, 11, 13, 19, 22, 25)
DEPTH_STEPS = (2, 3, 4, 6, 8, 10, 12, 14, 15, 17, 18, 20, 21, 23, 24)
UNCOMMON = {
    "Battle Trance",
    "Blood for Blood",
    "Bloodletting",
    "Burning Pact",
    "Carnage",
    "Combust",
    "Dark Embrace",
    "Disarm",
    "Dropkick",
    "Dual Wield",
    "Entrench",
    "Evolve",
    "Feel No Pain",
    "Fire Breathing",
    "Flame Barrier",
    "Ghostly Armor",
    "Hemokinesis",
    "Infernal Blade",
    "Inflame",
    "Intimidate",
    "Metallicize",
    "Power Through",
    "Pummel",
    "Rage",
    "Rampage",
    "Reckless Charge",
    "Rupture",
    "Searing Blow",
    "Second Wind",
    "Seeing Red",
    "Sentinel",
    "Sever Soul",
    "Shockwave",
    "Spot Weakness",
    "Uppercut",
    "Whirlwind",
}
RARE = {
    "Barricade",
    "Berserk",
    "Bludgeon",
    "Brutality",
    "Corruption",
    "Demon Form",
    "Double Tap",
    "Exhume",
    "Feed",
    "Fiend Fire",
    "Immolate",
    "Impervious",
    "Juggernaut",
    "Limit Break",
    "Offering",
    "Reaper",
}
PREDICATES = {
    *(f"floor_{n}" for n in FLOOR_STEPS),
    "combat_victory",
    "elite_victory",
    "act_1_boss_reached",
    "act_2_boss_reached",
    "act_1_complete",
    "act_2_complete",
    "act_3_complete",
    "run_victory",
    *(f"depth_{n}" for n in DEPTH_STEPS),
    *(f"kills_{n}" for n in (5, 10)),
    "elite_kills_2",
    *(f"relics_{n}" for n in (2, 3, 4, 5, 6)),
    "boss_relic",
    *(f"gold_gained_{n}" for n in (150, 300, 500)),
    *(f"max_hp_{n}" for n in (85, 90)),
    *(f"deck_{n}" for n in (13, 16, 20)),
    *(f"upgrades_{n}" for n in (1, 3, 5)),
    "card_removed",
    "uncommon_card",
    "rare_card",
    *(f"potions_{n}" for n in (1, 2, 3)),
    "potion_used",
    "rested",
    "smithed",
    "shop_purchase",
    *(f"events_{n}" for n in (1, 3)),
    "flawless_combat",
}


def facts(kind, raw, initial):
    data = decode_autosave(raw) if kind == "save" else json.loads(raw)
    seed = data.get("seed") if kind == "save" else data.get("seed_played")
    if str(seed) != str(initial["seed"]):
        raise ValueError("Evidence seed differs from verified setup")
    result = set()
    dead = kind == "history" and data.get("victory") is False and bool(data.get("killed_by"))
    won = kind == "history" and data.get("victory") is True
    act = int(data.get("act_num", 0))
    floor = int(data.get("floor_num", data.get("floor_reached", 0)))
    damage = data.get("metric_damage_taken" if kind == "save" else "damage_taken", [])
    new_combats = [m for m in damage if m not in initial.get("metric_damage_taken", [])]
    if kind == "save":
        if (
            data.get("post_combat")
            and data.get("current_health", 0) > 0
            and int(data.get("monsters_killed", 0)) > int(initial.get("monsters_killed", 0))
            and any(m.get("floor") == floor for m in new_combats)
        ):
            result.add("combat_victory")
    elif won:
        result.add("combat_victory")
    if any(
        int(data.get(f"elites{a}_killed", 0)) > int(initial.get(f"elites{a}_killed", 0))
        for a in (1, 2, 3)
    ):
        result.add("elite_victory")
    for a in (1, 2, 3):
        baseline_act = int(initial.get("act_num", 1))
        boss_save = (
            kind == "save"
            and act == a
            and data.get("post_combat")
            and data.get("current_health", 0) > 0
            and data.get("current_room", "").endswith(".MonsterRoomBoss")
            and any(m.get("floor") == floor for m in new_combats)
        )
        history_passed = kind == "history" and (won or floor > BOSS_FLOORS[a - 1])
        if a >= baseline_act and (act > a or boss_save or history_passed):
            result.add(f"act_{a}_complete")
    alive = kind == "history" or data.get("current_health", 0) > 0
    start_floor = int(initial.get("floor_num", 0))
    for a in (1, 2):
        if floor >= BOSS_FLOORS[a - 1] and start_floor < BOSS_FLOORS[a - 1] and alive:
            result.add(f"act_{a}_boss_reached")
    for n in FLOOR_STEPS:
        if floor >= n and start_floor < n and alive:
            result.add(f"floor_{n}")
    for n in DEPTH_STEPS:
        if floor >= n and start_floor < n and alive:
            result.add(f"depth_{n}")
    killed = int(data.get("monsters_killed", 0)) - int(initial.get("monsters_killed", 0))
    for n in (5, 10):
        if kind == "save" and killed >= n:
            result.add(f"kills_{n}")
    elites = sum(int(data.get(f"elites{a}_killed", 0)) for a in (1, 2, 3))
    elites -= sum(int(initial.get(f"elites{a}_killed", 0)) for a in (1, 2, 3))
    if elites >= 2:
        result.add("elite_kills_2")
    if any(m.get("damage", 1) == 0 for m in new_combats):
        result.add("flawless_combat")
    result |= collection(kind, data, initial)
    if won:
        result.add("run_victory")
    return result, "victory" if won else "death" if dead else None


def collection(kind, data, initial):
    result = set()
    save = kind == "save"
    prefix = "metric_" if save else ""

    def metric(name):
        return data.get(prefix + name, [])

    if save:
        deck = [(c["id"], int(c.get("upgrades", 0))) for c in data.get("cards", [])]
        relics = data.get("relics", [])
        gold_gained = int(data.get("gold_gained", 0)) - int(initial.get("gold_gained", 0))
        max_hp = int(data.get("max_health", 0))
    else:
        deck = []
        for entry in data.get("master_deck", []):
            name, _, plus = entry.partition("+")
            deck.append((name, int(plus or 0)))
        relics = data.get("relics", [])
        gold_per_floor = data.get("gold_per_floor", [])
        gold_gained = sum(max(0, b - a) for a, b in zip(gold_per_floor, gold_per_floor[1:]))
        max_hp = max(data.get("max_hp_per_floor", [0]) or [0])
    for n in (2, 3, 4, 5, 6):
        if len(relics) >= n:
            result.add(f"relics_{n}")
    if metric("boss_relics"):
        result.add("boss_relic")
    for n in (150, 300, 500):
        if gold_gained >= n:
            result.add(f"gold_gained_{n}")
    for n in (85, 90):
        if max_hp >= n:
            result.add(f"max_hp_{n}")
    for n in (13, 16, 20):
        if len(deck) >= n:
            result.add(f"deck_{n}")
    upgrades = sum(1 for _, u in deck if u > 0)
    for n in (1, 3, 5):
        if upgrades >= n:
            result.add(f"upgrades_{n}")
    ids = {name for name, _ in deck}
    if ids & UNCOMMON:
        result.add("uncommon_card")
    if ids & RARE:
        result.add("rare_card")
    if metric("items_purged"):
        result.add("card_removed")
    potions = metric("potions_obtained")
    for n in (1, 2, 3):
        if len(potions) >= n:
            result.add(f"potions_{n}")
    if metric("potions_floor_usage"):
        result.add("potion_used")
    choices = metric("campfire_choices")
    if any(c.get("key") == "REST" for c in choices):
        result.add("rested")
    if any(c.get("key") == "SMITH" for c in choices):
        result.add("smithed")
    if metric("items_purchased"):
        result.add("shop_purchase")
    events = metric("event_choices")
    for n in (1, 3):
        if len(events) >= n:
            result.add(f"events_{n}")
    return result
