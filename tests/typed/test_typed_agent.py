"""Typed decisions are proven with an offline HTTP double; no real provider is contacted."""

import json
import threading
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from gamecua.catalog import Catalog
from gamecua.models import create_client
from gamecua.provider import ProviderFailure, RetryPolicy
from gamecua.specs import InputProfile
from gamecua.typed import TypedAgent, merge, questions

ROOT = Path(__file__).parents[2]
CATALOG = Catalog(ROOT / "benchmarks")
PROFILE = CATALOG.inputs["celeste-keys-v1"]
MODEL = CATALOG.models["jev-1-14"]
IMAGE = Image.new("RGB", (64, 36), (10, 20, 30))


def answer(profile, picks):
    return {
        name: {
            "type": "choice",
            "choice": picks.get(name, "none" if "none" in group.buttons else "neutral"),
            "probabilities": {
                key: 1.0
                if key == picks.get(name, "none" if "none" in group.buttons else "neutral")
                else 0.0
                for key in group.buttons
            },
            "confidence": 0.9,
        }
        for name, group in profile.groups.items()
    }


def reply(profile, picks, **over):
    body = {
        "model": "jev-1.14.0",
        "answers": answer(profile, picks),
        "usage": {"input_tokens": 100, "output_tokens": 5},
    }
    body.update(over)
    return httpx.Response(200, json=body)


def agent_with(handler, **policy):
    client = create_client(MODEL)
    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    return TypedAgent(
        RetryPolicy(attempts=3, initial_delay=0.01, **policy),
        None,
        model_spec=MODEL,
        profile=PROFILE,
        client=client,
    )


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")


def test_request_has_native_shape_and_button_descriptions():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return reply(PROFILE, {"direction": "right", "jump": "jump"})

    decision, stats = agent_with(handler).decide(IMAGE, "", [], threading.Event())
    assert seen["path"].endswith("/systemone")
    assert seen["headers"]["authorization"] == "Bearer test-key"
    assert seen["headers"]["typesafe-danger-zone-images"] == "true"
    body = seen["body"]
    assert body["model"] == "jev-1.14.0" and len(body["assets"]) == 1
    assert set(body["questions"]) == {"direction", "jump", "dash", "grab"}
    assert body["questions"]["jump"]["criteria"]["jump"] == "Hold the C key."
    assert decision["action"] == {
        "type": "control",
        "keys": ["Right", "c"],
        "buttons": [],
        "dx": 0.0,
        "dy": 0.0,
        "duration": 0.5,
    }
    assert decision["memory"] == "" and decision["terminal_candidate"] is False
    assert stats["returned_model"] == "jev-1.14.0"
    assert stats["typed_answers"]["direction"]["choice"] == "right"
    assert stats["usage"]["total_tokens"] == 105


def test_all_idle_choices_wait_for_one_step():
    assert merge(PROFILE, answer(PROFILE, {})) == {"type": "wait", "seconds": 0.5}


def test_history_is_trimmed_without_model_summaries():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return reply(PROFILE, {"dash": "dash"})

    agent = agent_with(handler)
    for _ in range(6):
        agent.decide(IMAGE, "inherited", [{"step": 1}], threading.Event())
        agent.record_execution({"execution_status": "completed"})
    assert len(agent.steps) == MODEL.context.recent_images
    assert len(bodies[-1]["assets"]) == MODEL.context.recent_images + 1
    assert all(len(b["questions"]) == 4 for b in bodies)


def test_malformed_answers_are_retried_then_fail_as_model_output():
    calls = []

    def handler(request):
        calls.append(1)
        return reply(PROFILE, {}, model="")

    with pytest.raises(ProviderFailure) as failure:
        agent_with(handler).decide(IMAGE, "", [], threading.Event())
    assert failure.value.category == "model_output" and len(calls) == 2


def test_rejected_answer_excerpt_is_logged():
    events = []
    agent = agent_with(lambda request: reply(PROFILE, {}, model=""))
    agent.event = events.append
    with pytest.raises(ProviderFailure):
        agent.decide(IMAGE, "", [], threading.Event())
    errors = [e for e in events if e["type"] == "provider_error"]
    assert errors and '"answers"' in errors[0]["rejected_output_excerpt"]


def test_transient_status_is_retried_and_auth_failure_is_not():
    codes = iter([503, 200])

    def flaky(request):
        return httpx.Response(503) if next(codes) == 503 else reply(PROFILE, {})

    decision, stats = agent_with(flaky).decide(IMAGE, "", [], threading.Event())
    assert stats["attempts"] == 2 and decision["action"]["type"] == "wait"
    with pytest.raises(ProviderFailure, match="Non-retryable"):
        agent_with(lambda request: httpx.Response(401)).decide(IMAGE, "", [], threading.Event())


def test_probabilities_must_match_the_choice():
    bad = answer(PROFILE, {"direction": "left"})
    bad["direction"]["probabilities"]["right"] = 1.0
    bad["direction"]["probabilities"]["left"] = 0.0
    with pytest.raises(ProviderFailure):
        agent_with(
            lambda r: httpx.Response(
                200,
                json={
                    "model": "jev-1.14.0",
                    "answers": bad,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )
        ).decide(IMAGE, "", [], threading.Event())


def test_profile_rejects_single_button_groups():
    data = PROFILE.model_dump(mode="json")
    data["groups"]["jump"]["buttons"] = {"only": data["groups"]["jump"]["buttons"]["jump"]}
    with pytest.raises(ValidationError):
        InputProfile.model_validate(data)


def test_profile_text_carries_no_evaluator_state():
    text = json.dumps(questions(PROFILE)).lower()
    assert not any(
        word in text for word in ("chapter", "strawberr", "rubric", "milestone", "score")
    )


def test_catalog_binds_typed_models_to_matching_profiles():
    for trial in CATALOG.trials.values():
        if CATALOG.models[trial.model_id].provider == "typesafe":
            assert trial.inputs_id is not None
    frozen = CATALOG.trials["hollow-knight-silksong-jev-progress-v2-frozen-1h"]
    assert frozen.step_seconds == CATALOG.inputs[frozen.inputs_id].step_seconds
    assert (
        frozen.rubric_id
        == CATALOG.trials["hollow-knight-silksong-points-v1-kimi-k3-1-pro-frozen-3h"].rubric_id
    )


def test_click_buttons_merge_into_one_normalized_click():
    profile = CATALOG.inputs["sts-grid-v3"]
    action = merge(profile, answer(profile, {"input": "c08r05"}))
    assert action["type"] == "pointer" and 0.4 < action["x"] < 0.6 and 0.45 < action["y"] < 0.55
    assert merge(profile, answer(profile, {"input": "end_turn"})) == {
        "type": "control",
        "keys": ["e"],
        "buttons": [],
        "dx": 0.0,
        "dy": 0.0,
        "duration": 0.5,
    }
    assert "wait" not in profile.groups["input"].buttons


def test_rounded_probabilities_over_many_options_are_accepted():
    profile = CATALOG.inputs["sts-grid-v3"]
    picks = answer(profile, {"input": "c03r03"})
    for key in picks["input"]["probabilities"]:
        picks["input"]["probabilities"][key] = 0.0
    picks["input"]["probabilities"]["c03r03"] = 0.55
    picks["input"]["probabilities"]["c01r01"] = 0.30
    picks["input"]["probabilities"]["c02r01"] = 0.1
    body = {
        "model": "jev-1.14.0",
        "answers": picks,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    agent = agent_with(lambda request: httpx.Response(200, json=body))
    agent.profile, agent.questions = profile, questions(profile)
    decision, _ = agent.decide(IMAGE, "", [], threading.Event())
    assert decision["action"]["type"] == "pointer"


def test_language_model_prompt_carries_the_same_controls_reference():
    from gamecua.trials import policy_prompt

    spec = CATALOG.trials["hollow-knight-silksong-points-v1-kimi-k3-1-pro-frozen-3h"]
    profile = CATALOG.inputs[spec.inputs_id]
    prompt = policy_prompt(spec, profile)
    assert prompt.startswith(policy_prompt(spec))
    assert "Controls reference" in prompt
    for group in profile.groups.values():
        for button in group.buttons.values():
            assert button.description in prompt
