"""Baseline-relative Factorio bootstrap predicates from native telemetry samples."""

import json

VERSION = 4
PRODUCTION_TARGETS = (1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100, 150, 250, 500, 1000)
SCIENCE_TARGETS = (1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 75, 90, 100, 125, 150, 175, 200)
FAMILIES = {
    "iron-ore": (("produced", "iron-ore"), PRODUCTION_TARGETS),
    "iron-plate": (("produced", "iron-plate"), PRODUCTION_TARGETS),
    "copper-plate": (("produced", "copper-plate"), PRODUCTION_TARGETS),
    "iron-gear-wheel": (("produced", "iron-gear-wheel"), PRODUCTION_TARGETS),
    "new-furnace-iron": (("automated_iron",), PRODUCTION_TARGETS),
    "automation-science-used": (("consumed", "automation-science-pack"), SCIENCE_TARGETS),
}
PROGRESS_POINTS = {
    f"bootstrap_{family.replace('-', '_')}_{target}": (field, target)
    for family, (field, targets) in FAMILIES.items()
    for target in targets
}
PREDICATES = set(PROGRESS_POINTS)


def value(sample, field):
    """Read one nested native counter."""
    for key in field:
        sample = sample[key]
    return sample


def facts(kind, raw, initial):
    """Return bootstrap predicates reached in one evidence file and any native terminal state."""
    if kind != "save":
        return set(), None
    found = set()
    for row in json.loads(raw):
        found.update(
            predicate
            for predicate, (field, target) in PROGRESS_POINTS.items()
            if value(row, field) - value(initial, field) >= target
        )
        if not row["alive"]:
            return found, "death"
        if row["rockets_launched"] > initial["rockets_launched"]:
            return found, "victory"
    return found, None
