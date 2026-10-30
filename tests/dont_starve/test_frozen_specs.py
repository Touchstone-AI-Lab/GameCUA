"""Operator-directed Frozen specs and the budget, step, pause and profile contract."""

import json
from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.games.dont_starve.progress import PREDICATES
from gamecua.interview import prompt
from gamecua.trials import Trial

CATALOG = Catalog(Path(__file__).resolve().parents[2] / "benchmarks")

MODELS = ("gpt-6-astra", "claude-opus-5-5")


OFFICIAL = {
    "claude-opus-5-5": "https://api.anthropic.com/v1",
    "gpt-6-astra": "https://api.openai.com/v1",
}


def model_spec(model):
    return CATALOG.models[f"dont-starve-{model}-high"]


def frozen_spec(model):
    return CATALOG.trials[f"dont-starve-{model}-frozen-3h"]


def live_spec(model):
    name = {
        "gpt-6-astra": "dont-starve-gpt-6-astra-live-3h",
        "claude-opus-5-5": "dont-starve-opus-live-0714-240s",
    }[model]
    return CATALOG.trials[name]


@pytest.mark.parametrize("model", MODELS)
def test_frozen_specs_declare_one_life_three_hours_and_three_second_steps(model):
    spec = frozen_spec(model)
    assert spec.game_id == "dont-starve"
    assert spec.rubric_id == "dont-starve-survival-collection-v6"
    assert spec.total_seconds == 10800
    assert spec.episode_limit == 1
    assert spec.action_execution == "frozen_steps"
    assert spec.step_seconds == 3.0
    assert spec.downtime_policy == "charged"
    assert spec.episode_context == "fresh"
    assert spec.condition == "pure_image_no_rules"


@pytest.mark.parametrize("model", MODELS)
def test_frozen_specs_share_the_controls_v5_profile(model):
    assert frozen_spec(model).inputs_id == "dont-starve-controls-v5"
    assert live_spec(model).inputs_id == "dont-starve-controls-v5"


@pytest.mark.parametrize("model", MODELS)
def test_frozen_and_live_specs_differ_only_in_execution_mode(model):
    frozen, live = frozen_spec(model), live_spec(model)
    assert frozen.model_id == live.model_id
    assert frozen.rubric_id == live.rubric_id
    assert frozen.total_seconds == live.total_seconds == 10800
    assert frozen.episode_limit == live.episode_limit == 1
    assert frozen.inputs_id == live.inputs_id
    assert frozen.recording_fps == live.recording_fps
    assert live.action_execution == "live"
    assert live.step_seconds is None
    assert frozen.action_execution == "frozen_steps"
    assert frozen.step_seconds == 3.0


@pytest.mark.parametrize("model", MODELS)
def test_frozen_specs_use_the_high_effort_vision_model_unchanged(model):
    frozen = frozen_spec(model)
    spec = model_spec(model)
    assert spec.model == frozen.model_id.removeprefix("dont-starve-").removesuffix("-high")
    assert spec.provider == "openai_compatible"
    assert spec.base_url == OFFICIAL[spec.model]
    assert spec.generation["reasoning_effort"] == "high"
    assert spec.vision is True


@pytest.mark.parametrize("model", MODELS)
def test_frozen_models_match_the_live_model_settings(model):
    frozen_model = CATALOG.models[frozen_spec(model).model_id]
    live_model = CATALOG.models[live_spec(model).model_id]
    assert frozen_model.model == live_model.model
    assert frozen_model.base_url == live_model.base_url
    assert frozen_model.api_key_env == live_model.api_key_env
    assert frozen_model.generation == live_model.generation


def test_game_declares_the_pause_method_that_frozen_execution_needs():
    game = CATALOG.games["dont-starve"]
    assert game.pause.method == "process"
    assert game.budget == "attempts"


@pytest.mark.parametrize("model", MODELS)
def test_frozen_rubric_exposes_every_native_predicate(tmp_path, model):
    spec = frozen_spec(model)
    trial = Trial(
        tmp_path / "trial",
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
        inputs=CATALOG.inputs[spec.inputs_id],
    )
    assert len(trial.rubric.milestones) == 100
    assert {m.predicate for m in trial.rubric.milestones} <= PREDICATES
    assert sum(m.points for m in trial.rubric.milestones) == 100


@pytest.mark.parametrize("model", MODELS)
def test_frozen_interview_states_the_actual_contract_and_hides_the_rubric(tmp_path, model):
    spec = frozen_spec(model)
    trial = Trial(
        tmp_path / "trial",
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
        inputs=CATALOG.inputs[spec.inputs_id],
    )
    interview = prompt(trial.spec, trial.game, trial.rubric, trial.model, trial.profile).lower()
    assert "two attempts" not in interview
    assert "six hours" not in interview
    assert "collection earns no points" not in interview
    assert "two lives" not in interview
    playing = (trial.root / "system_prompt.txt").read_text().lower()
    for milestone in trial.rubric.milestones:
        assert milestone.description.lower() not in playing


def test_frozen_specs_keep_the_attempt_budget_form_for_jev_only():
    game = json.loads(
        (Path(__file__).resolve().parents[2] / "benchmarks/games/dont-starve/game.json").read_text()
    )
    assert game["budget"] == "attempts"
    for model in MODELS:
        trial = frozen_spec(model)
        assert trial.total_seconds == 10800
        assert trial.episode_limit == 1
