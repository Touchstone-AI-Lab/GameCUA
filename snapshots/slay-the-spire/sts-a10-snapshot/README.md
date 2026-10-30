# Slay the Spire: `sts-a10-snapshot`

An Ironclad run on Ascension 10 with seed `-4236424554807579186`, on floor 1 after the opening Cultist fight. The save carries the run-start effects of Ascension 10: 72 of 80 HP and Ascender's Bane in the deck. `GOLDEN.json` in the archive describes the state.

| | |
| --- | --- |
| Game | Slay the Spire (Steam) |
| Prepared by | Anonymous 001 |
| `snapshot_hash` | `c926b5d0af0e3b9d1c4f4fa64c1aa6e83d438647f0bc68caf202fb027c68e228` |
| `snapshot.tar.gz` | 8,947 bytes, sha256 `b233d22edee5b97cd332f385e043d6825d2d253b7b5656f27d55f388da647537` |
| Trials | 6 (6 live): all six agents |

## Contents

The archive holds the run save, the game preferences, `GOLDEN.json` and `snapshot.manifest.json`; 33 files in all. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
