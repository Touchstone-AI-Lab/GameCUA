# GameCUA V1 Starting States

This directory holds the starting state of each of the 156 trials of GameCUA V1, so that any trial can be run again from the same start. The trial records are on the `v1-official-exp` branch.

## Layout

```
snapshots/<game>/<snapshot>/   snapshot.tar.gz, snapshot.manifest.json and README.md
snapshots/art-of-rally/<snapshot>/runtime/
                               the runtime companion of art of rally: mod loader, observer plugin and menu references
snapshots/<game>/new.txt       the game starts from a new game rather than a prepared save
snapshots/snapshots.json       one entry per trial: its starting state and how it was matched
```

`snapshot.tar.gz` is the snapshot directory, packed deterministically (`tar --sort=name --owner=0 --group=0 --numeric-owner --mtime=@0 | gzip -n -9`). `snapshot.manifest.json` is a copy of the manifest inside the archive, and `README.md` describes the starting state and gives its `snapshot_hash`.

## Games

| Game | Starting state |
| --- | --- |
| art of rally | `v8-five-stage-720p-start-split-v1` |
| Baba Is You | `fresh-default-settings` |
| Civilization VI | `standard-aztec-prince-20261112-v1` |
| Don't Starve | `prepared-longday-v4` |
| Factorio | `deathworld-marathon-2.1.24-seed12345-v1` |
| Hollow Knight: Silksong | `moss-start-v5` |
| Left 4 Dead 2 | new game |
| Oxygen Not Included | `base-terra-20261030-v1` |
| Papers, Please | `fresh-story-1.4.11.124` |
| PEAK | new game |
| Slay the Spire | `sts-a10-snapshot` |
| Stardew Valley | `snapshot-spring2` |
| The Binding of Isaac: Rebirth | `snapshot-rep-mvsn` |
| Understand | `frozen-zero-progress-001` (DeepSeek-Flash, Jev 1.14.0), `zero-progress-1c84b437a573` (Opus 5.5, Grok 4.7), `zero-progress-31a3acc95951` (GPT-6-Astra), `zero-progress-c88a32950333` (Kimi K3.1 Pro); all four share the same native start save |
| Untitled Goose Game | new game |

## Matching trials to starting states

| `match` | Trials | Meaning |
| --- | ---: | --- |
| `snapshot_hash` | 120 | The `snapshot_hash` recorded by the trial equals the one given in the starting state's README. |
| `new_game` | 36 | PEAK, Left 4 Dead 2 and Untitled Goose Game start from a new game. |

Each entry also gives `initial_save_sha256`, the sha256 of the native start save kept in the trial's evidence.
