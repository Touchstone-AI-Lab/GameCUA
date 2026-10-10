"""Preparation-only title and main-menu recognition against the snapshot's reference frames."""

import numpy as np


def menu_match(frame, reference):
    actual = np.asarray(frame.convert("RGB"))
    expected = np.asarray(reference.convert("RGB"))
    if actual.shape != (720, 1280, 3) or expected.shape != actual.shape:
        return False, {}
    deltas = {}
    for name, (left, top, right, bottom) in {
        "title": (90, 80, 350, 145),
        "menu": (90, 235, 350, 325),
    }.items():
        source = expected[top:bottom, left:right]
        target = actual[top:bottom, left:right]
        mask = source.max(axis=2) < 150
        background = source.min(axis=2) > 180
        deltas[name] = float(np.abs(target[mask].astype(float) - source[mask].astype(float)).mean())
        deltas[name + "_background"] = float(
            np.abs(target[background].astype(float) - source[background].astype(float)).mean()
        )
    return all(
        delta <= (20 if name.endswith("_background") else 35) for name, delta in deltas.items()
    ), deltas


def title_match(frame, reference):
    actual = np.asarray(frame.convert("RGB"))
    expected = np.asarray(reference.convert("RGB"))
    if actual.shape != (720, 1280, 3) or expected.shape != actual.shape:
        return False
    for left, top, right, bottom in ((75, 575, 365, 625), (75, 632, 370, 662)):
        source = expected[top:bottom, left:right]
        target = actual[top:bottom, left:right]
        text = source.min(axis=2) > 220
        background = source.min(axis=2) < 180
        if float(np.abs(target[text].astype(float) - source[text].astype(float)).mean()) > 35:
            return False
        if (
            float(
                np.abs(target[background].astype(float) - source[background].astype(float)).mean()
            )
            > 70
        ):
            return False
    return True
