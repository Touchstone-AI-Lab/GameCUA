# Civilization VI: `standard-aztec-prince-20261112-v1`

A standard-rules game prepared through the in-game menus: Aztec (Montezuma) on Prince difficulty against one AI civilization, Ancient Era start, Standard speed, Small Continents, science victory only. The game is saved on turn 1. Before the clock starts, the harness ends turn 1 once and checks that turn 2 has begun.

| | |
| --- | --- |
| Game | Civilization VI (Steam), base game with the free Aztec Civilization Pack; expansion rules inactive |
| Prepared by | Anonymous 004 |
| `snapshot_hash` | `d9796a091e9b8466f1df0a2f86e7791d310f9129e868c5e1487aac953d19ca98` |
| `snapshot.tar.gz` | 10,251,251 bytes, sha256 `41582ca28cd18a7c41ce630386efb46d300dbc958d874f08bbb087266b916b6a` |
| Trials | 6 (6 live): all six agents |

## Contents

The archive holds the game profile (options, input settings and mod database), the start save and its autosave, the menu-loading references, `preparation.json` and `snapshot.manifest.json`; 20 files in all. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
