# Baba Is You: `fresh-default-settings`

`SettingsC.txt` is the settings file the game writes on its first launch in an empty profile, so the key bindings are the defaults. There is no save slot: every trial starts a new game, which opens on the first level.

| | |
| --- | --- |
| Game | Baba Is You, native build 24529734 |
| Prepared by | Anonymous 002 |
| `snapshot_hash` | `a2091dd078267d6b0995bd97e00171fea4c482384144fbbc2d0fc23032554395` |
| `snapshot.tar.gz` | 994 bytes, sha256 `a334a0af895dddd29f5db2883ae51865d424c5416b5ee4de15bedadd836c32d0` |
| Trials | 6 (6 live): all six agents |

## Contents

The archive holds `Baba_Is_You/SettingsC.txt`, `preparation.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
