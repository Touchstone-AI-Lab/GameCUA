"""Hotel points require a living human, fixed route positions and the native map transition."""

import json

from gamecua.games.left_4_dead_2.progress import MAPS, ROUTE, facts, route_progress


def baseline():
    return {
        "schema": 1,
        "session": "episode",
        "map": MAPS[0],
        "mode": "coop",
        "difficulty": "Easy",
        "cheats": 0,
        "human_alive": True,
        "kind": "sample",
        "time": 30.0,
        "x": 518.0,
        "y": 5632.0,
        "z": 2848.0,
        "kills": 2,
        "specials": 0,
        "heals": 0,
        "revives": 0,
    }


def evaluate(**updates):
    initial = baseline()
    return facts("history", json.dumps([{**initial, **updates}]).encode(), initial)


def test_preparation_and_bot_kills_are_not_player_points():
    assert evaluate(bot_kills=100) == (set(), None)


def test_combat_counters_earn_collection_points_over_the_baseline():
    assert evaluate(kills=7, specials=5, heals=1, revives=1)[0] == {
        "specials_1",
        "specials_2",
        "specials_3",
        "specials_5",
        "heals_1",
        "revives_1",
    }
    assert evaluate(kills=12)[0] == {"kills_10"}


def on_route(fraction, **updates):
    leg = ROUTE["legs"][0]
    target = ROUTE["length"] * fraction
    for a, b in zip(leg, leg[1:]):
        if a[3] <= target <= b[3]:
            t = (target - a[3]) / (b[3] - a[3])
            point = {k: a[i] + t * (b[i] - a[i]) for i, k in enumerate("xyz")}
            return evaluate(**point, **updates)
    raise AssertionError("fraction is not on the first leg")


def test_start_position_earns_nothing():
    assert evaluate() == (set(), None)


def test_progress_is_the_floor_of_the_route_percentage_reached():
    start = route_progress(518.0, 5632.0, 2848.0)
    for fraction in (0.02, 0.1, 0.25, 0.5):
        found = on_route(fraction)[0]
        expected = int(100 * (fraction * ROUTE["length"] - start) / (ROUTE["length"] - start))
        assert {f"route_{k}" for k in range(1, expected + 1)} <= found
        assert len(found) <= expected + 2
    assert on_route(0.25, human_alive=False)[0] == set()


def test_positions_off_the_route_earn_nothing():
    assert evaluate(x=5000.0, y=5000.0, z=2848.0)[0] == set()
    assert evaluate(x=518.0, y=5632.0, z=2400.0)[0] == set()


def test_chapter_completion_is_the_victory_and_needs_the_living_human():
    found, terminal = evaluate(kind="chapter_complete")
    assert terminal == "victory"
    assert found == {f"route_{k}" for k in range(1, 100)} | {"chapter_complete"}
    assert evaluate(kind="chapter_complete", human_alive=False)[0] == set()
    assert evaluate(kind="chapter_complete", map=MAPS[1])[0] == set()


def test_native_terminal_events():
    assert evaluate(kind="human_death", human_alive=False)[1] == "death"
    assert evaluate(kind="mission_lost")[1] == "death"
    assert evaluate(kind="campaign_complete", map=MAPS[0]) == (set(), None)
