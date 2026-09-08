"""Every canonical action type is reachable from an input profile, so a Jev profile can express it."""

import json

import pytest

from gamecua.actions import KINDS
from gamecua.specs import InputProfile
from gamecua.typed import describe_profile, merge


def load(value):
    return InputProfile.model_validate_json(json.dumps(value))


PROFILE = load(
    {
        "schema_version": 1,
        "id": "pointer-kinds-v1",
        "game_id": "demo",
        "version": 1,
        "step_seconds": 0.5,
        "instructions": "Pick one input.",
        "groups": {
            "pointer": {
                "buttons": {
                    "hover": {"description": "Click the middle.", "click": [0.5, 0.5]},
                    "file": {
                        "description": "Drag the file to the tray.",
                        "drag": [0.1, 0.2, 0.8, 0.9],
                    },
                    "down": {"description": "Scroll down.", "scroll": -3},
                    "up": {"description": "Scroll up.", "scroll": 2},
                }
            },
            "keys": {
                "buttons": {
                    "none": {"description": "Hold nothing."},
                    "space": {"description": "Hold space.", "keys": ["space"]},
                }
            },
        },
    }
)


def decide(pointer, keys="none"):
    return merge(PROFILE, {"pointer": {"choice": pointer}, "keys": {"choice": keys}})


def test_every_canonical_action_type_is_reachable_from_a_profile():
    reached = {
        decide("hover")["type"],
        decide("file")["type"],
        decide("down")["type"],
        merge(
            PROFILE.model_copy(update={"groups": {"keys": PROFILE.groups["keys"]}}),
            {"keys": {"choice": "space"}},
        )["type"],
        merge(
            PROFILE.model_copy(update={"groups": {"keys": PROFILE.groups["keys"]}}),
            {"keys": {"choice": "none"}},
        )["type"],
    }
    assert reached == set(KINDS)


def test_drag_and_scroll_buttons_become_actions():
    assert decide("file") == {
        "type": "drag",
        "x": 0.1,
        "y": 0.2,
        "to_x": 0.8,
        "to_y": 0.9,
        "duration": 0.5,
    }
    assert decide("down") == {"type": "scroll", "steps": -3}
    assert decide("up", "space") == {"type": "scroll", "steps": 2}


def test_two_pointer_choices_are_rejected():
    profile = PROFILE.model_dump(mode="json")
    profile["groups"]["second"] = {
        "buttons": {
            "drag": profile["groups"]["pointer"]["buttons"]["file"],
            "idle": {"description": "Nothing."},
        }
    }
    with pytest.raises(Exception, match="More than one pointer choice"):
        merge(
            load(profile),
            {
                "pointer": {"choice": "hover"},
                "keys": {"choice": "none"},
                "second": {"choice": "drag"},
            },
        )


def test_unused_fields_stay_out_of_stored_profiles_and_the_controls_reference_lists_targets():
    stored = PROFILE.model_dump(mode="json")["groups"]["keys"]["buttons"]["space"]
    assert "drag" not in stored and "scroll" not in stored
    text = describe_profile(PROFILE)
    assert "1 click targets" in text and "1 drag targets" in text
    assert "down: Scroll down." in text
