# Hollow Knight: Silksong: `moss-start-v5`

A new game in slot 1 (normal mode): no input during the opening, one bind at the first prompt, then Save and Quit from the pause menu. The start is in Moss Grotto (`Tut_01`) before any kill, with 4 of 5 masks and no silk.

| | |
| --- | --- |
| Game | Hollow Knight: Silksong, native Linux (Steam build 22479045, save version 1.0.30000) |
| Prepared by | Anonymous 012 |
| `snapshot_hash` | `9e513d41b3a1611062cabdd47a137f9730aa282cfba4fcdf6252790363ca18b4` |
| `snapshot.tar.gz` | 41,160 bytes, sha256 `732fb08a2b81edf7a15a17945010792de73dda516e3c7b9af0dfb2e768d44ba7` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds `user1.dat`, `shared.dat`, `prefs`, `GOLDEN.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
