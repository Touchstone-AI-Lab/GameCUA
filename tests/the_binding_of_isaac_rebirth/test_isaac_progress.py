"""Isaac predicates read from projected native log lines."""

import json
import signal
import subprocess
from pathlib import Path

from gamecua.games.the_binding_of_isaac_rebirth.integration import running, signal_group
from gamecua.games.the_binding_of_isaac_rebirth.progress import PREDICATES, facts, project
from gamecua.games.the_binding_of_isaac_rebirth.setup import normalize_seed
from gamecua.specs import Rubric

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/the-binding-of-isaac-rebirth"
INITIAL = {"episode_id": "episode-001", "seed": "MVSN TFS1"}


def test_points_rubric_uses_supported_predicates():
    path = FIXTURE.parents[2] / "benchmarks/rubrics/the-binding-of-isaac-rebirth/points-v1.json"
    rubric = Rubric.model_validate_json(path.read_text())
    assert {m.predicate for m in rubric.milestones} <= PREDICATES


def record(lines, **changes):
    return json.dumps({"schema_version": 1, **INITIAL, "lines": lines, **changes}).encode()


def operator_lines():
    return project((FIXTURE / "operator-log.txt").read_text())


def test_operator_log_records_only_leaving_the_start_room():
    lines = operator_lines()
    assert facts("save", record(lines[:-1]), INITIAL) == (set(), None)
    assert facts("save", record(lines), INITIAL) == ({"left_start_room"}, None)
    assert facts("history", b"agent claims victory", INITIAL) == (set(), None)


def test_floor_boss_mom_and_ending_lines_award_progress_and_victory():
    lines = operator_lines() + [
        "[INFO] - Adding collectible 1 (The Sad Onion)",
        "[INFO] - Boss 1 added to SaveState",
        "[INFO] - Level::Init m_Stage 3, m_StageType 0 Seed 1",
        "[INFO] - Level::Init m_Stage 6, m_StageType 0 Seed 2",
        "[INFO] - Mom clear time: 123",
        "[INFO] - playing cutscene 2 (Ending 1).",
    ]
    found, terminal = facts("save", record(lines), INITIAL)
    unmapped = {
        p
        for p in PREDICATES
        if p.startswith(("floor1_", "collectible_", "rooms_", "visited_", "treasure_floors_"))
    }
    unmapped -= {"collectible_1"}
    unmapped |= {"seventh_floor", "eighth_floor"}
    assert found == PREDICATES - unmapped and terminal == "victory"


def test_cutscene_before_mom_is_not_a_victory_and_death_is_terminal():
    lines = operator_lines() + ["[INFO] - playing cutscene 1 (Intro)."]
    assert facts("save", record(lines), INITIAL) == ({"left_start_room"}, None)
    lines.append("[INFO] - Game Over. Killed by (10.0) spawned by (0.0) damage flags (0)")
    assert facts("save", record(lines), INITIAL) == ({"left_start_room"}, "death")


def test_restart_ends_the_attempt_and_ignores_the_new_run():
    lines = operator_lines() + [
        "[INFO] - RNG Start Seed: MVSN TFS1 (1359984491)",
        "[INFO] - Level::Init m_Stage 2, m_StageType 0 Seed 1",
    ]
    assert facts("save", record(lines), INITIAL) == ({"left_start_room"}, "death")


def test_seed_normalization():
    assert normalize_seed("mvsntfs1") == "MVSN TFS1"


def test_repentance_run_start_suffix_is_accepted():
    lines = [
        "[INFO] - RNG Start Seed: MVSN TFS1 (1359984491) [New, 1]",
        "[INFO] - Level::Init m_Stage 1, m_StageType 0 Seed 1923844554",
        "[INFO] - Room 1.2(Start Room)",
        "[INFO] - Room 1.85()",
        "[INFO] - Adding collectible 1 (The Sad Onion) to player 0 (Isaac)",
    ]
    assert facts("save", record(project("\n".join(lines))), INITIAL) == (
        {"left_start_room", "collectible_1"},
        None,
    )


def test_observed_floor_mom_and_epilogue_lines_complete_the_floors_rubric():
    text = (FIXTURE / "console-mom-log.txt").read_text()
    found, terminal = facts("save", record(project(text)), INITIAL)
    assert {"second_floor", "caves", "fourth_floor", "depths", "mom_defeated"} <= found
    assert terminal == "victory"


FLOOR1_LINES = [
    "[INFO] - RNG Start Seed: MVSN TFS1 (1359984491) [New, 1]",
    "[INFO] - Level::Init m_Stage 1, m_StageType 0 Seed 1923844554",
    "[INFO] - Room 1.2(Start Room)",
    "[INFO] - Room 4.1()",
    "[INFO] - Adding collectible 395 (Tech X) to player 0 (Isaac)",
    "[INFO] - Room 1.660(New Room)",
    "[INFO] - Room 1.941(New Room)",
    "[INFO] - Room 1.916(New Room)",
]


def test_floor1_distance_and_collectibles_follow_the_exported_map():
    found, terminal = facts("save", record(FLOOR1_LINES), INITIAL)
    assert {"floor1_closer_1", "floor1_closer_2", "floor1_closer_3", "collectible_1"} <= found
    assert not {"floor1_closer_4", "collectible_2"} & found and terminal is None
    boss = FLOOR1_LINES + [
        "[INFO] - Room 5.1024(Monstro)",
        "[INFO] - Adding collectible 1 (The Sad Onion) to player 0 (Isaac)",
    ]
    assert {"floor1_closer_4", "collectible_2"} <= facts("save", record(boss), INITIAL)[0]


def test_rooms_on_another_floor_or_seed_earn_no_distance():
    other = [line.replace("Seed 1923844554", "Seed 1") for line in FLOOR1_LINES]
    assert not any(p.startswith("floor1_closer") for p in facts("save", record(other), INITIAL)[0])
    later = (
        FLOOR1_LINES[:2]
        + ["[INFO] - Level::Init m_Stage 2, m_StageType 0 Seed 5"]
        + FLOOR1_LINES[5:]
    )
    assert not any(p.startswith("floor1_closer") for p in facts("save", record(later), INITIAL)[0])


def test_leaving_a_room_with_enemies_clears_it_and_empty_rooms_do_not_count():
    found, _ = facts("save", record(FLOOR1_LINES), INITIAL)
    assert "floor1_cleared_1" in found and "floor1_cleared_2" not in found
    boss = FLOOR1_LINES + ["[INFO] - Room 5.1024(Monstro)"]
    assert {"floor1_cleared_1", "floor1_cleared_2"} <= facts("save", record(boss), INITIAL)[0]
    empty = FLOOR1_LINES[:4] + ["[INFO] - Room 1.85(New Room)", "[INFO] - Room 1.2(Start Room)"]
    assert not any(p.startswith("floor1_cleared") for p in facts("save", record(empty), INITIAL)[0])


def test_death_inside_a_room_with_enemies_does_not_clear_it():
    lines = FLOOR1_LINES[:3] + [
        "[INFO] - Room 1.660(New Room)",
        "[INFO] - Game Over. Killed by (276.0) spawned by (0.0) damage flags (4)",
    ]
    found, terminal = facts("save", record(lines), INITIAL)
    assert terminal == "death" and "floor1_closer_1" in found
    assert not any(p.startswith("floor1_cleared") for p in found)


def test_clears_count_only_on_the_mapped_floor():
    other = [line.replace("Seed 1923844554", "Seed 1") for line in FLOOR1_LINES]
    assert not any(p.startswith("floor1_cleared") for p in facts("save", record(other), INITIAL)[0])


def test_room_counts_special_rooms_and_treasure_floors_come_from_logged_rooms():
    lines = FLOOR1_LINES + [
        "[INFO] - Room 2.0(Shop L1)",
        "[INFO] - Room 7.37(Secret Room)",
        "[INFO] - Level::Init m_Stage 2, m_StageType 0 Seed 5",
        "[INFO] - Room 1.2(Start Room)",
        "[INFO] - Room 4.3()",
        "[INFO] - Room 14.1(Devil Room)",
    ]
    found, _ = facts("save", record(lines), INITIAL)
    assert {"visited_shop", "visited_secret", "visited_devil", "visited_treasure"} <= found
    assert {"treasure_floors_2", "rooms_8"} <= found and "rooms_12" not in found
    assert not {"visited_angel", "visited_library", "treasure_floors_3"} & found


def test_floor1_is_explored_only_when_every_normal_room_is_entered():
    assert "floor1_explored" not in facts("save", record(FLOOR1_LINES), INITIAL)[0]
    lines = FLOOR1_LINES + ["[INFO] - Room 1.85(New Room)"]
    assert "floor1_explored" in facts("save", record(lines), INITIAL)[0]


def test_twelve_collectibles_and_womb_floors():
    lines = FLOOR1_LINES[:3] + [
        f"[INFO] - Adding collectible {k} (Item) to player 0 (Isaac)" for k in range(1, 13)
    ]
    lines += [f"[INFO] - Level::Init m_Stage {n}, m_StageType 0 Seed {n}" for n in range(2, 9)]
    found, _ = facts("save", record(lines), INITIAL)
    assert {"collectible_12", "seventh_floor", "eighth_floor"} <= found


def test_group_signal_needs_the_recorded_leader():
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        stat = Path(f"/proc/{child.pid}/stat").read_text()
        identity = {"pid": child.pid, "start_ticks": stat.rsplit(")", 1)[1].split()[19]}
        signal_group({**identity, "start_ticks": "0"}, signal.SIGTERM)
        assert child.poll() is None and running(identity)
        signal_group(identity, signal.SIGTERM)
        assert child.wait(timeout=5) == -signal.SIGTERM and not running(identity)
    finally:
        child.kill()
        child.wait()
