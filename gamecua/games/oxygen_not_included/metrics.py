"""Native colony metrics decoded in one pass over an ONI save."""

from . import native

REPORT_TYPES = {1: "calories", 18: "oxygen_kg", 19: "energy_j"}
METALS = {
    "Aluminum",
    "Cobalt",
    "Copper",
    "Gold",
    "Iron",
    "Lead",
    "Niobium",
    "Steel",
    "Thermium",
    "Tungsten",
}
BATTERIES = {"Battery", "BatteryMedium", "BatterySmart"}
CROPS = {"BasicSingleHarvestPlant", "PrickleFlower", "MushroomPlant", "ColdWheat", "BeanPlant"}
WATER = 1836671383
SKIPPED = {("ReportManager", "noteStorageBytes"), ("ReportManager+ReportEntry", "contextEntries")}


class Decoder:
    """Decode nested records, lists and dictionaries from a save's templates."""

    def __init__(self, schema):
        self.schema = schema

    def record(self, reader, name):
        """Decode every field of a record except unbounded report payloads."""
        result = {}
        for field, info in self.schema[name]:
            if (name, field) in SKIPPED:
                native.scalar_or_skip(reader, info)
            else:
                result[field] = self.value(reader, info)
        return result

    def value(self, reader, info, element=False):
        """Decode one field value of any supported type."""
        code = info[0] & 63
        if code in native.SCALARS or code == 12:
            return native.scalar_or_skip(reader, info)
        if code == 0 and element and info[0] & 64:
            return self.record(reader, info[1])
        length = reader.unpack("i")
        if code in (17, 19, 20, 21, 22):
            count = reader.unpack("i")
            if count == -1:
                return None
        elif length == -1:
            return None
        nested = native.Reader(reader.take(length))
        if code == 0:
            return self.record(nested, info[1])
        if code == 19:
            values = [self.value(nested, info[2][1], True) for _ in range(count)]
            keys = [self.value(nested, info[2][0], True) for _ in range(count)]
            return dict(zip(keys, values))
        return [self.value(nested, info[2][0], True) for _ in range(count)]


def component(parts, schema, name, field):
    """Read one scalar field of an object's component."""
    return native.record(native.Reader(parts[name][0]), schema, name)[field]


def pipe_water(reader, schema):
    """Sum the water mass held in liquid conduits."""
    water = 0.0
    for field, _ in schema["ConduitFlow"]:
        length, count = reader.unpack("2i")
        if count == -1:
            continue
        nested = native.Reader(reader.take(length))
        if field == "versionedSerializedContents":
            for _ in range(count):
                item = native.record(nested, schema, "ConduitFlow+SerializedContents")
                if item["element"] == WATER:
                    water += item["mass"]
    return water


def generation(reader, schema):
    """Read cumulative energy produced by each generator type."""
    length, count = reader.unpack("2i")
    payload = native.Reader(reader.take(length))
    values = [payload.unpack("f") for _ in range(max(0, count))]
    result = {}
    for value in values:
        tag = native.Reader(payload.take(payload.unpack("i")))
        result[native.record(tag, schema, "Tag")["name"]] = value
    return result


def snapshot(raw):
    """Decode the native, metric, object and generation evidence of one save."""
    extended = {
        "stock_kg": {"refined_metal": 0.0, "plastic": 0.0, "steel": 0.0},
        "objects": {},
        "pipe_water_kg": 0.0,
        "consumed_j_by_day": {},
    }
    records, generated = {}, {}

    def observe(name, schema, parts):
        if name == "SaveGame":
            for key in ("Research", "ReportManager", "RationTracker"):
                records[key] = Decoder(schema).record(native.Reader(parts[key][0]), key)
        elif name == "Game+GameSaveData":
            reader = native.Reader(parts[name][0])
            for field, info in schema[name]:
                if field == "liquidConduitFlow":
                    nested = native.Reader(reader.take(reader.unpack("i")))
                    extended["pipe_water_kg"] = pipe_water(nested, schema)
                elif field == "savedInfo":
                    saved = native.Reader(reader.take(reader.unpack("i")))
                    for key, spec in schema["Game+SavedInfo"]:
                        if key == "powerCreatedbyGeneratorType":
                            generated.update(generation(saved, schema))
                        else:
                            native.scalar_or_skip(saved, spec)
                else:
                    native.scalar_or_skip(reader, info)
        elif name in METALS or name == "Polypropylene":
            mass = component(parts, schema, "PrimaryElement", "Units")
            stock = extended["stock_kg"]
            if name in METALS:
                stock["refined_metal"] += mass
            if name == "Steel":
                stock["steel"] += mass
            if name == "Polypropylene":
                stock["plastic"] += mass
        elif name in BATTERIES | CROPS:
            item = {"prefab": name}
            if name in BATTERIES:
                kind = "BatterySmart" if name == "BatterySmart" else "Battery"
                item["joules"] = component(parts, schema, kind, "joulesAvailable")
            else:
                item["planted"] = component(parts, schema, "HarvestDesignatable", "isInPlanterBox")
            identity = component(parts, schema, "KPrefabID", "InstanceID")
            extended["objects"][str(identity)] = item

    data = native.read_save(raw, observe)
    reports = records["ReportManager"]
    production = {}
    for report in [*reports["dailyReports"], reports["todaysReport"]]:
        entries = {entry["reportType"]: entry for entry in report["reportEntries"]}
        day = str(report["day"])
        production[day] = {
            key: entries[kind]["accPositive"] if kind in entries else 0.0
            for kind, key in REPORT_TYPES.items()
        }
        extended["consumed_j_by_day"][day] = -entries[19]["accNegative"] if 19 in entries else 0.0
    techs = records["Research"]["saveData"]["techs"]
    ration, day = records["RationTracker"], data["cycle"] + 1
    metrics = {
        "completed_technologies": sorted(tech["techId"] for tech in techs if tech["complete"]),
        "production_by_day": production,
        "manufactured_calories_by_day": {
            str(day + offset): ration[frame]["amountProduced"]
            for frame, offset in (("currentFrame", 0), ("previousFrame", -1))
            if day + offset >= 1
        },
    }
    return {"native": data, "metrics": metrics, "extended": extended, "generation": generated}
