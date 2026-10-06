"""Synthetic ONI save framing and duplicant-death decoding."""

import json
import struct
import zlib

import pytest

from gamecua.games.oxygen_not_included.native import Reader, SaveFormatError, dead, read_save
from gamecua.games.oxygen_not_included.progress import facts


def integer(value):
    """Pack a little-endian int32."""
    return struct.pack("<i", value)


def string(value):
    """Pack a length-prefixed UTF-8 string."""
    raw = value.encode()
    return integer(len(raw)) + raw


def machine_payload(state="root.alive"):
    """Build a StateMachineController payload with one death monitor."""
    machine = integer(0) + string("DeathMonitor+Instance") + integer(-1) + string(state)
    machine += integer(4) + integer(0)
    machines = integer(1) + machine
    return integer(20) + integer(len(machines)) + machines


def synthetic_save(groups=(), cycle=0, dead=0, compressed=True, dlc_ids=None):
    """Build a minimal native save with object groups, a clock and three duplicants."""
    groups = list(groups)
    if not any(name == "Minion" for name, _ in groups):
        groups.append(("Minion", 3))
    schemas = {
        "Klei.SaveFileRoot": [],
        "Game+Settings": [],
        "GameClock": [("cycle", 6), ("timeSinceStartOfCycle", 10), ("frame", 6)],
        "StateMachineController": [],
        "Game+GameSaveData": [("debugWasUsed", 3)],
    }
    templates = integer(len(schemas))
    for name, members in schemas.items():
        templates += string(name) + integer(len(members)) + integer(0)
        for field, kind in members:
            templates += string(field) + bytes([kind])
    clock = integer(cycle) + struct.pack("<f", 0.0) + integer(cycle * 100)
    instance = struct.pack("<10fB", *([0.0] * 10), 0) + integer(1)
    instance += string("GameClock") + integer(len(clock)) + clock
    objects = string("SaveGame") + integer(1) + integer(len(instance)) + instance
    for name, count in groups:
        instances = (struct.pack("<10fB", *([0.0] * 10), 0) + integer(0)) * count
        if name == "Minion":
            instances = b""
            for index in range(count):
                machine = machine_payload("root.dead.ground" if index < dead else "root.alive")
                component = string("StateMachineController") + integer(len(machine)) + machine
                instances += struct.pack("<10fB", *([0.0] * 10), 0) + integer(1) + component
        objects += string(name) + integer(count) + integer(len(instances)) + instances
    body = string("world") + string("Klei.SaveFileRoot") + string("Game+Settings") + integer(0)
    body += b"KSAV" + integer(7) + integer(38) + integer(len(groups) + 1) + objects
    body += string("Game+GameSaveData") + b"\x00"
    info = {"dlcIds": ["EXPANSION1_ID"] if dlc_ids is None else dlc_ids}
    header = json.dumps(info).encode()
    return (
        struct.pack("<4I", 744825, len(header), 1, compressed)
        + header
        + templates
        + (zlib.compress(body) if compressed else body)
    )


@pytest.mark.parametrize("compressed", [False, True])
def test_completed_and_blueprint_groups_are_counted_separately(compressed):
    data = read_save(
        synthetic_save([("Bed", 1), ("BedUnderConstruction", 2)], cycle=4, compressed=compressed)
    )
    assert data["groups"]["Bed"] == 1
    assert data["groups"]["BedUnderConstruction"] == 2
    assert data["cycle"] == 4
    assert data["dlc_ids"] == ["EXPANSION1_ID"]


def test_truncated_saves_raise_instead_of_decoding():
    raw = synthetic_save(compressed=False)
    for end in range(len(raw) - 2, 60, -7):
        with pytest.raises((ValueError, struct.error)):
            read_save(raw[:end])
    with pytest.raises(zlib.error):
        read_save(synthetic_save()[:-1])
    with pytest.raises(SaveFormatError):
        Reader(b"abc").take(4)


@pytest.mark.parametrize("dead,terminal", [(0, None), (1, None), (2, None), (3, "death")])
def test_death_requires_every_duplicant_dead(dead, terminal):
    raw = synthetic_save(dead=dead)
    assert read_save(raw)["population"] == {"living": 3 - dead, "dead": dead}
    assert facts("save", raw, None) == (set(), terminal)


def test_only_the_death_monitor_decides_death():
    unrelated = integer(0) + string("SyntheticMonitor") + integer(-1) + string("root.dead.ground")
    unrelated += integer(4) + integer(0)
    machines = integer(2) + unrelated + machine_payload()[12:]
    assert dead(Reader(integer(20) + integer(len(machines)) + machines)) is False
    assert dead(Reader(machine_payload("root.dead.ground"))) is True
