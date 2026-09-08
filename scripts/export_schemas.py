"""Regenerate published JSON Schemas after changing the Python contracts."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamecua.specs import (
    GameSpec,
    InputProfile,
    Milestone,
    ModelSpec,
    Rubric,
    TrialRecord,
    TrialSpec,
)

if __name__ == "__main__":
    target = ROOT / "benchmarks/schemas"
    target.mkdir(exist_ok=True)
    for schema in (
        GameSpec,
        InputProfile,
        ModelSpec,
        Milestone,
        Rubric,
        TrialSpec,
        TrialRecord,
    ):
        (target / (schema.__name__ + ".schema.json")).write_text(
            json.dumps(schema.model_json_schema(), indent=2) + "\n"
        )
