# Stardew Valley: `snapshot-spring2`

A new farm on the morning of Spring 2, Year 1. The game was started with Skip Intro and slept through the first night, which gives the earliest native save.

| | |
| --- | --- |
| Game | Stardew Valley, Linux |
| Prepared by | Anonymous 007 |
| `snapshot_hash` | `a94615a1808e66857d52bfa57f52012fb45e7bbe023b8e69ec413905f3633821` |
| `snapshot.tar.gz` | 94,883 bytes, sha256 `3fdec20a24662b41f8a6615233c540bc1bb240dda9d72d4ab54fb9de2777854f` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds `Saves/Research_450935580/Research_450935580` (sha256 `f5243f22976d72454bff71e27bad89508190f2b9378319059003014b83824288`), `Saves/Research_450935580/SaveGameInfo`, `startup_preferences`, `preparation.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
