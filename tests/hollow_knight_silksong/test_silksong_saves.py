"""Save decoding uses synthetic encrypted saves, never real player data or benchmark results."""

import base64
import json

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from gamecua.games.hollow_knight_silksong.saves import HEADER, KEY, decode_save

DOCUMENT = {
    "playerData": {
        "completedTutorial": True,
        "defeatedMossMother": False,
        "hasDash": True,
        "health": 5,
        "permadeathMode": 0,
        "playTime": 812.5,
    },
    "sceneData": {},
}


def encrypt(text, key=KEY):
    padding = 16 - len(text) % 16
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(text + bytes((padding,)) * padding) + encryptor.finalize()


def prefix(length):
    out = bytearray()
    while True:
        byte = length & 0x7F
        length >>= 7
        out.append(byte | (0x80 if length else 0))
        if not length:
            return bytes(out)


def wrap(payload):
    return HEADER + prefix(len(payload)) + payload + bytes((11,))


def encode(document, key=KEY):
    return wrap(base64.b64encode(encrypt(json.dumps(document).encode(), key)))


def test_round_trip_returns_the_document():
    assert decode_save(encode(DOCUMENT)) == DOCUMENT


@pytest.mark.parametrize("size", [0, 100, 20000])
def test_multi_byte_length_prefixes(size):
    document = {"playerData": {"padding": "x" * size}}
    assert decode_save(encode(document)) == document


def test_partially_written_saves_raise_value_errors():
    raw = encode(DOCUMENT)
    for broken in (bytes((1,)) + raw[1:], raw[: len(raw) // 2], wrap(base64.b64encode(b"short"))):
        with pytest.raises(ValueError):
            decode_save(broken)
