"""Synthetic first-life ascent scoring; these checks are not experimental results."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from gamecua.catalog import Catalog
from gamecua.games.peak.progress import ASCENT_HEIGHTS, facts
from gamecua.trials import Trial
from tests.peak.test_progress import INITIAL, envelope, sample

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("height", [1, 20, 99, 100])
def test_absolute_height_is_not_ascent_and_thresholds_are_inclusive(height):
    predicate = f"ascent_{height:03d}m"
    anchor = sample(height_meters=103)
    below = envelope([sample(3, height_meters=103 + height - 0.001)], anchor)
    exact = envelope([sample(3, height_meters=103 + height)], anchor)
    assert predicate not in facts("save", below, INITIAL)[0]
    found, terminal = facts("save", exact, INITIAL)
    assert predicate in found and terminal is None
    assert len(found & ASCENT_HEIGHTS.keys()) == height


@pytest.mark.parametrize(
    "changes",
    [
        {"dead": True},
        {"passed_out": True},
        {"in_airport": True},
        {"run_started": False},
        {"lost": True},
        {"won": True},
    ],
)
def test_terminal_teleports_and_nonconscious_heights_do_not_earn_fine_points(changes):
    raw = envelope([sample(3, height_meters=8000, **changes)])
    assert not (facts("save", raw, INITIAL)[0] & ASCENT_HEIGHTS.keys())


def test_fine_points_stop_at_loss_and_do_not_accumulate_repeated_climbs():
    raw = envelope(
        [
            sample(3, height_meters=13),
            sample(4, height_meters=3),
            sample(5, height_meters=13),
            sample(6, lost=True, dead=True, height_meters=8000),
            sample(7, height_meters=103),
        ]
    )
    found, terminal = facts("save", raw, INITIAL)
    assert found & ASCENT_HEIGHTS.keys() == {f"ascent_{n:03d}m" for n in range(1, 11)}
    assert terminal == "death"


@pytest.mark.parametrize(
    "short,model,endpoint",
    [
        ("opus", "claude-opus-5-5", "https://api.anthropic.com/v1"),
        ("astra", "gpt-6-astra", "https://api.openai.com/v1"),
    ],
)
@pytest.mark.parametrize("mode,execution", [("live", "live"), ("frozen", "frozen_steps")])
def test_one_life_cells_freeze_policy_and_keep_rubric_out_of_play_prompt(
    tmp_path, short, model, endpoint, mode, execution
):
    catalog = Catalog(ROOT / "benchmarks")
    spec = catalog.trials[f"peak-ascent-points-v1-{short}-{mode}"]
    configured = catalog.models[spec.model_id]
    assert configured.model == model and configured.generation["reasoning_effort"] == "high"
    assert configured.base_url == endpoint
    assert spec.episode_limit == 1 and spec.total_seconds == 10800
    assert spec.action_execution == execution
    assert spec.provider_failure_policy == "freeze_retry_timeout_credit"
    assert spec.inputs_id == "peak-controls-v1"
    rubric = catalog.rubrics[spec.rubric_id]
    assert len(rubric.milestones) == 100 and all(m.points == 1 for m in rubric.milestones)
    assert len({m.predicate for m in rubric.milestones}) == 100
    trial = Trial(
        tmp_path / "trial",
        spec,
        rubric,
        catalog.games["peak"],
        configured,
        backend=SimpleNamespace(freeze=lambda: None, thaw=lambda: None),
        inputs=catalog.inputs[spec.inputs_id],
    )
    prompt = (trial.root / "system_prompt.txt").read_text()
    assert all(m.description not in prompt and m.predicate not in prompt for m in rubric.milestones)
