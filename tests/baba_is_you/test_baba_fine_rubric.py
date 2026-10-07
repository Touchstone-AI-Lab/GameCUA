"""The v5 rubric: progress thresholds and named levels read from synthetic slot saves."""

from pathlib import Path

from gamecua.games.baba_is_you.progress import CHOICE_LEVELS, PREDICATES, facts
from gamecua.games.baba_is_you.saves import read_save
from gamecua.specs import Rubric

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/baba-is-you"
RUBRIC = Rubric.model_validate_json(
    (ROOT / "benchmarks/rubrics/baba-is-you/victory-v5.json").read_text()
)
LAKE = ["20level", "212level", "10level", "4level", "93level", "209level", "15level", "8level"]


def save(*cleared, prizes=None, entered=()):
    lines = ["[baba]"] + [f"{name}=3" for name in cleared]
    lines += [f"{name}_intro=1" for name in entered] + ["[baba_prize]", "total=0"]
    lines += [f"{name}={count}" for name, count in (prizes or {}).items()]
    return "\n".join(lines).encode()


def found(*cleared, prizes=None, entered=(), initial=b""):
    return facts("save", save(*cleared, prizes=prizes, entered=entered), read_save(initial))[0]


def test_more_than_fifty_independent_points_total_one_hundred():
    predicates = [m.predicate for m in RUBRIC.milestones]
    assert len(RUBRIC.milestones) == 52 and sum(m.points for m in RUBRIC.milestones) == 100
    assert len(set(predicates)) == 52 and set(predicates) == PREDICATES
    assert all(not m.prerequisites and m.points <= 10 for m in RUBRIC.milestones)
    choice = [p for p in predicates if p.startswith("cleared_")]
    assert len(choice) == len(CHOICE_LEVELS) == 26 and len(predicates) - len(choice) == 26


def test_named_levels_and_total_count():
    result = found("0level", "1level", "189level", "2level")
    assert {"level_0", "level_1", "opening_3", "cleared_189level", "cleared_2level"} <= result
    assert "levels_8" not in result and "opening_4" not in result
    assert "levels_8" in found(*LAKE)
    assert not found("117level")


def test_lake_counts_use_the_game_prize_counter():
    assert {f"lake_levels_{n}" for n in range(1, 4)} <= found(prizes={"177level": 3})
    assert "lake_levels_4" not in found(prizes={"177level": 3})
    assert "lake_levels_1" not in found(prizes={"106level": 6})
    assert "lake_levels_2" not in found(
        prizes={"177level": 2}, initial=save(prizes={"177level": 1})
    )


def test_area_counts_split_the_lake_from_other_areas():
    result = found(prizes={"177level": 8, "207level": 4})
    assert {"area_levels_12", "other_area_levels_1", "other_area_levels_4"} <= result
    assert "area_levels_15" not in result
    assert "other_area_levels_1" not in found(prizes={"177level": 10})


def test_entered_areas_are_new_intro_flags_of_numbered_areas():
    assert "areas_entered_1" in found(entered=["177level"])
    assert "areas_entered_2" not in found(entered=["177level", "106level", "0level"])
    assert "areas_entered_2" in found(entered=["177level", "207level"])
    assert "areas_entered_1" not in found(entered=["177level"], initial=save(entered=["177level"]))


def test_area_completion_points():
    lake = found("177level")
    assert "lake_complete" in lake and "second_area_complete" not in lake
    assert {"lake_complete", "second_area_complete"} <= found("177level", "207level")
    assert "lake_complete" not in found("207level", "206level")


def test_game_written_lake_save_earns_the_lake_points():
    before = read_save((FIXTURES / "lake-area-crafted-input.ba").read_bytes())
    after = (FIXTURES / "lake-area-complete.ba").read_bytes()
    assert facts("save", after, before)[0] == {"lake_complete", "areas_entered_1"}
    assert "177level" in read_save(after)["entered"]


def test_first_levels_count_in_route_order():
    assert "level_0" in found("0level") and "level_1" not in found("0level")
    assert {"level_0", "level_1"} <= found("0level", "1level")
    assert "level_1" not in found("1level")


def test_opening_three_needs_the_forced_levels_and_either_successor():
    assert "opening_3" not in found("0level", "1level")
    assert "opening_3" in found("0level", "1level", "189level")
    assert "opening_3" in found("0level", "1level", "3level")
    assert "opening_3" not in found("0level", "189level", "3level")


def test_opening_four_needs_a_level_before_the_first_area():
    assert "opening_4" not in found("0level", "1level", "189level", "3level")
    assert "opening_4" in found("0level", "1level", "3level", "5level")
    assert "opening_4" in found("0level", "1level", "189level", "6level")
    assert "opening_4" not in found("0level", "1level", "5level", "6level")
