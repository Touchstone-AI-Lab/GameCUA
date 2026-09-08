"""The pre-run interview is a separate, unscored conversation stored with the Trial."""

import json
from pathlib import Path

from fake_clients import SdkShapedClient
from test_trials import FakeBackend, FakeRecorder, InterruptedAgent, make_trial

from gamecua import interview
from gamecua.catalog import Catalog
from gamecua.evidence import score

CATALOG = Catalog(Path(__file__).resolve().parents[1] / "benchmarks")
ANSWER = {
    "expected_score": 20,
    "expected_score_probability": 60,
    "full_score_probability": 1,
    "hardest_part": "chapter 2",
    "likely_failure": "precise dashes",
    "helpful_mechanics": "instant respawn",
    "harmful_mechanics": "latency",
}


def celeste():
    spec = CATALOG.trials["hollow-knight-silksong-points-v1-kimi-k3-1-pro-frozen-3h"]
    return (
        spec,
        CATALOG.games["hollow-knight-silksong"],
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.models[spec.model_id],
        CATALOG.inputs[spec.inputs_id],
    )


def test_prompt_names_model_game_controls_mode_and_every_milestone():
    spec, game, rubric, model, profile = celeste()
    text = interview.prompt(spec, game, rubric, model, profile)
    assert model.model in text and game.introduction in text and game.controls in text
    assert "paused while you think" in text and "3 hours" in text
    assert all(m.description in text for m in rubric.milestones)
    assert "expected_score" in text


def test_conduct_parses_answers_and_keeps_the_raw_reply():
    calls = []

    def create(**body):
        calls.append(body)
        return {"model": body["model"], "choices": [{"message": {"content": json.dumps(ANSWER)}}]}

    record = interview.conduct(*celeste(), client=SdkShapedClient(create))
    assert record["answers"] == ANSWER and record["reply"] == json.dumps(ANSWER)
    assert len(calls[0]["messages"]) == 1
    prose = interview.conduct(
        *celeste(),
        client=SdkShapedClient(lambda **b: {"choices": [{"message": {"content": "maybe 10"}}]}),
    )
    assert prose["answers"] is None and prose["reply"] == "maybe 10"


def test_typed_models_skip_the_interview():
    spec, game, rubric, _, profile = celeste()
    record = interview.conduct(spec, game, rubric, CATALOG.models["jev-1-14"], profile)
    assert record["skipped"]


def test_trial_interviews_once_before_the_clock_and_scores_carry_the_answers(tmp_path, monkeypatch):
    seen = []

    def fake(spec, game, rubric, model, profile=None, **_):
        seen.append(model.id)
        return {"answers": ANSWER}

    monkeypatch.setattr(interview, "conduct", fake)
    trial = make_trial(tmp_path / "trial")
    trial.interview = True
    trial.backend = FakeBackend(trial.root)
    trial.agent_factory, trial.recorder = InterruptedAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert seen == ["deepseek-flash"]
    assert json.loads((trial.root / "interview.json").read_text())["answers"] == ANSWER
    events = [json.loads(line) for line in (trial.root / "events.jsonl").read_text().splitlines()]
    first = next(e for e in events if e["type"] == "interview")
    assert first["elapsed"] == 0.0
    assert score(trial.root)[1]["interview"] == ANSWER


def test_prompt_states_the_attempt_limit_and_its_time_cap():
    spec, game, rubric, model, profile = celeste()
    limited = spec.model_copy(update={"total_seconds": 21600.0, "episode_limit": 2})
    text = interview.prompt(limited, game, rubric, model, profile)
    assert "allows 2 attempts and lasts at most 6 hours" in text
    assert "another remains" in text
