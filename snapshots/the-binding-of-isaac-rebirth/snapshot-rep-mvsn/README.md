# The Binding of Isaac: Rebirth: `snapshot-rep-mvsn`

A zero-progress game data directory: there is no save slot, so nothing is unlocked. `options.ini` turns off Steam Cloud, mods, the debug console, pause on focus loss, music and sound, and sets a 1280x720 window. Every trial starts a seeded run, `MVSN TFS1`, as Isaac on Normal (`GOLDEN.json`), so floor 1 is the same in every trial.

| | |
| --- | --- |
| Game | The Binding of Isaac: Repentance v1.7.9b.J835, Windows build run through Proton (Steam build 22878971) |
| Prepared by | Anonymous 013 |
| `snapshot_hash` | `5073d5cc6c0dffddd92f2eaae1cdf39ca547781bdf367ffe7c75643d19b72953` |
| `snapshot.tar.gz` | 925 bytes, sha256 `1ccdc697165acc453f5a753a80fb6b9f8a8f9199966503f8a0d130daafad703b` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds `data/Binding of Isaac Repentance/options.ini`, `GOLDEN.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
