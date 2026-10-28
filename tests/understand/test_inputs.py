"""Regression checks for native hit regions and ordinary input semantics; no puzzle solutions."""

import json
from pathlib import Path

from gamecua.actions import pixel
from gamecua.catalog import Catalog
from gamecua.models.typesafe import parse_answers
from gamecua.typed import merge, questions

ROOT = Path(__file__).resolve().parents[2]
HITBOXES = json.loads((ROOT / "tests/fixtures/understand/input-hitboxes.json").read_text())


def cell(point, board):
    x, y = pixel(*point, *HITBOXES["resolution"])
    x = (x - board["left"]) // board["cell_size"] + 1
    y = (y - board["top"]) // board["cell_size"] + 1
    if 1 <= x <= board["columns"] and 1 <= y <= board["rows"]:
        return x, y
    return None


def test_current_profile_uses_native_boxes_for_targets_and_keeps_buttonless_motion():
    profile = Catalog(ROOT / "benchmarks").inputs["understand-pointer-v3"]
    asked = questions(profile)
    boxes = [name for name, question in asked.items() if question["type"] == "box"]
    assert set(boxes) == {"pointer_left", "pointer_move", "pointer_drag_from", "pointer_drag_to"}
    buttons = profile.groups["input"].buttons
    assert set(asked["input"]["criteria"]) == set(buttons)
    points = {
        "pointer_left": (0.425, 0.45),
        "pointer_move": (0.575, 0.45),
        "pointer_drag_from": (0.425, 0.45),
        "pointer_drag_to": (0.575, 0.45),
    }
    for choice in buttons:
        response = {
            "model": "jev-1.14.0",
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "answers": {
                "input": {
                    "type": "choice",
                    "choice": choice,
                    "probabilities": {name: float(name == choice) for name in buttons},
                    "confidence": 1.0,
                },
                **{
                    name: {
                        "type": "box",
                        "confidence": None,
                        "box": {
                            "left": x - 0.01,
                            "right": x + 0.01,
                            "top": y - 0.01,
                            "bottom": y + 0.01,
                        },
                    }
                    for name, (x, y) in points.items()
                },
            },
        }
        answers, _, _ = parse_answers(response, {"input": set(buttons)}, boxes)
        action = merge(profile, answers)
        if buttons[choice].pointer == "move":
            assert "button" not in action
            assert cell((action["x"], action["y"]), HITBOXES["boards"]["three_by_one"]) == (3, 1)
        elif buttons[choice].pointer == "drag":
            assert cell((action["x"], action["y"]), HITBOXES["boards"]["three_by_one"]) == (1, 1)
            assert cell((action["to_x"], action["to_y"]), HITBOXES["boards"]["three_by_one"]) == (
                3,
                1,
            )
        else:
            assert action["button"] == "left"


def test_standard_cohorts_share_controls_and_use_standard_transports():
    catalog = Catalog(ROOT / "benchmarks")
    llm = catalog.trials["understand-ending-v2-live-3h"]
    jev = catalog.trials["understand-jev-ending-v2-live-1h"]
    assert llm.inputs_id == jev.inputs_id == "understand-pointer-v3"
    assert llm.agent is None and jev.agent is None
    assert llm.total_seconds == 10800 and jev.total_seconds == 600
    assert llm.model_id == "deepseek-v41-flash-thinking" and jev.model_id == "jev-1-14"
    assert llm.rubric_id == jev.rubric_id == "understand-route-panels-v4"
    buttons = catalog.inputs[llm.inputs_id].groups["input"].buttons
    assert {button.pointer for button in buttons.values()} == {"left", "move", "drag"}
    assert all(button.click is None and button.drag is None for button in buttons.values())
