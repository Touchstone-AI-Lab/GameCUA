"""Native Slay the Spire autosave codec."""

import base64
import json

XOR_KEY = b"key"


def xor(data):
    """Apply the game's repeating XOR key."""
    return bytes(b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(data))


def decode_autosave(raw: bytes) -> dict:
    """Decode a base64 XOR autosave into its JSON run state."""
    return json.loads(xor(base64.b64decode(raw)))


def encode_autosave(state: dict) -> bytes:
    """Encode a JSON run state as a native autosave."""
    return base64.b64encode(xor(json.dumps(state).encode()))
