"""Synthetic Factorio evidence tests; fixtures are never benchmark results."""

import json
from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.games.factorio.progress import FAMILIES, PREDICATES, PROGRESS_POINTS, facts

ROOT = Path(__file__).parents[2]
ITEMS = ("iron-ore", "iron-plate", "copper-plate", "iron-gear-wheel")


def sample(**changes):
    """Build one synthetic native telemetry row."""
    return {
        "schema_version": 2,
        "kind": "sample",
        "session_id": "session-one",
        "seq": 1,
        "tick": 60,
        "alive": True,
        "automated_iron": 0,
        "produced": {name: 100 for name in ITEMS},
        "consumed": {"automation-science-pack": 0},
        "rockets_launched": 0,
        **changes,
    }


def evidence(*rows):
    """Encode rows like one preserved evidence file."""
    return json.dumps(rows).encode()


def test_rubric_uses_one_point_per_unique_native_target_and_all_specs_use_it():
    catalog = Catalog(ROOT / "benchmarks")
    rubric = catalog.rubrics["factorio-bootstrap-v4"]
    assert len(rubric.milestones) == 100
    assert {m.points for m in rubric.milestones} == {1}
    assert {m.predicate for m in rubric.milestones} == PREDICATES
    assert len(set(PROGRESS_POINTS.values())) == 100
    specs = [t for t in catalog.trials.values() if t.game_id == "factorio"]
    assert specs and all(t.rubric_id == rubric.id for t in specs)


def test_existing_progress_never_receives_setup_credit():
    baseline = sample(automated_iron=100, consumed={"automation-science-pack": 10})
    assert facts("save", evidence({**baseline, "seq": 2}), baseline) == (set(), None)


def test_small_production_earns_distinct_targets():
    initial = sample()
    row = sample(seq=2, produced={**initial["produced"], "copper-plate": 102})
    assert facts("save", evidence(row), initial) == (
        {"bootstrap_copper_plate_1", "bootstrap_copper_plate_2"},
        None,
    )


def test_progress_after_death_is_not_scored():
    initial = sample()
    death = sample(seq=2, alive=False)
    after = sample(seq=3, produced={k: 1100 for k in ITEMS})
    assert facts("save", evidence(death, after), initial) == (set(), "death")


def test_rocket_launch_is_native_victory_and_history_is_ignored():
    found, terminal = facts("save", evidence(sample(seq=2, rockets_launched=1)), sample())
    assert terminal == "victory" and found == set()
    assert facts("history", b"claimed victory", sample()) == (set(), None)


@pytest.mark.parametrize("family", FAMILIES)
def test_each_counter_family_has_an_exact_baseline_relative_ceiling(family):
    initial = sample()
    field, targets = FAMILIES[family]
    row = sample(seq=2)
    start, end = initial, row
    for key in field[:-1]:
        start, end = start[key], end[key]
    start[field[-1]] = 2000
    end[field[-1]] = 2000 + targets[-1] - 1
    prefix = f"bootstrap_{family.replace('-', '_')}_"
    found, _ = facts("save", evidence(row), initial)
    assert len({p for p in found if p.startswith(prefix)}) == len(targets) - 1
    end[field[-1]] += 1
    found, _ = facts("save", evidence(row), initial)
    assert len({p for p in found if p.startswith(prefix)}) == len(targets)
