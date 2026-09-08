"""Atomic JSON writes, bundle-relative evidence paths and file digests."""

import hashlib
import json
import os
from pathlib import Path


def write_json(path, value):
    """Write JSON through a synced temporary file so readers never see a partial file."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as file:
        file.write(json.dumps(value, indent=2, ensure_ascii=False))
        file.flush()
        os.fsync(file.fileno())
    tmp.replace(path)


def local_file(root, relative):
    """Resolve an evidence path recorded relative to its bundle."""
    return Path(root) / relative


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
