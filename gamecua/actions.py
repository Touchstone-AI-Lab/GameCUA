"""Five canonical action types; the eleven pre-2026-10-25 types are accepted and rewritten into them so stored evidence and game scripts keep validating."""

import math

KINDS = ("pointer", "drag", "control", "scroll", "wait")
KEYS = tuple("abcdefghijklmnopqrstuvwxyz0123456789") + (
    "space",
    "Return",
    "Escape",
    "Tab",
    "Up",
    "Down",
    "Left",
    "Right",
    "Shift_L",
    "Control_L",
)
BUTTONS = ("left", "right")
CANONICAL_KEYS = {key.lower(): key for key in KEYS}
FIELDS = {
    "pointer": {"type", "x", "y", "button"},
    "drag": {"type", "x", "y", "to_x", "to_y", "duration"},
    "control": {"type", "keys", "buttons", "dx", "dy", "duration"},
    "scroll": {"type", "steps"},
    "wait": {"type", "seconds"},
}
TAP_SECONDS = 0.1


def number(v, low, high):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"Expected finite number in [{low}, {high}]")
    if not low <= v <= high:
        raise ValueError(f"Expected finite number in [{low}, {high}]")
    return float(v)


def canonical_key(key):
    return CANONICAL_KEYS.get(key.lower(), key) if isinstance(key, str) else key


LEGACY_FIELDS = {
    "move": {"type", "x", "y"},
    "click": {"type", "x", "y", "button"},
    "press": {"type", "key"},
    "hold": {"type", "key", "duration"},
    "keys": {"type", "keys", "duration"},
    "mouse_hold": {"type", "button", "duration"},
    "relative_move": {"type", "dx", "dy"},
}


def legacy(a):
    kind = a.get("type")
    if kind in LEGACY_FIELDS and set(a) - LEGACY_FIELDS[kind]:
        raise ValueError("Unexpected action fields")
    if kind == "move":
        return {"type": "pointer", "x": a.get("x"), "y": a.get("y")}
    if kind == "click":
        return {
            "type": "pointer",
            "x": a.get("x"),
            "y": a.get("y"),
            "button": a.get("button", "left"),
        }
    if kind in ("press", "hold"):
        return {
            "type": "control",
            "keys": [a.get("key")],
            "duration": a.get("duration", TAP_SECONDS),
        }
    if kind == "keys":
        return {"type": "control", "keys": a.get("keys"), "duration": a.get("duration")}
    if kind == "mouse_hold":
        return {"type": "control", "buttons": [a.get("button")], "duration": a.get("duration")}
    if kind == "relative_move":
        return {"type": "control", "dx": a.get("dx"), "dy": a.get("dy")}
    return a


def distinct(items, allowed, limit):
    if (
        not isinstance(items, list)
        or len(items) > limit
        or any(item not in allowed for item in items)
        or len(set(items)) != len(items)
    ):
        raise ValueError("Supply distinct supported controls")
    return items


def validate(action):
    if not isinstance(action, dict):
        raise ValueError("Unknown action type")
    a = legacy(dict(action))
    kind = a.get("type")
    if kind not in KINDS:
        raise ValueError("Unknown action type")
    if set(a) - FIELDS[kind]:
        raise ValueError("Unexpected action fields")
    if kind in ("pointer", "drag"):
        a["x"], a["y"] = number(a.get("x"), 0, 1), number(a.get("y"), 0, 1)
    if kind == "pointer" and "button" in a and a["button"] not in BUTTONS:
        raise ValueError("Unsupported button")
    if kind == "drag":
        a["to_x"], a["to_y"] = number(a.get("to_x"), 0, 1), number(a.get("to_y"), 0, 1)
        a["duration"] = number(a.get("duration", 0.5), 0.1, 2)
    if kind == "control":
        keys = a.get("keys") or []
        a["keys"] = distinct(
            [canonical_key(k) for k in keys] if isinstance(keys, list) else keys, KEYS, 8
        )
        a["buttons"] = distinct(a.get("buttons") or [], BUTTONS, 2)
        a["dx"] = number(a.get("dx") or 0, -2048, 2048)
        a["dy"] = number(a.get("dy") or 0, -2048, 2048)
        a["duration"] = number(a.get("duration") or TAP_SECONDS, 0.05, 3)
        if not (a["keys"] or a["buttons"] or a["dx"] or a["dy"]):
            raise ValueError("Control needs keys, buttons or movement")
    if kind == "scroll" and (type(a.get("steps")) is not int or not 1 <= abs(a["steps"]) <= 8):
        raise ValueError("Scroll requires one to eight signed steps")
    if kind == "wait":
        a["seconds"] = number(a.get("seconds"), 0.1, 5)
    return a


def pixel(x, y, width, height):
    return round(x * (width - 1)), round(y * (height - 1))
