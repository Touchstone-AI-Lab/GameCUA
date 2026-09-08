"""Pre-run interview in its own conversation: the model is told the game, controls and rubric and predicts its result. Nothing from it reaches the gameplay conversation, and it runs before the Trial clock starts."""

import json
import threading
import time
from urllib.parse import urlsplit

from .provider import RetryPolicy, with_retries

QUESTIONS = """Please answer four questions:
1. What score out of 100 do you expect to reach, and how likely (0-100%) is it that you reach at least that score?
2. How likely (0-100%) is it that you reach the full 100 points?
3. What do you expect to be the hardest part, and where are you most likely to fail?
4. Which game mechanics work in your favour, and which work against you?
Reply with one JSON object only:
{"expected_score": 0-100, "expected_score_probability": 0-100, "full_score_probability": 0-100, "hardest_part": "...", "likely_failure": "...", "helpful_mechanics": "...", "harmful_mechanics": "..."}"""
FIELDS = (
    "expected_score",
    "expected_score_probability",
    "full_score_probability",
    "hardest_part",
    "likely_failure",
    "helpful_mechanics",
    "harmful_mechanics",
)


def prompt(spec, game, rubric, model, profile=None):
    from .typed import describe_profile

    if spec.action_execution == "frozen_steps":
        mode = (
            f"the game is paused while you think, then each action uses a nominal {spec.step_seconds:g} s "
            "host-time step. Input is released before any integration-specific rendering wait, "
            "then the game pauses again. Native simulation time depends on speed, native pause "
            "and performance. Rendering waits consume the same wall-clock budget"
        )
    else:
        mode = "the game keeps running while you think"
    controls = "\n".join(
        part for part in (game.controls, describe_profile(profile) if profile else "") if part
    )
    hours = f"{spec.total_seconds / 3600:g} hours of wall-clock time, including your thinking time"
    if spec.episode_limit:
        budget = (
            f"The run allows {spec.episode_limit} attempt"
            + ("s" if spec.episode_limit > 1 else "")
            + f" and lasts at most {hours}. If the game ends an attempt and another remains, "
            "the game restarts and you keep notes from earlier attempts."
        )
    else:
        budget = (
            f"The run lasts {hours}. If the game ends your attempt, it restarts within the same "
            "time budget and you keep notes from earlier attempts."
        )
    milestones = "\n".join(
        f"- {m.description} ({m.points} points"
        + (f"; requires {', '.join(m.prerequisites)}" if m.prerequisites else "")
        + ")"
        for m in rubric.milestones
    )
    return f"""You are about to be evaluated in GameCUA, a benchmark in which AI models play commercial video games from screenshots with ordinary keyboard and mouse input. Before the run starts we would like to interview you. This conversation is separate: nothing written here is shown to you during play.

Model under test: {model.model} (served at {urlsplit(model.base_url).netloc}).
Game: {game.title}.
About the game: {game.introduction}
Controls:
{controls or "Ordinary keyboard and mouse input; no control reference is supplied."}
How you will play: each turn you see one screenshot and choose one action; {mode}. {budget}
Scoring: 100 points, awarded only from the game's own saved progress, each milestone at most once:
{milestones}

{QUESTIONS}"""


def parse(content):
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return {k: value.get(k) for k in FIELDS} if isinstance(value, dict) else None


def conduct(
    spec, game, rubric, model, profile=None, client=None, event=None, seconds=900, stop=None
):
    text = prompt(spec, game, rubric, model, profile)
    record = {"prompt": text, "model": model.model, "started_at": time.time()}
    if model.provider == "typesafe":
        return {**record, "skipped": "typed-choice models cannot answer open questions"}
    if client is None:
        from .models import create_client

        client = create_client(model)

    def attempt(timeout):
        data = client.complete(
            {
                "model": model.model,
                "messages": [{"role": "user", "content": text}],
                **model.generation,
            },
            timeout=timeout,
        )
        return (
            data["choices"][0]["message"].get("content"),
            data.get("usage") or {},
            data.get("model"),
        )

    try:
        content, stats = with_retries(
            RetryPolicy(),
            event or (lambda e: None),
            stop or threading.Event(),
            time.monotonic() + seconds,
            attempt,
            "interview",
        )
    except Exception as exc:
        return {**record, "failure": type(exc).__name__}
    finally:
        client.close()
    return {
        **record,
        "reply": content,
        "answers": parse(content),
        "returned_model": stats["returned_model"],
        "usage": stats["usage"],
        "latency_seconds": stats["latency_seconds"],
    }
