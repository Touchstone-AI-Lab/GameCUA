"""Pointer buttons take their target from a native Box question in the same request; proven with an offline HTTP double."""

import json
import threading
from pathlib import Path

import httpx
import pytest
from PIL import Image

from gamecua.catalog import Catalog
from gamecua.models import create_client
from gamecua.provider import ProviderFailure, RetryPolicy
from gamecua.specs import InputProfile
from gamecua.typed import TypedAgent, describe_profile, merge, questions

MODEL = Catalog(Path(__file__).parents[2] / "benchmarks").models["jev-1-14"]
IMAGE = Image.new("RGB", (64, 36), (10, 20, 30))


def load(value):
    return InputProfile.model_validate_json(json.dumps(value))


PROFILE = load(
    {
        "schema_version": 1,
        "id": "box-pointer-v1",
        "game_id": "demo",
        "version": 1,
        "step_seconds": 0.5,
        "instructions": "Pick one input.",
        "groups": {
            "input": {
                "buttons": {
                    "click_target": {"description": "Left-click a target.", "pointer": "left"},
                    "inspect_target": {"description": "Right-click a target.", "pointer": "right"},
                    "hover_target": {"description": "Point at a target.", "pointer": "move"},
                    "confirm": {"description": "Press Return.", "keys": ["Return"]},
                }
            }
        },
    }
)
BOX = {"top": 0.2, "bottom": 0.4, "left": 0.5, "right": 0.7}


def answers(choice, box=BOX):
    return {
        "input": {"choice": choice, "probabilities": {}, "confidence": 0.9},
        **{f"pointer_{m}": {"box": box, "confidence": 0.8} for m in ("left", "right", "move")},
    }


def test_profile_adds_one_box_question_per_pointer_kind():
    asked = questions(PROFILE)
    assert set(asked) == {"input", "pointer_left", "pointer_right", "pointer_move"}
    assert all(asked[f"pointer_{m}"]["type"] == "box" for m in ("left", "right", "move"))
    assert "criteria" not in asked["pointer_left"]
    assert "current screenshot" in asked["pointer_left"]["instructions"]
    assert "click_target: Left-click a target." in describe_profile(PROFILE)


def test_profiles_without_pointer_buttons_ask_no_box_question():
    profile = PROFILE.model_dump(mode="json")
    profile["groups"]["input"]["buttons"] = {
        "confirm": {"description": "Press Return.", "keys": ["Return"]},
        "back": {"description": "Press Escape.", "keys": ["Escape"]},
    }
    assert set(questions(load(profile))) == {"input"}


def test_box_center_becomes_the_pointer_action():
    assert merge(PROFILE, answers("click_target")) == {
        "type": "pointer",
        "x": pytest.approx(0.6),
        "y": pytest.approx(0.3),
        "button": "left",
    }
    assert merge(PROFILE, answers("inspect_target"))["button"] == "right"
    assert "button" not in merge(PROFILE, answers("hover_target"))
    assert merge(PROFILE, answers("confirm"))["type"] == "control"


def test_stored_buttons_omit_an_unset_pointer():
    stored = PROFILE.model_dump(mode="json")["groups"]["input"]["buttons"]["confirm"]
    assert "pointer" not in stored


def reply(choice, box=BOX, confidence=0.8, **over):
    body = {
        "model": "jev-1.14.0",
        "answers": {
            "input": {
                "type": "choice",
                "choice": choice,
                "probabilities": {
                    key: 1.0 if key == choice else 0.0 for key in PROFILE.groups["input"].buttons
                },
                "confidence": 0.9,
            },
            **{
                f"pointer_{m}": {"type": "box", "box": box, "confidence": confidence}
                for m in ("left", "right", "move")
            },
        },
        "usage": {"input_tokens": 100, "output_tokens": 5},
    }
    body.update(over)
    return httpx.Response(200, json=body)


def agent_with(handler):
    client = create_client(MODEL)
    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    return TypedAgent(
        RetryPolicy(attempts=2, initial_delay=0.01),
        None,
        model_spec=MODEL,
        profile=PROFILE,
        client=client,
    )


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")


def test_one_request_carries_choice_and_box_questions():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["headers"] = request.headers
        return reply("click_target", confidence=None)

    agent = agent_with(handler)
    decision, stats = agent.decide(IMAGE, "", [], threading.Event())
    assert seen["headers"]["typesafe-danger-zone-images"] == "true"
    assert seen["body"]["questions"]["pointer_left"]["type"] == "box"
    assert decision["action"]["type"] == "pointer" and decision["action"]["button"] == "left"
    assert stats["typed_answers"]["pointer_left"] == {"box": BOX, "confidence": None}
    assert agent.steps[-1]["chosen"] == {"input": "click_target"}


@pytest.mark.parametrize(
    "box",
    [
        {"top": 0.2, "bottom": 0.4, "left": 0.7, "right": 0.5},
        {"top": 0.2, "bottom": 1.4, "left": 0.5, "right": 0.7},
        {"top": 0.2, "bottom": 0.4, "left": 0.5},
    ],
)
def test_malformed_boxes_are_model_output_failures(box):
    with pytest.raises(ProviderFailure) as failure:
        agent_with(lambda request: reply("click_target", box=box)).decide(
            IMAGE, "", [], threading.Event()
        )
    assert failure.value.category == "model_output"


def test_every_input_button_kind_has_a_tested_path():
    from gamecua.specs import InputButton

    kinds = set(InputButton.model_fields) - {"schema_version", "description"}
    assert kinds == {"keys", "click", "drag", "scroll", "pointer"}


def test_box_drag_asks_for_a_start_and_a_drop_box_and_drags_between_their_centres():
    profile = PROFILE.model_dump(mode="json")
    profile["groups"]["input"]["buttons"]["move_document"] = {
        "description": "Drag an object to a place.",
        "pointer": "drag",
    }
    profile = load(profile)
    asked = questions(profile)
    assert {"pointer_drag_from", "pointer_drag_to"} <= set(asked)
    assert all(asked[f"pointer_drag_{end}"]["type"] == "box" for end in ("from", "to"))
    chosen = answers("move_document") | {
        "pointer_drag_from": {"box": BOX, "confidence": 0.7},
        "pointer_drag_to": {
            "box": {"top": 0.6, "bottom": 0.8, "left": 0.1, "right": 0.3},
            "confidence": None,
        },
    }
    assert merge(profile, chosen) == {
        "type": "drag",
        "x": pytest.approx(0.6),
        "y": pytest.approx(0.3),
        "to_x": pytest.approx(0.2),
        "to_y": pytest.approx(0.7),
        "duration": 0.5,
    }
