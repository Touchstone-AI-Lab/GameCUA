"""Loads the game, model, rubric, Trial and input-profile configurations of a catalog directory."""

import hashlib
import json
from pathlib import Path

from .specs import GameSpec, InputProfile, ModelSpec, Rubric, TrialSpec

KINDS = {
    "games": GameSpec,
    "models": ModelSpec,
    "rubrics": Rubric,
    "trials": TrialSpec,
    "inputs": InputProfile,
}


def digest(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class Catalog:
    def __init__(self, root):
        self.root = Path(root)
        for kind, schema in KINDS.items():
            items = (
                schema.model_validate_json(path.read_text())
                for path in sorted((self.root / kind).rglob("*.json"))
            )
            setattr(self, kind, {item.id: item for item in items})

    def pause_gaps(self):
        return sorted(
            game.id
            for game in self.games.values()
            if game.status == "verified" and game.timing == "realtime" and game.pause is None
        )
