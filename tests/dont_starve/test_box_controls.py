"""Synthetic checks for the 0.7.4 Box profile; these are not benchmark outcomes."""

from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.trials import Trial
from gamecua.typed import merge, questions

CATALOG = Catalog(Path(__file__).parents[2] / "benchmarks")
PROFILE = CATALOG.inputs["dont-starve-controls-v5"]


def test_current_profile_activates_all_native_box_questions():
    asked = questions(PROFILE)
    assert set(asked) == {
        "action",
        "pointer_left",
        "pointer_right",
        "pointer_move",
        "pointer_drag_from",
        "pointer_drag_to",
    }
    assert all(value["type"] == "box" for key, value in asked.items() if key != "action")
    old = CATALOG.inputs["dont-starve-controls-v4"].groups["action"].buttons
    current = PROFILE.groups["action"].buttons
    assert len(current) == 31
    for name, button in old.items():
        if button.click is None:
            assert current[name] == button
    assert all(button.click is None and button.drag is None for button in current.values())


@pytest.mark.parametrize(
    "choice,expected",
    [
        ("click_target", {"type": "pointer", "x": 0.25, "y": 0.375, "button": "left"}),
        ("secondary_target", {"type": "pointer", "x": 0.25, "y": 0.375, "button": "right"}),
        ("point_target", {"type": "pointer", "x": 0.25, "y": 0.375}),
        (
            "drag_target",
            {
                "type": "drag",
                "x": 0.25,
                "y": 0.375,
                "to_x": 0.75,
                "to_y": 0.875,
                "duration": 2.0,
            },
        ),
    ],
)
def test_game_choices_use_observed_boxes_instead_of_fixed_grid_points(choice, expected):
    source = {"left": 0.125, "right": 0.375, "top": 0.25, "bottom": 0.5}
    destination = {"left": 0.625, "right": 0.875, "top": 0.75, "bottom": 1.0}
    answers = {"action": {"choice": choice}} | {
        name: {"box": destination if name == "pointer_drag_to" else source}
        for name in questions(PROFILE)
        if name != "action"
    }
    assert merge(PROFILE, answers) == expected


@pytest.mark.parametrize("mode", ["live", "frozen"])
def test_jev_specs_share_boxes_and_keep_targets_out_of_play(tmp_path, mode):
    spec = CATALOG.trials[f"dont-starve-survival-v5-jev-{mode}-2h"]
    assert spec.total_seconds == 7200 and spec.episode_limit == 1
    assert spec.step_seconds == (3 if mode == "frozen" else None)
    assert spec.inputs_id == PROFILE.id
    assert spec.rubric_id == "dont-starve-survival-collection-v6"
    trial = Trial(
        tmp_path / "trial",
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
        inputs=PROFILE,
    )
    playing = (trial.root / "system_prompt.txt").read_text()
    assert "1792983405" not in playing
    assert "Long Day" not in playing
    assert all(milestone.description not in playing for milestone in trial.rubric.milestones)
