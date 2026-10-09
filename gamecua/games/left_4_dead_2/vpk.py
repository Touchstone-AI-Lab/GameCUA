"""Read selected unmodified resources from the licensed Valve VPK archive."""

import struct
from pathlib import Path


def resource(pack, wanted):
    """Return the bytes of one file stored in a VPK directory archive."""
    pack = Path(pack)
    data = pack.read_bytes()
    _, version, tree_size = struct.unpack_from("<III", data)
    start = 28 if version == 2 else 12
    position = start

    def string():
        nonlocal position
        end = data.index(b"\0", position)
        value = data[position:end].decode()
        position = end + 1
        return value

    while extension := string():
        while folder := string():
            while name := string():
                _, preload, archive, offset, length, _ = struct.unpack_from(
                    "<IHHIIH", data, position
                )
                position += 18
                prefix = data[position : position + preload]
                position += preload
                path = (folder + "/" if folder != " " else "") + name + "." + extension
                if path == wanted:
                    source = (
                        pack
                        if archive == 0x7FFF
                        else pack.with_name(pack.name.replace("_dir.vpk", f"_{archive:03d}.vpk"))
                    )
                    with source.open("rb") as file:
                        file.seek(start + tree_size + offset if archive == 0x7FFF else offset)
                        return prefix + file.read(length)
    raise ValueError("Missing licensed native resource: " + wanted)
