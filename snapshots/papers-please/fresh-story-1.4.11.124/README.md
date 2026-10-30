# Papers, Please: `fresh-story-1.4.11.124`

The initial settings of the game (English, normal difficulty). Every trial creates a fresh profile from these settings and starts Story mode. The game draws some ordinary entrants at random and has no seed setting, so the entrant sequence can differ between trials.

| | |
| --- | --- |
| Game | Papers, Please 1.4.11.124 (Steam app 239030, build 10817815) |
| Prepared by | Anonymous 008 |
| `snapshot_hash` | `26904a3ecc6799eb6298357ab70643dee65fe86ab61e37895ee48e102856ab5a` |
| `snapshot.tar.gz` | 324,373 bytes, sha256 `839b3bf335f2de4551af8b64c98acdbbee216de091474b3cd4a0a8ba3bf9e61b` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds `settings.sav`, three reference screenshots of the title menu, the new-game menu and the first office day, `preparation.json` and `snapshot.manifest.json`. It holds no game files, Steam login state or credentials.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `snapshot.manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
