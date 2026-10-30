# Don't Starve: `prepared-longday-v4`

A base-game survival world created through the in-game menus: Wilson, DLC disabled, the Long Day option and default resources. After the opening cutscene the world was saved through the menu with no movement, gathering or crafting. The save is on day 1, during the day, seed 1792983405, with 150 health and an empty inventory.

| | |
| --- | --- |
| Game | Don't Starve, Linux (Steam app 219740, build 12527201) |
| Prepared by | Anonymous 011 |
| `snapshot_hash` | `459353d6d4af14f903a23ae529aab5249ddf027f44ae0f5e325a03f208a2afc9` |
| `snapshot.tar.gz` | 4,887,941 bytes, sha256 `a83462d2ee54273402d43c09ac40dc187896eac05f5e6df9bd0734db15e7ffe5` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds the slot save and its save indexes, the game settings, `preparation.json`, `snapshot.manifest.json`, and the menu plan with its five reference screenshots used to load the save through the menus; 14 files in all. It holds no game files, Steam login state or credentials.

`gamecua.games.dont_starve.setup.validate_snapshot(<directory>)` checks every file and returns `snapshot_hash` as its first value.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
