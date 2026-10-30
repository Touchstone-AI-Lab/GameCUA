# Factorio: `deathworld-marathon-2.1.24-seed12345-v1`

A base-game freeplay map on Nauvis with one player, created by the game with seed `12345` and the `death-world-marathon` preset (technology price multiplier 4, enemy base frequency and size 2, peaceful mode off). The map was loaded in the game client and saved from the menu before any movement, mining, crafting, building or research.

| | |
| --- | --- |
| Game | Factorio 2.1.24, Linux (Steam app 427520, build 26246811) |
| Prepared by | Anonymous 005 |
| `snapshot_hash` | `b23c6cdb01d501a5813ae64afcd653a8e868ac905565c913638ea89459ae98c8` |
| `snapshot.tar.gz` | 1,791,111 bytes, sha256 `712cb781d1ccf566c748085fdd8649e2620ccd7e820f24dca519d75f36a37638` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds `start.zip` (the save), `preparation.json` and `snapshot.manifest.json`. The manifest also pins the files of the game installation it was prepared with, so a matching installation is required. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
