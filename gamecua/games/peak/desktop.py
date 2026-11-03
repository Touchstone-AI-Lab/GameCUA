"""Deterministic PEAK keyboard aliases for the shared model input profile."""

from ...actions import validate
from ...desktop import X11Desktop

LOOK_PIXELS_PER_SECOND = 600
ALIASES = {"Left", "Right", "Up", "Down", "j", "k"}


def translate(action):
    """Turn arrow aliases into mouse motion and J/K into held mouse buttons."""
    action = validate(action)
    if action["type"] != "control":
        return action
    keys = set(action["keys"])
    if not keys & ALIASES:
        return action
    action["keys"] = [key for key in action["keys"] if key not in ALIASES]
    distance = LOOK_PIXELS_PER_SECOND * action["duration"]
    action["dx"] += distance * (("Right" in keys) - ("Left" in keys))
    action["dy"] += distance * (("Down" in keys) - ("Up" in keys))
    for key, button in (("j", "left"), ("k", "right")):
        if key in keys and button not in action["buttons"]:
            action["buttons"].append(button)
    if not (action["keys"] or action["buttons"] or action["dx"] or action["dy"]):
        return {"type": "wait", "seconds": action["duration"]}
    return validate(action)


class Desktop(X11Desktop):
    """X11 desktop that applies the PEAK aliases before executing an action."""

    def _execute(self, action, *, stop=None, deadline=None):
        return super()._execute(translate(action), stop=stop, deadline=deadline)
