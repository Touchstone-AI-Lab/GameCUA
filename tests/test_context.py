"""Continuous SDK session, compaction, and restoration contract tests."""

import json
import threading
import time
from types import SimpleNamespace

import pytest
from fake_clients import SdkShapedClient
from PIL import Image

from gamecua.context import Conversation, estimate_tokens, load_checkpoint, prune_images
from gamecua.provider import COMPACTION_FALLBACK, ProviderFailure, VisionAgent
from gamecua.specs import ContextSpec, ModelSpec

DECISION = {
    "observation": "A room",
    "hypothesis": "The door may open",
    "memory": "",
    "action": {"type": "press", "key": "Return"},
    "terminal_candidate": False,
}


def spec(context=None, model="fixture-vision"):
    return ModelSpec(
        id="context-fixture",
        provider="openai_compatible",
        model=model,
        base_url="https://fixture.invalid/v1",
        api_key_env="TEST_KEY",
        generation={"max_tokens": 256},
        context=context or ContextSpec(window_tokens=131072),
    )


def client(responses):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        content = responses.pop(0)
        if isinstance(content, Exception):
            raise content
        return SimpleNamespace(
            model=kwargs["model"],
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(content)),
                )
            ],
            usage=SimpleNamespace(
                model_dump=lambda: {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                }
            ),
        )

    return SdkShapedClient(create), calls


def turn(text):
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def small_context():
    return ContextSpec(
        window_tokens=9984,
        summary_tokens=256,
        image_tokens=256,
        recent_turns=1,
        recent_images=1,
    )


def test_history_keeps_observations_decisions_and_execution(tmp_path):
    transport, calls = client([DECISION, DECISION])
    agent = VisionAgent(client=transport, model_spec=spec())
    agent.bind_context(tmp_path / "context")
    image = Image.new("RGB", (2, 2))
    decision, _ = agent.decide(image, "", [], threading.Event())
    agent.record_execution(
        {
            "step": 1,
            "decision": decision,
            "execution_status": "rejected",
            "reason": "stale_observation",
        }
    )
    agent.decide(image, "", [], threading.Event())
    assert len(calls[1]["messages"]) > len(calls[0]["messages"])
    assert "stale_observation" in json.dumps(calls[1]["messages"])
    assert '"role": "assistant"' in json.dumps(calls[1]["messages"])
    assert "your_previous_notes" not in json.dumps(calls[1]["messages"])
    agent.close()
    restored = load_checkpoint(tmp_path / "context")
    assert len(restored["items"]) == 5


def test_automatic_compaction_preserves_recent_turns_and_evidence(tmp_path):
    conversation = Conversation(small_context(), tmp_path)
    older = turn("learned " * 930)
    recent = turn("latest room")
    conversation.append([older, {"role": "assistant", "content": "go"}, recent])
    requests = []

    def summarize(messages, tokens):
        requests.append((messages, tokens))
        return '{"summary":"Return opened the door; uncertain location."}', {
            "usage": {"prompt_tokens": 20}
        }

    messages, compactions = conversation.prepare("policy" * 750, [turn("now")], summarize)
    assert requests and 0 < requests[0][1] <= 256 * 4
    assert "characters" in requests[0][0][0]["content"]
    assert estimate_tokens(messages, small_context().image_tokens) <= 9984 / 3
    assert any(item == recent for item in messages)
    assert "Return opened" in json.dumps(messages)
    assert "learned learned" not in json.dumps(messages)
    assert compactions[0]["usage"]["prompt_tokens"] == 20
    assert load_checkpoint(tmp_path)["compactions"] == 1
    conversation.close()


def test_invalid_summary_does_not_replace_history(tmp_path):
    conversation = Conversation(small_context(), tmp_path)
    original = [turn("learned " * 930), {"role": "assistant", "content": "go"}, turn("recent")]
    conversation.append(original)
    with pytest.raises(ValueError):
        conversation.prepare("policy" * 750, [turn("now")], lambda *args: ('{"summary":""}', {}))
    assert conversation.items() == original
    assert conversation.compactions == 0
    conversation.close()


def test_compaction_uses_same_provider_and_counts_requests(tmp_path):
    config = small_context()
    transport, calls = client([{"summary": "A learned control"}, DECISION])
    agent = VisionAgent(client=transport, model_spec=spec(config, "tested-model"))
    agent.bind_context(tmp_path)
    agent.conversation.append(
        [
            turn("learned " * 930),
            {"role": "assistant", "content": "go"},
            turn("recent"),
        ]
    )
    _, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    assert [call["model"] for call in calls] == ["tested-model", "tested-model"]
    assert calls[0]["max_tokens"] == 256
    limit = int(calls[0]["messages"][0]["content"].rsplit("at most ", 1)[1].split()[0])
    assert 0 < limit <= config.summary_tokens * 4
    assert stats["context"]["compactions"][0]["usage"]["completion_tokens"] == 20
    agent.close()


def test_death_retains_summary_and_clears_old_visual_history(tmp_path):
    initial = {
        "items": [turn("Old location: room A"), {"role": "assistant", "content": "Return worked"}],
        "compactions": 0,
        "inheritance": True,
    }
    conversation = Conversation(small_context(), tmp_path, initial)
    messages, _ = conversation.prepare(
        "New attempt",
        [turn("current room")],
        lambda *args: ('{"summary":"Return can open doors."}', {}),
    )
    assert "Return can open" in json.dumps(messages)
    assert "Old location" not in json.dumps(messages)
    conversation.close()


def test_restore_checkpoint(tmp_path):
    original = Conversation(ContextSpec(window_tokens=131072), tmp_path / "original")
    original.append([turn("remember this")])
    original.save()
    original.close()
    state = load_checkpoint(tmp_path / "original")
    restored = Conversation(ContextSpec(window_tokens=131072), tmp_path / "restored", state)
    assert restored.items() == state["items"]
    restored.close()


def test_budget_overflow_never_sends_oversized_decision():
    conversation = Conversation(small_context())
    with pytest.raises(ValueError):
        conversation.prepare("policy", [turn("x" * 15000)], lambda *args: pytest.fail("no history"))
    conversation.close()


def test_cancelled_and_expired_requests_do_not_call_provider():
    transport, calls = client([])
    agent = VisionAgent(client=transport, model_spec=spec())
    stop = threading.Event()
    stop.set()
    with pytest.raises(ProviderFailure):
        agent.decide(Image.new("RGB", (2, 2)), "", [], stop)
    with pytest.raises(ProviderFailure):
        agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event(), time.monotonic() - 1)
    assert calls == []
    agent.close()


def test_pruning_keeps_text_and_recent_images_without_mutating_history():
    items = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "observed"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,old"}},
            ],
        },
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,new"}}],
        },
    ]
    pruned = prune_images(items, 1)
    assert "old" not in json.dumps(pruned)
    assert "observed" in json.dumps(pruned) and "new" in json.dumps(pruned)
    assert "old" in json.dumps(items)
    assert estimate_tokens(pruned, 4096) >= 4096


def scripted_client(replies):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        finish, content = replies.pop(0)
        return SimpleNamespace(
            model=kwargs["model"],
            choices=[
                SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))
            ],
            usage=None,
        )

    return SdkShapedClient(create), calls


class RecordingStop:
    def __init__(self):
        self.waits = []

    def is_set(self):
        return False

    def wait(self, delay):
        self.waits.append(delay)
        return False


def history_needing_compaction(agent):
    agent.conversation.append(
        [turn("learned " * 930), {"role": "assistant", "content": "go"}, turn("recent")]
    )


def test_invalid_compaction_output_retries_immediately_as_model_output(tmp_path):
    first = ("length", None)
    events = []
    transport, calls = scripted_client(
        [
            first,
            ("stop", json.dumps({"summary": "A learned control"})),
            ("stop", json.dumps(DECISION)),
        ]
    )
    agent = VisionAgent(
        event=events.append, client=transport, model_spec=spec(small_context(), "tested-model")
    )
    agent.bind_context(tmp_path)
    history_needing_compaction(agent)
    stop = RecordingStop()
    decision, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], stop)
    assert decision["action"]["keys"] == ["Return"]
    assert stop.waits == []
    errors = [e for e in events if e["type"] == "provider_error"]
    assert len(errors) == 1 and errors[0]["category"] == "model_output"
    assert [e for e in events if e["type"] == "provider_backoff"] == []
    assert len(stats["context"]["compactions"]) == 1
    agent.close()


def test_summary_limit_counts_characters_not_utf8_bytes(tmp_path):
    events = []
    probe, probe_calls = scripted_client(
        [("stop", json.dumps({"summary": "x"})), ("stop", json.dumps(DECISION))]
    )
    agent = VisionAgent(client=probe, model_spec=spec(small_context(), "tested-model"))
    agent.bind_context(tmp_path / "probe")
    history_needing_compaction(agent)
    agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    agent.close()
    limit = int(probe_calls[0]["messages"][0]["content"].rsplit("at most ", 1)[1].split()[0])
    transport, calls = scripted_client(
        [
            ("stop", json.dumps({"summary": "\u5730" * limit}, ensure_ascii=False)),
            ("stop", json.dumps(DECISION)),
        ]
    )
    agent = VisionAgent(
        event=events.append, client=transport, model_spec=spec(small_context(), "tested-model")
    )
    agent.bind_context(tmp_path / "multibyte")
    history_needing_compaction(agent)
    decision, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    assert len("\u5730" * limit) == limit < len(("\u5730" * limit).encode("utf-8"))
    assert [e for e in events if e["type"] == "provider_error"] == []
    assert len(stats["context"]["compactions"]) == 1
    agent.close()


def test_overlong_summary_is_truncated_without_retry(tmp_path):
    events = []
    transport, calls = scripted_client(
        [("stop", json.dumps({"summary": "x" * 50000})), ("stop", json.dumps(DECISION))]
    )
    agent = VisionAgent(
        event=events.append, client=transport, model_spec=spec(small_context(), "tested-model")
    )
    agent.bind_context(tmp_path)
    history_needing_compaction(agent)
    decision, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    limit = int(calls[0]["messages"][0]["content"].rsplit("at most ", 1)[1].split()[0])
    assert [e for e in events if e["type"] == "provider_error"] == []
    summary = agent.conversation.items()[0]["content"]
    assert summary.endswith("x" * limit) and "x" * (limit + 1) not in summary
    assert len(calls) == 2 and decision["action"]["keys"] == ["Return"]
    agent.close()


def test_failed_compaction_drops_history_and_play_continues(tmp_path):
    events = []
    replies = [("length", None)] * 2 + [("stop", json.dumps(DECISION))]
    replies += [("stop", "  ")] * 2 + [("stop", json.dumps(DECISION))]
    transport, calls = scripted_client(replies)
    agent = VisionAgent(
        event=events.append, client=transport, model_spec=spec(small_context(), "tested-model")
    )
    agent.bind_context(tmp_path)
    stop = RecordingStop()
    for _ in range(2):
        history_needing_compaction(agent)
        decision, _ = agent.decide(Image.new("RGB", (2, 2)), "", [], stop)
        assert decision["action"]["keys"] == ["Return"]
    fallbacks = [e for e in events if e["type"] == "compaction_fallback"]
    assert len(fallbacks) == 2 and all("invalid" in e["reason"] for e in fallbacks)
    assert stop.waits == [] and not [e for e in events if e["type"] == "provider_backoff"]
    assert COMPACTION_FALLBACK in agent.conversation.items()[0]["content"]
    assert agent.conversation.compactions == 2
    agent.close()


def test_provider_failure_during_compaction_is_not_masked(tmp_path):
    def create(**kwargs):
        raise ProviderFailure("Stopped")

    client = SdkShapedClient(create)
    agent = VisionAgent(client=client, model_spec=spec(small_context(), "tested-model"))
    agent.bind_context(tmp_path)
    history_needing_compaction(agent)
    with pytest.raises(ProviderFailure) as failure:
        agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    assert failure.value.category == "provider"
    agent.close()


@pytest.mark.parametrize(
    "provider_prompt_tokens", [942, 1124], ids=["qwen-together", "gpt-compatible"]
)
def test_default_estimate_does_not_undercount_measured_screenshot_requests(provider_prompt_tokens):
    request = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What game is this and where is the player? One sentence.",
                },
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        }
    ]
    estimate = estimate_tokens(request, ContextSpec().image_tokens)
    assert provider_prompt_tokens <= estimate <= 2 * provider_prompt_tokens


def test_text_estimate_stays_conservative_for_english_and_cjk():
    english = "The character walks east along the path toward the town square. " * 20
    assert estimate_tokens([{"role": "user", "content": english}], 0) >= len(english) // 4
    cjk = "".join(map(chr, (0x89D2, 0x8272, 0x5411, 0x4E1C, 0x8D70))) * 40
    assert estimate_tokens([{"role": "user", "content": cjk}], 0) >= len(cjk)


@pytest.mark.parametrize(
    "oversized_recent", [False, True], ids=["single-old-item", "recent-overflow"]
)
def test_local_compaction_budget_failure_keeps_decisions_and_checkpoints(
    tmp_path, oversized_recent
):
    events = []
    transport, calls = scripted_client([("stop", json.dumps(DECISION))])
    agent = VisionAgent(
        event=events.append, client=transport, model_spec=spec(small_context(), "tested-model")
    )
    agent.bind_context(tmp_path)
    original = (
        [turn("older"), turn("x" * 50000)]
        if oversized_recent
        else [turn("x" * 50000), turn("recent")]
    )
    agent.conversation.append(original)
    stop = RecordingStop()
    decision, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], stop)
    assert decision["action"]["keys"] == ["Return"]
    assert len(calls) == 1 and stop.waits == []
    assert stats["context"]["compactions"][0]["budget_fallback"]
    assert stats["context"]["estimated_input_tokens"] <= 9984 / 3
    assert not any("x" * 50000 in str(item) for item in agent.conversation.items())
    assert any(
        e["type"] == "compaction_fallback" and e["category"] == "context_budget" for e in events
    )
    assert stats["context"]["compactions"][0]["dropped_items"] >= 1
    restored = Conversation(
        small_context(), tmp_path / "restored", initial=load_checkpoint(tmp_path)
    )
    assert restored.items() == agent.conversation.items()
    restored.close()
    agent.close()


def test_budget_fallback_cannot_hide_oversized_current_input():
    conversation = Conversation(small_context())
    original = [turn("old"), turn("recent")]
    conversation.append(original)
    with pytest.raises(ValueError, match="Current observation"):
        conversation.prepare(
            "policy", [turn("x" * 50000)], lambda *args: pytest.fail("summary request")
        )
    assert conversation.items() == original
    conversation.close()


def test_budget_fallback_does_not_inherit_old_attempt_state():
    original = [turn("previous position " + "x" * 50000)]
    conversation = Conversation(small_context(), initial={"items": original, "inheritance": True})
    messages, stats = conversation.prepare(
        "policy", [turn("new attempt")], lambda *args: pytest.fail("summary request")
    )
    assert stats[0]["budget_fallback"]
    assert "previous position" not in str(messages)
    assert not conversation.inheritance
    conversation.close()


def test_requested_compaction_summarizes_turns_beyond_the_recent_window(tmp_path):
    config = ContextSpec(window_tokens=131072)
    model = spec(config).model_copy(update={"generation": {"max_tokens": 12288}})
    transport, calls = scripted_client(
        [
            ("stop", json.dumps({"summary": "Earlier learned controls"})),
            ("stop", json.dumps(DECISION)),
        ]
    )
    agent = VisionAgent(client=transport, model_spec=model)
    agent.bind_context(tmp_path)
    for index in range(config.recent_turns + 2):
        agent.conversation.append([turn(f"turn {index}"), {"role": "assistant", "content": "go"}])
    agent.conversation.pending_request = True
    _, stats = agent.decide(Image.new("RGB", (2, 2)), "", [], threading.Event())
    assert config.window_tokens == 131072
    assert config.summary_tokens == 2048
    assert len(calls) == 2 and all(c["max_tokens"] == 12288 for c in calls)
    assert len(stats["context"]["compactions"]) == 1
    assert estimate_tokens(calls[1]["messages"], config.image_tokens) <= 131072 / 3
    agent.close()


def test_screenshots_are_referenced_files_and_restore_across_segments(tmp_path):
    from gamecua.provider import image_block

    root = tmp_path / "trial"
    directory = root / "episodes/episode-001/segments/segment-001/context"
    conversation = Conversation(ContextSpec(window_tokens=131072), directory)
    for index in range(10):
        path = directory.parent / f"{index:05d}_before.png"
        image = Image.new("RGB", (12, 12), (index, 0, 0))
        image.save(path)
        conversation.observation_path = path
        conversation.append([{"role": "user", "content": [image_block(image)]}])
        conversation.save()
    items = conversation.items()
    assert all(item["content"][0]["type"] == "evidence_image" for item in items)
    assert not (root / "context-images").exists()
    assert "base64" not in (directory / "latest.json").read_text()
    restored = Conversation(
        ContextSpec(window_tokens=131072),
        root / "episodes/episode-001/segments/segment-002/context",
        load_checkpoint(directory),
    )
    messages, _ = restored.prepare("policy", [], lambda *args: pytest.fail("unexpected compaction"))
    images = [
        part
        for item in messages
        if isinstance(item.get("content"), list)
        for part in item["content"]
        if part["type"] == "image_url"
    ]
    assert len(images) == 3
    conversation.close()
    restored.close()


@pytest.mark.parametrize(
    "content,expected",
    [
        ('{"summary":"a "quoted" b"}', 'a "quoted" b'),
        ('{"summary":"cut off mid', "cut off mid"),
        ("plain notes", "plain notes"),
        ('```json\n{"summary":"x"}\n```', "x"),
    ],
)
def test_malformed_or_truncated_summaries_are_kept_as_text(content, expected):
    from gamecua.provider import parse_summary

    assert json.loads(parse_summary(content, 100))["summary"] == expected


def test_compaction_starts_at_a_third_of_the_window():
    conversation = Conversation(ContextSpec(window_tokens=30000, image_tokens=256))
    assert conversation.fits([{"role": "user", "content": "x" * 3 * 9900}])
    assert not conversation.fits([{"role": "user", "content": "x" * 3 * 10100}])
    conversation.close()
