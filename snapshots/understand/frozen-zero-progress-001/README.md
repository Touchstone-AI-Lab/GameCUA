# Understand: `frozen-zero-progress-001`

A native save with zero progress in all three slots, in full screen. The four Understand starting states have the same save (sha256 `163e97e1634346e927d99ecb36effc3c48aaa20e3f831f34b66b5d13e465d670`); they differ only in `preparation.json`, which records the Proton build each was prepared with, and so have different `snapshot_hash` values.

| | |
| --- | --- |
| Game | Understand 1.2.3, Windows build 7803420 (Steam app 1299400), run through Proton Experimental build 25936768 and Steam Linux Runtime 4.0 build 25607596 |
| Prepared by | Anonymous 003 |
| `snapshot_hash` | `4de18957d54a55c765cef5f53d8bddebc8a81a1fa5c602e77a9022a81909fab3` |
| `snapshot.tar.gz` | 1,751 bytes, sha256 `19c88413b7b5381d2fd8db0cddf07f385a99e8dc541eefe11241a8be9e998510` |
| Trials | 2 (2 live): DeepSeek-Flash, Jev 1.14.0 |

## Contents

The archive holds `understand.sav`, `preparation.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
