"""Synthetic native save fixtures; never benchmark results."""

from pathlib import Path

import pytest

from gamecua.catalog import Catalog
from gamecua.games.untitled_goose_game.progress import PREDICATES, facts
from gamecua.games.untitled_goose_game.saves import GOALS, SaveFormatError, read_save

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/untitled-goose-game"


def test_v5_rubric_awards_each_native_task_and_all_specs_use_it():
    catalog = Catalog(ROOT / "benchmarks")
    rubric = catalog.rubrics["untitled-goose-game-native-tasks-v5"]
    assert {m.predicate for m in rubric.milestones} == PREDICATES
    assert sum(m.points for m in rubric.milestones) == 100
    assert catalog.games["untitled-goose-game"].budget == "time"
    specs = [t for t in catalog.trials.values() if t.game_id == "untitled-goose-game"]
    assert specs and all(t.rubric_id == rubric.id for t in specs)


def test_reads_binaryformatter_entries():
    assert read_save((FIXTURES / "partial.synthetic.save").read_bytes()) == {
        "completed": ["goalHammering"]
    }


def test_complete_native_save_scores_every_task_and_victory():
    raw = (FIXTURES / "complete.synthetic.save").read_bytes()
    assert facts("save", raw, {"completed": []}) == (set(GOALS), "victory")


def test_partial_progress_is_gradual():
    one = (FIXTURES / "partial.synthetic.save").read_bytes()
    assert facts("save", one, {"completed": []}) == ({"goalHammering"}, None)


def test_baseline_progress_is_not_credited_again():
    raw = (FIXTURES / "complete.synthetic.save").read_bytes()
    assert facts("save", raw, read_save(raw)) == (set(), None)


@pytest.mark.parametrize("raw", [b"", b"not a BinaryFormatter stream"])
def test_rejects_malformed_save(raw):
    with pytest.raises(SaveFormatError):
        read_save(raw)
