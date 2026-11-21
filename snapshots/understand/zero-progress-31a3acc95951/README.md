# Understand: `zero-progress-31a3acc95951`

A native save with zero progress in all three slots, in full screen. The four Understand starting states have the same save (sha256 `163e97e1634346e927d99ecb36effc3c48aaa20e3f831f34b66b5d13e465d670`); they differ only in `preparation.json`, which records the Proton build each was prepared with, and so have different `snapshot_hash` values.

| | |
| --- | --- |
| Game | Understand 1.2.3, Windows build 7803420 (Steam app 1299400), run through Proton build 26306234 and Steam Linux Runtime 4.0 build 25607596 |
| Prepared by | Anonymous 003 |
| `snapshot_hash` | `31a3acc95951dd8fc090568f1d1e21ad2ebf12db954d8d15dec8602198fd380d` |
| `snapshot.tar.gz` | 1,645 bytes, sha256 `5250175298839e2482b540f9dd9ae7a07b64d496e1e7d69f767e4587edb76926` |
| Trials | 1 (1 live): GPT-6-Astra |

## Contents

The archive holds `understand.sav`, `preparation.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
