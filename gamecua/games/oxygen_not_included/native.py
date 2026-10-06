"""ONI 7.38 save reader for object counts, the game clock and duplicant deaths."""

import hashlib
import json
import struct
import zlib

SCALARS = {
    1: "b",
    2: "B",
    3: "?",
    4: "h",
    5: "H",
    6: "i",
    7: "I",
    8: "q",
    9: "Q",
    10: "f",
    11: "d",
    13: "i",
    14: "2i",
    15: "2f",
    16: "3f",
    23: "4B",
}


class SaveFormatError(ValueError):
    """A save that is incomplete or not in the supported native format."""


class Reader:
    """Sequential little-endian reader over a byte buffer."""

    def __init__(self, raw):
        self.raw = memoryview(raw)
        self.pos = 0

    def take(self, size):
        """Return the next size bytes, rejecting reads past the end."""
        if not 0 <= size <= len(self.raw) - self.pos:
            raise SaveFormatError("Truncated or invalid native section length")
        value = self.raw[self.pos : self.pos + size]
        self.pos += size
        return value

    def unpack(self, fmt):
        """Unpack one struct value, or a list when the format has several."""
        values = struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))
        return values[0] if len(values) == 1 else list(values)

    def string(self):
        """Read a length-prefixed UTF-8 string."""
        length = self.unpack("i")
        return None if length == -1 else bytes(self.take(length)).decode("utf-8")


def type_info(reader):
    """Read one serialized type descriptor."""
    flags = reader.unpack("B")
    code = flags & 63
    name = reader.string() if code in (0, 13) else None
    children = []
    if flags & 128:
        children = [type_info(reader) for _ in range(reader.unpack("B"))]
    elif code == 17:
        children = [type_info(reader)]
    return flags, name, children


def templates(reader):
    """Read the save's type templates."""
    result = {}
    for _ in range(reader.unpack("i")):
        name = reader.string()
        members = reader.unpack("i") + reader.unpack("i")
        result[name] = [(reader.string(), type_info(reader)) for _ in range(members)]
    return result


def scalar_or_skip(reader, info):
    """Return a scalar or string field and skip any other field."""
    code = info[0] & 63
    if code in SCALARS:
        return reader.unpack(SCALARS[code])
    if code == 12:
        return reader.string()
    length = reader.unpack("i")
    if code in (17, 19, 20, 21, 22) and reader.unpack("i") == -1:
        return None
    if length != -1:
        reader.take(length)
    return None


def record(reader, schema, name):
    """Read a record's scalar fields by its template."""
    return {field: scalar_or_skip(reader, info) for field, info in schema[name]}


def dead(reader):
    """Return whether a duplicant's state machines put it in a dead state."""
    reader.unpack("i")
    machines = Reader(reader.take(reader.unpack("i")))
    for _ in range(machines.unpack("i")):
        machines.unpack("i")
        name = machines.string()
        length = machines.unpack("i")
        if length >= 0:
            machines.take(length)
        state = machines.string()
        machines.take(machines.unpack("i"))
        if name == "DeathMonitor+Instance":
            return state.startswith("root.dead")
    return False


def read_save(raw, object_observer=None):
    """Read object counts, clock and population, passing raw components to an observer."""
    size, compressed = struct.unpack_from("<4I", raw)[1::2]
    info = json.loads(bytes(raw[16 : 16 + size]))
    outer = Reader(raw[16 + size :])
    schema = templates(outer)
    payload = bytes(outer.take(len(outer.raw) - outer.pos))
    body = Reader(zlib.decompress(payload) if compressed else payload)
    body.string()
    for name in ("Klei.SaveFileRoot", "Game+Settings"):
        body.string()
        record(body, schema, name)
    body.take(body.unpack("i"))
    body.take(12)
    groups, clock, deaths = {}, {}, []
    for _ in range(body.unpack("i")):
        name, count = body.string(), body.unpack("i")
        group = Reader(body.take(body.unpack("i")))
        for _ in range(count):
            group.take(41)
            observed = {}
            for _ in range(group.unpack("i")):
                component = group.string()
                data = group.take(group.unpack("i"))
                if object_observer is not None:
                    observed.setdefault(component, []).append(bytes(data))
                if name == "SaveGame" and component == "GameClock":
                    clock = record(Reader(data), schema, component)
                elif name == "Minion" and component == "StateMachineController":
                    deaths.append(dead(Reader(data)))
            if object_observer is not None:
                object_observer(name, schema, observed)
        groups[name] = count
    body.string()
    if object_observer is not None:
        game = {"Game+GameSaveData": [bytes(body.raw[body.pos :])]}
        object_observer("Game+GameSaveData", schema, game)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "dlc_ids": info.get("dlcIds"),
        "cycle": clock.get("cycle", 0),
        "groups": groups,
        "population": {"living": deaths.count(False), "dead": deaths.count(True)},
    }
