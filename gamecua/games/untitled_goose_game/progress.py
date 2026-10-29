"""Native task milestones from game-written slot saves."""

from .saves import GOALS, read_save

VERSION = "untitled-goose-game-native-save-2"
PREDICATES = set(GOALS)


def facts(kind, raw, initial):
    """Return newly completed native goals and victory once the finale is completed."""
    if kind != "save":
        return set(), None
    earned = set(read_save(raw)["completed"]) - set(initial["completed"])
    return earned, "victory" if "goalFinale" in earned else None
