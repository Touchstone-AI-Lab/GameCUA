# Oxygen Not Included: `base-terra-20261030-v1`

A base-game Survival colony on the Terra asteroid, seed `1880042481`, with DLC, mods, sandbox and debug mode off. The three starting duplicants (Gossmann, Bubbles and Ashkan) are the first ones generated, without rerolls. The game was saved 53 seconds into cycle 0, before any building or digging.

| | |
| --- | --- |
| Game | Oxygen Not Included, Linux (Steam app 457140, build 24423041; game build 744825, save format 7.38) |
| Prepared by | Anonymous 006 |
| `snapshot_hash` | `afab5a9efc334f643c3bf63c1840c14b0d8c6d6e6b88a634bd748fcfe7ba5cfa` |
| `snapshot.tar.gz` | 700,531 bytes, sha256 `a44d9435cb332ec1646ef3e7b6962640e5d9607db940c4d467bfccf79385ad2f` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds `initial.sav` (sha256 `69f9797471f6cfa1086e825b820dd9d4a729af0cbb43b207dc730f56b1336f35`), `preparation.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
