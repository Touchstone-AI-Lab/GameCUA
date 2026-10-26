"""Award progress only from fields that preserved native saves newly record; a recorded ending is the run's verified completion and a save written at zero health is a native death."""

from .saves import decode_save

VERSION = "silksong-native-save-6"
FLAGS = {
    "moss_mother_encountered": "encounteredMossMother",
    "moss_mother_defeated": "defeatedMossMother",
    "bone_bottom_visited": "visitedBoneBottom",
    "bone_forest_visited": "visitedBoneForest",
    "bell_bench_activated": "hasActivatedBellBench",
    "mosstown_visited": "visitedMosstown",
    "bell_beast_encountered": "encounteredBellBeast",
    "bell_beast_defeated": "defeatedBellBeast",
}
NEW_SCENES = (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16)
MARKS = {
    "moss_cave_visited": "visitedMossCave",
    "deep_docks_visited": "visitedDeepDocks",
    "bone_gate_opened": "greatBoneGateOpened",
    "swift_step_gained": "hasDash",
}
STEPS = {
    "enemy_kinds": (1, 2, 3, 4, 5, 6, 8, 10, 12),
    "enemy_kills": (5, 10, 25, 50, 100),
    "shell_shards": (10, 25, 50, 100, 200),
    "rosaries": (1, 20),
    "items": (1,),
    "tools": (1,),
    "wishes": (1,),
    "npcs": (1, 3),
}
BENCH_RESPAWN = 1
PREDICATES = (
    set(FLAGS)
    | set(MARKS)
    | {f"new_scenes_{count}" for count in NEW_SCENES}
    | {f"{name}_{count}" for name, counts in STEPS.items() for count in counts}
    | {"bench_rested", "silkspear_gained"}
)


def summary(raw):
    """Record the story flags, endings and scenes of the setup save."""
    player = decode_save(raw)["playerData"]
    return {
        "flags": {field: player[field] for field in FLAGS.values()},
        "endings": player["CompletedEndings"],
        "scenes": sorted(set(player["scenesVisited"])),
    }


def tally(player):
    """Count journal kills, collections, characters met and other absolute marks."""
    kills = [entry["Record"]["Kills"] for entry in player["EnemyJournalKillData"]["list"]]
    tools = player["Tools"]["savedData"]
    return {
        **{field: player[field] for field in MARKS.values()},
        "bench_rested": player["respawnType"] == BENCH_RESPAWN,
        "silkspear_gained": player["hasNeedleThrow"]
        or any(t["Name"] == "Silk Spear" and t["Data"].get("IsUnlocked") is True for t in tools),
        "enemy_kinds": sum(1 for count in kills if count > 0),
        "enemy_kills": sum(kills),
        "shell_shards": player["ShellShards"],
        "rosaries": player["geo"] + player["HeroCorpseMoneyPool"],
        "items": len(player["Collectables"]["savedData"]),
        "tools": sum(1 for t in tools if t["Data"].get("IsUnlocked") is True),
        "wishes": sum(
            1
            for item in player["QuestCompletionData"]["savedData"]
            if item["Data"].get("IsAccepted") is True
        ),
        "npcs": sum(
            1 for name, value in player.items() if name[:3] in ("met", "Met") and value is True
        ),
    }


def facts(kind, raw, initial):
    """Return the predicates a preserved save newly shows and its terminal outcome."""
    player = decode_save(raw)["playerData"]
    found = {name for name, field in FLAGS.items() if player[field] and not initial["flags"][field]}
    new = len(set(player["scenesVisited"]) - set(initial["scenes"]))
    found |= {f"new_scenes_{count}" for count in NEW_SCENES if new >= count}
    counts = tally(player)
    found |= {name for name, field in MARKS.items() if counts[field]}
    found |= {name for name in ("bench_rested", "silkspear_gained") if counts[name]}
    found |= {
        f"{name}_{count}"
        for name, steps in STEPS.items()
        for count in steps
        if counts[name] >= count
    }
    if player["CompletedEndings"] & ~initial["endings"]:
        return found, "victory"
    return found, "death" if player["health"] == 0 else None
