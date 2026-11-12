"""The read-only tuner channel returns one parsed base-game checkpoint per query."""

import struct

import pytest

from gamecua.games.civilization_vi.base_game import (
    QUERY,
    NativeBaseGame,
    NativeChannelError,
    parse,
)

PROJECTS = (
    "PROJECT_LAUNCH_EARTH_SATELLITE",
    "PROJECT_LAUNCH_MOON_LANDING",
    "PROJECT_LAUNCH_MARS_REACTOR",
    "PROJECT_LAUNCH_MARS_HABITATION",
    "PROJECT_LAUNCH_MARS_HYDROPONICS",
)
LINES = [
    "GBASE_CONFIG|CIVILIZATION_AZTEC|RULESET_STANDARD|DIFFICULTY_PRINCE|ERA_ANCIENT|2|1",
    "GBASE_MOD|02A8BDDE-67EA-4D38-9540-26E685E3156E",
    "GBASE_STATE|2|0|0|true|1|-1|NONE",
    "GBASE_VICTORY|VICTORY_TECHNOLOGY",
    *[f"GBASE_PROJECT|{name}|0" for name in PROJECTS],
    "GBASE_TECH|TECH_POTTERY",
    "GBASE_CITY|65536|0",
    "GBASE_BUILDING|65536|0|BUILDING_PALACE|false",
    "GBASE_DISTRICT|65536|0|DISTRICT_CITY_CENTER|true|false",
    "GBASE_UNIT|1114114|0|UNIT_BUILDER",
    "GBASE_COMPLETE|technologies,cities,buildings,districts,units",
]


def test_parser_keeps_the_native_inventory_layout():
    state = parse(LINES)
    assert state["active_mod_ids"] == ["02a8bdde-67ea-4d38-9540-26e685e3156e"]
    assert (state["turn"], state["native_player_id"], state["alive"], state["cities"]) == (
        2,
        0,
        True,
        1,
    )
    assert state["projects"] == dict.fromkeys(PROJECTS, 0)
    assert state["technologies"] == ["TECH_POTTERY"]
    assert state["buildings"] == [
        {"city": 65536, "owner": 0, "type": "BUILDING_PALACE", "pillaged": False}
    ]
    assert state["districts"][0]["complete"] and not state["districts"][0]["pillaged"]
    assert state["units"] == [{"id": 1114114, "owner": 0, "type": "UNIT_BUILDER"}]
    with pytest.raises(ValueError, match="query failed"):
        parse(LINES + ["GBASE_ERROR|missing native API"])


class FragmentedSocket:
    def __init__(self, messages):
        self.data = b"".join(
            struct.pack("<Ii", len(message.encode()) + 1, 4) + message.encode() + b"\x00"
            for message in messages
        )
        self.sent = []
        self.closed = False

    def recv(self, count):
        result, self.data = self.data[: min(count, 3)], self.data[min(count, 3) :]
        return result

    def sendall(self, data):
        self.sent.append(data)

    def settimeout(self, value):
        assert value > 0

    def close(self):
        self.closed = True


def native_messages():
    return [
        "Civ6\x00Sid Meier's Civilization 6",
        "\x00".join(("0", "Main State", "4", "InGame")),
        *[f"O\x00InGame: {line}" for line in LINES],
        "O\x00InGame: GBASE_END",
    ]


def test_fragmented_messages_use_only_the_fixed_read_query(monkeypatch):
    transport = FragmentedSocket(native_messages())
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: transport)
    reader = NativeBaseGame()
    assert reader.read() == parse(LINES)
    assert len(transport.sent) == 3
    command = transport.sent[-1]
    assert struct.unpack("<Ii", command[:8]) == (len(command) - 8, 3)
    assert command[8:] == ("CMD:4:" + QUERY).encode() + b"\x00"
    reader.close()
    assert transport.closed


@pytest.mark.parametrize("header", [struct.pack("<Ii", 0, 3), struct.pack("<Ii", 1048577, -1), b""])
def test_broken_channel_reconnects_once_without_replaying_game_actions(monkeypatch, header):
    first = FragmentedSocket(native_messages())
    first.data += header
    second = FragmentedSocket(native_messages())
    connections = iter((first, second))
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: next(connections))
    reader = NativeBaseGame()
    assert reader.read() == reader.read() == parse(LINES)
    assert first.closed and len(first.sent) == 4 and len(second.sent) == 3


def test_reconnection_is_bounded_and_closes_both_connections(monkeypatch):
    connections = [FragmentedSocket([]), FragmentedSocket([])]
    pending = iter(connections)
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: next(pending))
    with pytest.raises(NativeChannelError, match="channel closed"):
        NativeBaseGame().read()
    assert all(connection.closed for connection in connections)
