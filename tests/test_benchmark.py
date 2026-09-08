"""Current catalog and generic model transport; synthetic responses are test-only."""

import asyncio
import json
import threading
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from gamecua.catalog import Catalog
from gamecua.models import CompatibleClient, CompletionHTTPError
from gamecua.provider import ProviderFailure, VisionAgent
from gamecua.specs import ContextSpec, ModelSpec

ROOT = Path(__file__).resolve().parents[1]
DECISION = {
    "observation": "Fixture screen",
    "hypothesis": "Uncertain",
    "memory": "Observed a fixture",
    "action": {"type": "wait", "seconds": 0.1},
    "terminal_candidate": False,
}


def model(model_id="fixture-vlm"):
    return ModelSpec(
        id=model_id,
        provider="openai_compatible",
        model=model_id,
        base_url="http://localhost:9999/v1",
        api_key_env="TEST_VLM_KEY",
        context=ContextSpec(window_tokens=131072),
    )


def test_catalog_current_trial_references():
    catalog = Catalog(ROOT / "benchmarks")
    spec = catalog.trials["sts-victory-v3-live-3h"]
    assert spec.model_id == "deepseek-v41-flash-thinking"
    assert catalog.rubrics[spec.rubric_id].game_id == spec.game_id
    assert not hasattr(catalog, "plan")


def test_specs_reject_unknown_fields():
    with pytest.raises(ValidationError):
        ModelSpec.model_validate({**model().model_dump(), "api_key": "not-allowed"})


@pytest.mark.parametrize("model_id", ["fixture-vlm-a", "fixture-vlm-b"])
def test_transport_switching_and_private_history_isolation(monkeypatch, model_id):
    spec = model(model_id)
    monkeypatch.setenv("TEST_VLM_KEY", "test-secret")
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer test-secret"
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(DECISION)}}]
            },
        )

    client = CompatibleClient(spec, http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    agent = VisionAgent(client=client, model_spec=spec)
    history = [
        {
            "step": 1,
            "action": DECISION["action"],
            "segment": "PRIVATE_GAME_NAME",
            "goal": "PRIVATE_GOAL_SENTINEL",
        }
    ]
    decision, _ = agent.decide(Image.new("RGB", (80, 40)), "", history, threading.Event())
    body = requests[0]
    assert body["model"] == model_id and decision["action"] == DECISION["action"]
    payload = json.dumps(body)
    assert "image_url" in payload
    assert all(
        value not in payload
        for value in ("PRIVATE_GAME_NAME", "PRIVATE_GOAL_SENTINEL", "test-secret")
    )
    assert "reasoning_effort" not in body and "response_format" not in body
    agent.close()


def test_reasoning_only_truncated_reply_is_model_output_without_backoff(monkeypatch):
    monkeypatch.setenv("TEST_VLM_KEY", "test-secret")
    events, sleeps = [], []

    class Stop:
        def is_set(self):
            return False

        def wait(self, delay):
            sleeps.append(delay)
            return False

    def handle(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"role": "assistant", "reasoning_content": "still thinking"},
                    }
                ]
            },
        )

    client = CompatibleClient(
        model(), http_client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    agent = VisionAgent(event=events.append, client=client, model_spec=model())
    with pytest.raises(ProviderFailure) as failure:
        agent.decide(Image.new("RGB", (8, 8)), "", [], Stop())
    assert failure.value.category == "model_output"
    errors = [e for e in events if e["type"] == "provider_error"]
    assert errors and all(e["reason"] == "Truncated answer" for e in errors)
    assert sleeps == []
    agent.close()


def test_transport_does_not_follow_redirect(monkeypatch):
    monkeypatch.setenv("TEST_VLM_KEY", "test-secret")
    urls = []

    def handle(request):
        urls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://other.invalid/steal"})

    client = CompatibleClient(
        model(), http_client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    with pytest.raises(CompletionHTTPError):
        client.complete({"model": "fixture", "messages": []})
    assert len(urls) == 1
    client.close()


def test_async_transport_timeout_is_wall_clock_bounded(monkeypatch):
    monkeypatch.setenv("TEST_VLM_KEY", "test-secret")

    async def handle(request):
        await asyncio.Event().wait()

    client = CompatibleClient(
        model(), http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    )
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        client.complete({"model": "fixture", "messages": []}, timeout=0.05)
    assert time.monotonic() - started < 1


def test_context_window_is_read_from_the_provider(monkeypatch):
    monkeypatch.setenv("TEST_VLM_KEY", "test-secret")

    def handle(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200, json={"data": [{"id": "fixture-vlm", "context_window": 1048576}]}
        )

    client = CompatibleClient(
        model(), http_client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    events = []
    agent = VisionAgent(event=events.append, client=client, model_spec=model())
    assert agent.context_config.window_tokens == 1048576
    assert events[0] == {"type": "context_window", "tokens": 1048576, "source": "provider"}
    agent.close()
