"""Read-only decoding of the native PPSAVE1 big-endian XXTEA XML format."""

import hashlib
import struct
import xml.etree.ElementTree as ET


def decrypt(raw, key):
    """Decrypt one big-endian XXTEA block of native save bytes."""
    values = list(struct.unpack(">" + "I" * (len(raw) // 4), raw))
    words = struct.unpack(">4I", key)
    count = len(values)
    total = ((6 + 52 // count) * 0x9E3779B9) & 0xFFFFFFFF
    y = values[0]

    def mix(z, y, position, selector):
        return (
            ((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4))
            ^ ((total ^ y) + (words[(position & 3) ^ selector] ^ z))
        ) & 0xFFFFFFFF

    while total:
        selector = (total >> 2) & 3
        for position in range(count - 1, 0, -1):
            z = values[position - 1]
            values[position] = (values[position] - mix(z, y, position, selector)) & 0xFFFFFFFF
            y = values[position]
        values[0] = (values[0] - mix(values[-1], y, 0, selector)) & 0xFFFFFFFF
        y = values[0]
        total = (total - 0x9E3779B9) & 0xFFFFFFFF
    return struct.pack(">" + "I" * count, *values).rstrip(b"\0")


def plaintext(raw, key):
    """Return the payload after the PPSAVE1 header of a hex-encoded native file."""
    decoded = decrypt(bytes.fromhex(raw.decode("ascii")), key)
    if not decoded.startswith(b"PPSAVE1"):
        raise ValueError("Unsupported native save header")
    return decoded[7:]


def read_save(raw, key):
    """Parse a native XML save."""
    return ET.fromstring(plaintext(raw, key))


def members(raw, key):
    """Return the key and value entries of a native members dictionary."""
    return {item.attrib["key"]: item.attrib["val"] for item in read_save(raw, key)}


def discover_key(metadata, settings):
    """Find the native file-format key among the licensed client's metadata strings."""
    offset, length, data_offset, data_length = struct.unpack_from("<4I", metadata, 8)
    for size, index in struct.iter_unpack("<II", metadata[offset : offset + length]):
        if not 1 <= size <= 80 or index + size > data_length:
            continue
        candidate = hashlib.md5(metadata[data_offset + index : data_offset + index + size]).digest()
        try:
            settings_data = members(settings, candidate)
        except (ValueError, KeyError, ET.ParseError):
            continue
        if {"easyMode", "languageCode", "fullscreen"} <= settings_data.keys():
            return candidate
    raise ValueError("No supported native save decoder found")
