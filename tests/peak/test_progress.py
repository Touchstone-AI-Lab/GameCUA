"""Synthetic PEAK evidence checks; fixtures are never benchmark results."""

import json
from pathlib import Path

from gamecua.catalog import Catalog
from gamecua.games.peak.progress import ASCENT_HEIGHTS, PREDICATES, facts

ROOT = Path(__file__).resolve().parents[2]
RUN = "4d15286e-3307-4cc5-8bd4-0b5ab538eddf"
INITIAL = {"binding": "fixture-episode", "baseline_sequence": 1}


def sample(sequence=2, **changes):
    """Build one synthetic observer sample."""
    return {
        "schema_version": 1,
        "evaluator_version": "peak-native-observer-1",
        "binding": INITIAL["binding"],
        "sequence": sequence,
        "unix_time": float(sequence),
        "scene": "FixtureIsland",
        "game_version": "fixture",
        "run_id": RUN,
        "run_started": True,
        "in_airport": False,
        "character_present": True,
        "stats_initialized": True,
        "dead": False,
        "passed_out": False,
        "climbing": False,
        "won": False,
        "lost": False,
        "segment": "Beach",
        "height_meters": 3.0,
        "run_seconds": float(sequence),
        "error": "",
        **changes,
    }


def envelope(rows, anchor=None):
    """Encode rows like one preserved evidence file."""
    return json.dumps(
        {
            "schema_version": 1,
            "binding": INITIAL["binding"],
            "run_start": sample() if anchor is None else anchor,
            "rows": rows,
        }
    ).encode()


def test_rubric_uses_every_ascent_predicate_and_all_specs_use_it():
    catalog = Catalog(ROOT / "benchmarks")
    rubric = catalog.rubrics["peak-ascent-points-v1"]
    assert {m.predicate for m in rubric.milestones} == PREDICATES
    assert sum(m.points for m in rubric.milestones) == 100
    specs = [t for t in catalog.trials.values() if t.game_id == "peak"]
    assert specs and all(t.rubric_id == rubric.id for t in specs)


def test_victory_and_loss_are_native_terminal_states():
    assert facts("save", envelope([sample(3, segment="Peak")]), INITIAL) == (set(), None)
    assert facts("save", envelope([sample(3, won=True)]), INITIAL) == (set(), "victory")
    assert facts("save", envelope([sample(3, dead=True, lost=True)]), INITIAL) == (set(), "death")
    assert facts("save", envelope([sample(3, dead=True)]), INITIAL)[1] is None
    assert facts("history", envelope([sample(3, won=True)]), INITIAL) == (set(), None)


def test_rows_without_a_run_start_anchor_earn_nothing():
    raw = json.loads(envelope([sample(3, height_meters=50)]))
    raw["run_start"] = None
    assert facts("save", json.dumps(raw).encode(), INITIAL) == (set(), None)


def test_preserved_native_segment_fixture_detects_progress_and_death():
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures/peak/native-segment-regression.json").read_text()
    )
    anchor, rise, loss = (item["row"] for item in fixture["samples"])
    raw = json.dumps({"run_start": anchor, "rows": [anchor, rise, loss]}).encode()
    found, terminal = facts("save", raw, fixture["initial"])
    assert found == {f"ascent_{n:03d}m" for n in range(1, 11)} and terminal == "death"
    assert found <= ASCENT_HEIGHTS.keys()
