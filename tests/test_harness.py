import json
import threading
from types import SimpleNamespace

import pytest
from fake_clients import SdkShapedClient
from PIL import Image

from gamecua.actions import pixel, validate
from gamecua.provider import (
    InvalidResponse,
    ProviderFailure,
    RetryPolicy,
    VisionAgent,
    parse_reply,
)
from gamecua.specs import ContextSpec, ModelSpec

SPEC = ModelSpec(
    id="harness-fixture",
    provider="openai_compatible",
    model="vision-fixture",
    base_url="https://service.invalid/v1",
    api_key_env="TEST_PROVIDER_KEY",
    context=ContextSpec(window_tokens=131072),
)
VALID = {
    "observation": "a button",
    "hypothesis": "might start",
    "memory": "uncertain",
    "action": {"type": "click", "x": 0.4, "y": 0.6},
    "terminal_candidate": False,
}


@pytest.mark.parametrize(
    "action",
    [
        {"type": "click", "x": float("nan"), "y": 0},
        {"type": "click", "x": 1.1, "y": 0},
        {"type": "press", "key": "Alt+F4"},
        {"type": "wait", "seconds": 600},
        {"type": "click", "x": True, "y": 0},
        {"type": "click", "x": 0.2, "y": 0.3, "shell": "bad"},
    ],
)
def test_reject_unsafe_actions(action):
    with pytest.raises(ValueError):
        validate(action)


def test_coordinate_edges():
    assert pixel(1, 1, 1280, 720) == (1279, 719)
    assert pixel(0, 0, 1280, 720) == (0, 0)


def test_parse():
    assert parse_reply(json.dumps(VALID))["action"]["button"] == "left"
    with pytest.raises(InvalidResponse):
        parse_reply('{"action":{}}')


def test_backoff_exceeds_ten_minutes():
    p = RetryPolicy()
    delays = [p.delay(i, jitter=1) for i in range(9)]
    assert delays == [5, 10, 20, 40, 80, 160, 320, 640, 660]
    assert sum(delays) < p.budget_seconds
    assert p.delay(0, retry_after=800, jitter=1) == 800


def test_retries_do_not_execute_actions_or_leak_errors():
    events = []

    class Temporary(Exception):
        status_code = 503

    calls = []

    def create(**kw):
        calls.append(kw)
        if len(calls) < 3:
            raise Temporary("secret-key must not be logged")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(VALID)),
                )
            ],
            usage=None,
        )

    client = SdkShapedClient(create)
    agent = VisionAgent(
        RetryPolicy(initial_delay=0, max_delay=0), events.append, client, model_spec=SPEC
    )
    reply, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    assert stats["attempts"] == 3
    assert "secret-key" not in json.dumps(events)
    assert reply["action"]["type"] == "pointer"
    assert all("image_url" in str(c["messages"]) for c in calls)


def test_auth_failure_is_not_retried():
    class Unauthorized(Exception):
        status_code = 401

    calls = []

    def create(**kw):
        calls.append(1)
        raise Unauthorized()

    client = SdkShapedClient(create)
    agent = VisionAgent(client=client, model_spec=SPEC)
    with pytest.raises(ProviderFailure):
        agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    assert len(calls) == 1


def test_cancel_before_api_call():
    stop = threading.Event()
    stop.set()
    agent = VisionAgent(client=object(), model_spec=SPEC)
    with pytest.raises(ProviderFailure):
        agent.decide(Image.new("RGB", (2, 2)), "", [], stop)


def test_connections_reset_while_reading_or_writing_are_retried():
    import httpx

    sleeps, calls, events = [], [], []

    class FakeStop:
        def is_set(self):
            return False

        def wait(self, delay):
            sleeps.append(delay)
            return False

    def create(**kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadError("Connection reset by peer")
        if len(calls) == 2:
            raise httpx.WriteError("Broken pipe")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop", message=SimpleNamespace(content=json.dumps(VALID))
                )
            ],
            usage=None,
        )

    client = SdkShapedClient(create)
    agent = VisionAgent(event=events.append, client=client, model_spec=SPEC)
    decision, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], FakeStop())
    assert decision["action"] == validate(VALID["action"]) and stats["attempts"] == 3
    errors = [e for e in events if e["type"] == "provider_error"]
    assert [e["error_type"] for e in errors] == ["ReadError", "WriteError"]
    assert all(e["retryable"] for e in errors) and len(sleeps) == 2


def test_full_outage_recovery_includes_11_minute_wait(monkeypatch):
    from gamecua import provider

    clock = [0.0]
    monkeypatch.setattr(provider.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(provider.random, "uniform", lambda a, b: 1.0)
    sleeps = []

    class FakeStop:
        def is_set(self):
            return False

        def wait(self, delay):
            sleeps.append(delay)
            clock[0] += delay
            return False

    class Unavailable(Exception):
        status_code = 503

    calls = []

    def create(**kwargs):
        calls.append(1)
        if len(calls) <= 9:
            raise Unavailable()
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(VALID)),
                )
            ],
            usage=None,
        )

    client = SdkShapedClient(create)
    agent = VisionAgent(client=client, model_spec=SPEC)
    _, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], FakeStop())
    assert len(calls) == 10 and sleeps[-1] == 660
    assert stats["latency_seconds"] == 1935


def test_provider_budget_prevents_excessive_retry_after():
    class Busy(Exception):
        status_code = 429
        response = SimpleNamespace(headers={"retry-after": "9999"})

    calls = []

    def create(**kwargs):
        calls.append(1)
        raise Busy()

    client = SdkShapedClient(create)
    with pytest.raises(ProviderFailure):
        VisionAgent(client=client, model_spec=SPEC).decide(
            Image.new("RGB", (2, 2)), "", [], threading.Event()
        )
    assert len(calls) == 1


def test_resume_never_replays_pending_actions(tmp_path):
    from gamecua.execution import inherited_context

    segment = tmp_path / "episodes/episode-001/segments/segment-001"
    segment.mkdir(parents=True)
    (segment / "00001.json").write_text(
        json.dumps({"step": 1, "execution_status": "completed", "decision": VALID})
    )
    (segment / "00002.json").write_text(
        json.dumps(
            {
                "step": 2,
                "execution_status": "pending",
                "decision": {**VALID, "memory": "unconfirmed"},
            }
        )
    )
    episode = {"id": "episode-001", "segments": [{"id": "segment-001"}]}
    context = inherited_context(tmp_path, episode, [episode], "trial_memory")
    memory, history = context["memory"], context["history"]
    assert memory == VALID["memory"]
    assert len(history) == 1 and history[0]["step"] == 1


@pytest.mark.parametrize("content", ["```", "```json"])
def test_incomplete_code_fence_is_retryable_invalid_response(content):
    with pytest.raises(InvalidResponse):
        parse_reply(content)


def test_invalid_decision_retries_without_backoff_then_yields_the_step():
    sleeps, calls, events = [], [], []

    class FakeStop:
        def is_set(self):
            return False

        def wait(self, delay):
            sleeps.append(delay)
            return False

    def create(**kwargs):
        calls.append(1)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="not json"))
            ],
            usage=None,
        )

    client = SdkShapedClient(create)
    agent = VisionAgent(event=events.append, client=client, model_spec=SPEC)
    with pytest.raises(ProviderFailure) as failure:
        agent.decide(Image.new("RGB", (2, 2)), "", [], FakeStop())
    assert failure.value.category == "model_output"
    assert len(calls) == 2 and sleeps == []
    errors = [e for e in events if e["type"] == "provider_error"]
    assert [e["rejected_output_excerpt"] for e in errors] == ["not json", "not json"]
    assert all(e["reason"] == "Invalid structured decision" for e in errors)


def test_invalid_decision_recovers_on_immediate_retry():
    replies = ["not json", json.dumps(VALID)]

    def create(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop", message=SimpleNamespace(content=replies.pop(0))
                )
            ],
            usage=None,
        )

    client = SdkShapedClient(create)
    decision, stats = VisionAgent(client=client, model_spec=SPEC).decide(
        Image.new("RGB", (2, 2)), "", [], threading.Event()
    )
    assert decision["action"] == validate(VALID["action"]) and stats["attempts"] == 2


@pytest.mark.parametrize(
    "action, expected",
    [
        ({"type": "press", "key": "down"}, {"keys": ["Down"]}),
        ({"type": "press", "key": "RETURN"}, {"keys": ["Return"]}),
        ({"type": "hold", "key": "W", "duration": 0.5}, {"keys": ["w"]}),
        (
            {"type": "keys", "keys": ["shift_l", "Left"], "duration": 0.5},
            {"keys": ["Shift_L", "Left"]},
        ),
        (
            {
                "type": "control",
                "keys": ["SPACE"],
                "buttons": [],
                "dx": 0,
                "dy": 0,
                "duration": 0.5,
            },
            {"keys": ["space"]},
        ),
    ],
)
def test_key_names_are_case_insensitive_and_canonical(action, expected):
    result = validate(action)
    assert all(result[field] == value for field, value in expected.items())


@pytest.mark.parametrize(
    "action",
    [
        {"type": "press", "key": "enter"},
        {"type": "press", "key": "arrow_down"},
        {"type": "keys", "keys": ["w", "W"], "duration": 0.5},
    ],
)
def test_unknown_or_duplicate_keys_remain_rejected(action):
    with pytest.raises(ValueError):
        validate(action)


def test_five_action_types_and_legacy_rewrites():
    from gamecua.actions import KINDS

    assert KINDS == ("pointer", "drag", "control", "scroll", "wait")
    assert validate({"type": "pointer", "x": 0.1, "y": 0.2}) == {
        "type": "pointer",
        "x": 0.1,
        "y": 0.2,
    }
    tap = validate({"type": "control", "keys": ["space"]})
    assert tap["duration"] == 0.1 and tap["buttons"] == [] and tap["dx"] == 0
    assert validate({"type": "click", "x": 0.1, "y": 0.2})["button"] == "left"
    assert validate({"type": "relative_move", "dx": 5, "dy": 0})["dx"] == 5
    assert validate({"type": "mouse_hold", "button": "right", "duration": 1})["buttons"] == [
        "right"
    ]
    with pytest.raises(ValueError, match="Control needs"):
        validate({"type": "control"})
