"""Read-only decoding of Silksong PC saves; decoded state stays evaluator-private."""

import base64
import json

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = b"UKu52ePUBwetZ9wNX88o54dnfKRu0T1l"
HEADER = bytes((0, 1, 0, 0, 0, 255, 255, 255, 255, 1, 0, 0, 0, 0, 0, 0, 0, 6, 1, 0, 0, 0))


def unwrap(raw):
    """Return the base64 payload inside the BinaryFormatter string wrapper."""
    if not raw.startswith(HEADER):
        raise ValueError("save lacks the BinaryFormatter string wrapper")
    body = raw[len(HEADER) : -1]
    length = index = 0
    while True:
        length |= (body[index] & 0x7F) << (7 * index)
        if not body[index] & 0x80:
            return body[index + 1 : index + 1 + length]
        index += 1


def decode_save(raw):
    """Decrypt a save into its JSON document; a partially written save raises ValueError."""
    data = base64.b64decode(unwrap(raw), validate=True)
    decryptor = Cipher(algorithms.AES(KEY), modes.ECB()).decryptor()
    plain = decryptor.update(data) + decryptor.finalize()
    return json.loads(plain[: -plain[-1]].decode("utf-8"))
