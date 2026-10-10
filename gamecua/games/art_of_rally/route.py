"""Directed XZ gate crossings of native route segments and checkpoint segment selection."""

import json
import math
from functools import lru_cache

SELECTION = "ordered-nearest-3d-midpoint-19-v1"
LATERAL_RADIUS = 2.0
HEIGHT_RADIUS = 2.0


def vector(raw):
    return tuple(float(raw[k]) for k in ("x", "y", "z"))


def interpolate(a, b, fraction):
    return tuple(x + (y - x) * fraction for x, y in zip(a, b))


def edges(geometry, start, last):
    points = [vector(p) for p in json.loads(geometry)["points"]][start : last + 1]
    return list(zip(points, points[1:]))


@lru_cache(maxsize=32)
def select_segments(geometry, start, last):
    segments = edges(geometry, start, last)
    lengths = [math.dist(a, b) for a, b in segments]
    total = math.fsum(lengths)
    midpoints, distance = [], 0.0
    for length in lengths:
        midpoints.append(distance + length / 2)
        distance += length
    selected, previous = [], -1
    for number in range(1, 20):
        target = total * number / 20
        index = min(
            range(previous + 1, len(segments) - (19 - number)),
            key=lambda candidate: (abs(midpoints[candidate] - target), candidate),
        )
        selected.append(index + start)
        previous = index
    return tuple(selected)


def selection(anchor):
    return select_segments(anchor["coverage"]["geometry"], anchor["start"], anchor["last"])


class Coverage:
    def __init__(self, row):
        self.edges = edges(row["coverage"]["geometry"], row["start"], row["last"])
        self.axes = tuple((b[0] - a[0], b[2] - a[2]) for a, b in self.edges)
        self.lengths = tuple(x * x + z * z for x, z in self.axes)
        self.covered = {}
        self.active = {}
        self.previous = row

    def suspend(self):
        self.active = {}
        self.previous = None

    def pause(self, row):
        if self.previous is None or vector(self.previous["position"]) != vector(row["position"]):
            self.active = {}
        self.previous = row

    def along(self, index, point):
        a, _ = self.edges[index]
        dx, dz = self.axes[index]
        return ((point[0] - a[0]) * dx + (point[2] - a[2]) * dz) / self.lengths[index]

    def inside(self, index, point, fraction):
        a, b = self.edges[index]
        center = interpolate(a, b, min(1, max(0, fraction)))
        return (
            math.hypot(point[0] - center[0], point[2] - center[2]) <= LATERAL_RADIUS
            and abs(point[1] - center[1]) <= HEIGHT_RADIUS
        )

    def advance(self, row):
        previous, self.previous = self.previous, row
        if previous is None:
            return
        before, after = vector(previous["position"]), vector(row["position"])
        active = dict(self.active)
        intervals = {}
        for index in range(len(self.edges)):
            start, end = self.along(index, before), self.along(index, after)
            if index in active and (end < 0 or (end < 1 and not self.inside(index, after, end))):
                del active[index]
            if start == end:
                continue
            low, high = sorted(((0 - start) / (end - start), (1 - start) / (end - start)))
            low, high = max(0, low), min(1, high)
            if low > high:
                continue
            first, last = interpolate(before, after, low), interpolate(before, after, high)
            if not (
                self.inside(index, first, self.along(index, first))
                and self.inside(index, last, self.along(index, last))
            ):
                active.pop(index, None)
                continue
            intervals[index] = (low, high, start, end)
        ambiguous = set()
        for index, (low, high, _, _) in intervals.items():
            for other, (other_low, other_high, _, _) in intervals.items():
                if abs(index - other) > 1 and max(low, other_low) <= min(high, other_high):
                    ambiguous.update((index, other))
        for index in ambiguous:
            active.pop(index, None)
        for index, (_, _, start, end) in intervals.items():
            if index in ambiguous or end <= start:
                continue
            if start <= 0 < end:
                active[index] = previous["sequence"]
            if start < 1 <= end and index in active:
                self.covered.setdefault(index + row["start"], [active.pop(index), row["sequence"]])
        self.active = active
