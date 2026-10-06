"""Recognize the native Colony Lost screen and preserve it as a loss receipt."""

import base64
import io
import json

import numpy as np

KIND = "oni-colony-lost-v1"
CUES = {
    "zero": ((116, 20, 129, 39), "AAAAAAAAAOAPgEQCIBEAiARAIgGwD4AAAAAAAAAAAA=="),
    "banner": (
        (34, 122, 102, 139),
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADACAAAAAAAADAAgAAACAABAgAIAAAAgAAQQGyPGyIINEsEBEkJEiCCJBBAQpCRJAhCYQYEKQkRQIQhkCBEkJEYCCIJAebI8RCA80WcAAAAAAgAAAAAAAAAAQAAAAAAAAAAYAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
    ),
    "modal": (
        (590, 302, 691, 323),
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAfH4wH4xmMCA/j8fwBgM5gMxzMYEBjOAMADAYzAQjmYwIDGYAYAGAxmAhHMxgQGMwAwAMBjMBCPZjAgMZgBgAYDGYCEezGBAYz8DAAwGMwEI1mMCAxj8GABgMZgIRvH4EBjAYMADAYzAQjeHgIDGAwYAGAxmAhGcGAQGMBgwAMBjMBCM4MAgMYDBgAfj+fj8YwYB8fz+DAAfD4fDwxgwB4fH4GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    ),
    "message": (
        (526, 343, 754, 358),
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACEgcAAAkAAAAAAAAABAAAIAAAgAAAAAAQAAAAQGEgjAAAgAAAIAAAAABAAAIAAAAAAAAAACAEAAQGEgggAQkMIEIIBAhANCBBoDAgBgwhYIECCEECQJEggkRMkQETIgCTGwREgSIEjAmRAJkCYSAkJMwJEggkREkgCRIgASEQRIgSIISAkSAJCCQSAkRIQPkggkREkgeRIYDyHwRPjyIISAkSB5CeQSHkfIQQkggkREkgiRIEESEARIESIISAkSCJCiQSIkQIQQkghEREkhmRICESEARIESIISAkTCJEiQSIkQIwAUg+Dx4kc6RG8HyDwOHnxwHiAkR75c+OTvjPHGAAAAABAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    ),
}


def colony_lost(image):
    """Return whether a 1280x720 frame shows zero population and the defeat message."""
    if image.size != (1280, 720):
        return False
    matches = {}
    for key, (box, encoded) in CUES.items():
        values = np.asarray(image.crop(box).convert("L"), dtype=float).ravel()
        contrast = float(values.max() - values.min())
        actual = values > values.min() + contrast * 0.65
        expected = np.unpackbits(np.frombuffer(base64.b64decode(encoded), dtype=np.uint8))
        matches[key] = contrast >= 8 and np.mean(actual != expected[: len(actual)]) <= 0.02
    return bool(
        matches["zero"] and (matches["banner"] or (matches["modal"] and matches["message"]))
    )


def receipt(image):
    """Return a JSON receipt holding the frame when it shows Colony Lost."""
    if not colony_lost(image):
        return None
    output = io.BytesIO()
    image.save(output, format="PNG")
    data = {"kind": KIND, "window_png": base64.b64encode(output.getvalue()).decode("ascii")}
    return (json.dumps(data) + "\n").encode()
