"""Native pause-button recognition for the 1280x720 ONI window."""

import base64

import numpy as np

BOX = (100, 45, 122, 67)
TEMPLATES = {
    "paused": (
        "SUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUhLTExLR0hJSUhHR0dHSElJSUlJSUlIRURERBkoRUYqHiUmJSlCSUlJ"
        "SUlJJxxcXFxBCTo9AV1sb24sMUlJSUlJSSZLlJqadAk4OgGVlZmYRi9JSUlJSUkmUZObm3cJPToBlpaamEcvSUlJ"
        "SUlJJlGTm5t3CT06AZaWmphHLklJSUlJSSZQk5ubdwk9OgGVlpqYRy9JSUlJSUkmUJKbm3cJPToBlZWZmEcvSUlJ"
        "SUlJJlCSm5t3CT07AZWVmZhHLklJSUlJSSZQkpubdwk9PAGVlZmYRy1JSUlJSUkmUJKbm3cJPTsBlZWZmEctSUlJ"
        "SUlJJlCSm5t3CT07AZWVmZhHLklJSUlJSSdQkpubdQc4OwKUlJiWRi5JSUlJSUkoPI+bm3EHODsEfpOTkEMwSUlJ"
        "SUlJLUppdHRcBzg1BGVqamlDMUlJSUlJSS5OY21tVwc4MwRjY2NiQTBJSUlJSUkuPWFiYk0HODYBX2loZjAvSUlJ"
        "SUlJNRobHBwfNElFCBwnKSghPUlJSUlJSUY/TE1NTEtJSUBFTEtLSUhJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJ"
        "SUlJSUlJSUlJSUlJSUlJSUlJSUlJSQ=="
    ),
    "running": (
        "SUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUhISUlIRkhJSUhHR0dHSElJSUlJSUk/LCkpKRcoRUYqHCAgHylCSUlJ"
        "SUlJJw4oKCgcCDo9ASkvMDAWMUlJSUlJSSYiQUREMwg4OgFCQkNDIC9JSUlJSUkmJUBERDQJPToBQkJEQyEvSUlJ"
        "SUlJJiVAREQ0CT06AUJCREMhLklJSUlJSSYkQERENAk9OgFBQUNDIS9JSUlJSUkmJEBERDQJPToBQUFDQyEvSUlJ"
        "SUlJJiRAREQ0CT06AUFBQ0MhLklJSUlJSSYkQERENAk9OwFBQUNDIC1JSUlJSUkmJEBERDQJPTsBQUFDQyAtSUlJ"
        "SUlJJiRAREQ0CT06AUFBQ0MgLklJSUlJSSYkQERENAc4OgFBQUNCIC5JSUlJSUknGz9ERDEHODoDN0BAPx8wSUlJ"
        "SUlJLCIuMzMoBzg0AywuLi4gMUlJSUlJSS0kKy8vJgc4MwIsLCsrHjBJSUlJSUkuHSorKyIHODYBKS4uLRYvSUlJ"
        "SUlJNQ8MDAwRJkZFCAwTFhYWOklJSUlJSUY/REVFRUdJSUBBREVFREhJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJ"
        "SUlJSUlJSUlJSUlJSUlJSUlJSUlJSQ=="
    ),
}


def simulation_state(image):
    """Return paused or running when exactly one pause-button template matches."""
    actual = np.asarray(image.crop(BOX).convert("L"), dtype=float).ravel()
    matches = [
        name
        for name, encoded in TEMPLATES.items()
        if np.mean(np.abs(actual - np.frombuffer(base64.b64decode(encoded), dtype=np.uint8))) < 3
    ]
    return matches[0] if len(matches) == 1 else None
