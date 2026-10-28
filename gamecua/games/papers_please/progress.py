"""Awards from original encrypted native stashes and daily saves, never agent claims."""

import json

from .haxe import read
from .saves import plaintext, read_save

VERSION = "papers-please-native-xxtea-haxe-9"
DAYS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 23, 26, 29)
THRESHOLDS = {
    "processed": (5, 10, 15, 20, 30, 45, 60, 80, 100, 120, 140, 150),
    "correct": (10, 25, 30, 45, 70, 95, 120, 150),
    "approved": (10, 25, 50, 75),
    "denied": (10, 15, 25, 35, 50),
    "stamps": (25, 50, 85, 120),
}
PREDICATES = (
    {f"{name}_{n}" for name, steps in THRESHOLDS.items() for n in steps}
    | {f"reach_day_{n}" for n in DAYS}
    | {"story_success"}
)
SUCCESS_ENDINGS = {"escape", "ignore-ezic", "help-ezic-hold-fire"}


def story(values, day, end_id=None):
    """Summarize native story facts for one workday or ending screen."""
    counters = {
        key.removeprefix("Game/Stat/"): int(value)
        for key, value in values.items()
        if key.startswith("Game/Stat/Num")
    }
    processed = counters.get("NumProcessed", 0)
    return {
        "day": day,
        "processed": processed,
        "correct": processed - counters.get("NumCitations", 0),
        "counters": counters,
        "end_id": end_id,
    }


def state(raw, decoder_key):
    """Read the encrypted native stash written during a workday or at an ending."""
    root = read(plaintext(raw, decoder_key).decode("utf-8"))
    values = {
        key: value["value"]["text"]
        for key, value in root["storyStateFacts"]["facts"].items()
        if key == "Game/Day" or key.startswith("Game/Stat/Num")
    }
    if root["day"] is None:
        return story(values, int(values["Game/Day"]), root["endId"])
    return story(values, root["day"]["id"])


def day_state(raw, decoder_key):
    """Read the encrypted native daily story facts save."""
    values = {item.get("p"): item.get("v", "") for item in read_save(raw, decoder_key)}
    return story(values, int(values["Game/Day"]))


def facts(kind, raw, initial):
    """Return the predicates a preserved native proof shows and its terminal outcome."""
    proof = json.loads(raw)
    key = bytes.fromhex(initial["decoder_key"])
    current = (
        state(proof["stash"].encode(), key)
        if kind == "history"
        else day_state(proof["save"].encode(), key)
    )
    counters = current["counters"]
    values = {
        "processed": current["processed"] - initial["processed"],
        "correct": current["correct"],
        "approved": counters.get("NumApproved", 0),
        "denied": counters.get("NumDenied", 0),
        "stamps": counters.get("NumStamps", 0),
    }
    found = {
        f"{name}_{n}" for name, steps in THRESHOLDS.items() for n in steps if values[name] >= n
    }
    if values["processed"] > 0:
        found |= {f"reach_day_{n}" for n in DAYS if current["day"] >= n}
    if current["end_id"] is None:
        return found, None
    if current["end_id"] in SUCCESS_ENDINGS:
        return found | {"story_success"}, "victory"
    return found, "death"
