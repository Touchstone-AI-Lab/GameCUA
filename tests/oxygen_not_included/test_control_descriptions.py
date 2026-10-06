"""ONI rendered control references must describe executable inputs and their bounds."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from gamecua.actions import validate
from gamecua.catalog import Catalog
from gamecua.trials import policy_prompt

PROFILE = Catalog(Path(__file__).resolve().parents[2] / "benchmarks").inputs["oni-pointer-v3"]


@pytest.mark.parametrize("mode", ["live", "frozen_steps"])
def test_rendered_control_keys_match_executable_profile(mode):
    prompt = policy_prompt(SimpleNamespace(action_execution=mode, step_seconds=1), PROFILE)
    for name, button in PROFILE.groups["input"].buttons.items():
        if not button.keys:
            continue
        line = next(line for line in prompt.splitlines() if line.startswith(f"  {name}: "))
        key = re.search(r"Press (\w+) to", line).group(1)
        assert [key] == button.keys
        assert validate({"type": "control", "keys": [key]})["keys"] == button.keys
    with pytest.raises(ValueError, match="supported controls"):
        validate({"type": "control", "keys": ["pause"]})


@pytest.mark.parametrize(
    "label,action,field",
    [
        ("control duration", {"type": "control", "keys": ["space"]}, "duration"),
        ("drag duration", {"type": "drag", "x": 0, "y": 0, "to_x": 1, "to_y": 1}, "duration"),
        ("wait seconds", {"type": "wait"}, "seconds"),
    ],
)
def test_disclosed_action_bounds_match_validator(label, action, field):
    prompt = policy_prompt(SimpleNamespace(action_execution="live"), PROFILE)
    match = re.search(rf"{label} is ([\d.]+)\.\.([\d.]+)", prompt)
    low, high = map(float, match.groups())
    for value in (low, high):
        assert validate({**action, field: value})[field] == value
    for value in (low - 0.001, high + 0.001):
        with pytest.raises(ValueError, match="Expected finite number"):
            validate({**action, field: value})
