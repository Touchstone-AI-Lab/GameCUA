"""Decoding of native ONI reports, conduits, generation and colony objects."""

import struct

import pytest

from gamecua.games.oxygen_not_included import metrics
from gamecua.games.oxygen_not_included.native import Reader

from .test_native import string

ENTRY = [
    ("noteStorageId", (6, None, [])),
    ("gameHash", (6, None, [])),
    ("reportType", (6, None, [])),
    ("context", (12, None, [])),
    ("accPositive", (10, None, [])),
    ("contextEntries", (128, "Nested", [])),
]


def test_report_context_entries_are_skipped():
    raw = struct.pack("<iii", 0, 0, 19) + string("generator") + struct.pack("<f", 100)
    raw += struct.pack("<i", 6) + b"nested"
    reader = Reader(raw)
    result = metrics.Decoder({"ReportManager+ReportEntry": ENTRY}).record(
        reader, "ReportManager+ReportEntry"
    )
    assert reader.pos == len(raw)
    assert result == {
        "noteStorageId": 0,
        "gameHash": 0,
        "reportType": 19,
        "context": "generator",
        "accPositive": 100,
    }


def test_decoder_reads_lists_and_dictionaries():
    text, number = (12, None, []), (10, None, [])
    schema = {"Root": [("names", (17, None, [text])), ("map", (147, None, [text, number]))]}
    names = string("a") + string("b")
    values = struct.pack("<f", 1.5) + string("k")
    raw = struct.pack("<ii", len(names), 2) + names + struct.pack("<ii", len(values), 1) + values
    assert metrics.Decoder(schema).record(Reader(raw), "Root") == {
        "names": ["a", "b"],
        "map": {"k": 1.5},
    }


def test_pipe_water_sums_only_water_mass():
    schema = {
        "ConduitFlow": [
            (name, (17, None, []))
            for name in ("serializedIdx", "serializedContents", "versionedSerializedContents")
        ],
        "ConduitFlow+SerializedContents": [
            ("element", (13, "SimHashes", [])),
            ("mass", (10, None, [])),
            ("temperature", (10, None, [])),
            ("diseaseHash", (6, None, [])),
            ("diseaseCount", (6, None, [])),
        ],
    }
    contents = struct.pack("<iffii", metrics.WATER, 10.0, 295.0, 0, 0)
    contents += struct.pack("<iffii", 7, 50.0, 295.0, 0, 0)
    raw = struct.pack("<iiii", 8, 2, 10, 11) + struct.pack("<ii", 0, -1)
    raw += struct.pack("<ii", len(contents), 2) + contents
    assert metrics.pipe_water(Reader(raw), schema) == 10.0


@pytest.mark.parametrize("entries", [[("Generator", 100000)], [], [("ManualGenerator", 1.5)]])
def test_generation_dictionary(entries):
    payload = b"".join(struct.pack("<f", value) for _, value in entries)
    for name, _ in entries:
        tag = string(name) + struct.pack("<i", 0)
        payload += struct.pack("<i", len(tag)) + tag
    raw = struct.pack("<ii", len(payload), len(entries)) + payload
    schema = {"Tag": [("name", (12, None, [])), ("hash", (6, None, []))]}
    assert metrics.generation(Reader(raw), schema) == dict(entries)


def test_objects_record_stock_batteries_and_crops(monkeypatch):
    schema = {
        "KPrefabID": [("InstanceID", (6, None, []))],
        "PrimaryElement": [("Units", (10, None, []))],
        "Battery": [("joulesAvailable", (10, None, []))],
        "BatterySmart": [("joulesAvailable", (10, None, []))],
        "HarvestDesignatable": [("isInPlanterBox", (3, None, []))],
    }

    def parts(identity, **values):
        result = {"KPrefabID": [struct.pack("<i", identity)]}
        for key, (fmt, value) in values.items():
            result[key] = [struct.pack(fmt, value)]
        return result

    def read(raw, observe):
        for identity, name, mass in ((1, "Steel", 100), (2, "Polypropylene", 50), (3, "Iron", 7)):
            observe(name, schema, parts(identity, PrimaryElement=("<f", mass)))
        observe("SteelUnderConstruction", schema, parts(4, PrimaryElement=("<f", 1000)))
        observe("BatteryMedium", schema, parts(5, Battery=("<f", 25)))
        observe("BatterySmart", schema, parts(6, BatterySmart=("<f", 30)))
        observe("PrickleFlower", schema, parts(7, HarvestDesignatable=("<?", True)))
        records = {
            "Research": {"saveData": {"techs": [{"techId": "Jobs", "complete": True}]}},
            "ReportManager": {
                "dailyReports": [],
                "todaysReport": {
                    "day": 1,
                    "reportEntries": [
                        {"reportType": 19, "accPositive": 5.0, "accNegative": -3.0},
                        {"reportType": 1, "accPositive": 9.0, "accNegative": 0.0},
                    ],
                },
            },
            "RationTracker": {
                "currentFrame": {"amountProduced": 4.0},
                "previousFrame": {"amountProduced": 2.0},
            },
        }
        monkeypatch.setattr(metrics.Decoder, "record", lambda self, reader, name: records[name])
        observe("SaveGame", schema, dict.fromkeys(records, [b""]))
        return {"cycle": 0}

    monkeypatch.setattr(metrics.native, "read_save", read)
    result = metrics.snapshot(b"synthetic")
    extended = result["extended"]
    assert extended["stock_kg"] == {"refined_metal": 107, "plastic": 50, "steel": 100}
    assert extended["objects"] == {
        "5": {"prefab": "BatteryMedium", "joules": 25},
        "6": {"prefab": "BatterySmart", "joules": 30},
        "7": {"prefab": "PrickleFlower", "planted": True},
    }
    assert extended["consumed_j_by_day"] == {"1": 3.0}
    assert result["metrics"] == {
        "completed_technologies": ["Jobs"],
        "production_by_day": {"1": {"calories": 9.0, "oxygen_kg": 0.0, "energy_j": 5.0}},
        "manufactured_calories_by_day": {"1": 4.0},
    }
