# art of rally: `v8-five-stage-720p-start-split-v1`

The start is before the first of five custom-rally stages, with no stage results, in a clean Group 2 the esky v1 (`Car_Escort_V1`, livery 1). The stages, in order, are Noormarkku (reverse, rain), Palus (morning, dry), Kairila (morning, dry), Lassila (afternoon, dry) and Lamppi (morning, dry). The game runs at 1280x720 with normal AI, automatic transmission and the assist settings stored in `prefs`; damage is disabled.

| | |
| --- | --- |
| Game | art of rally, native Linux build (Steam app 550320) |
| Prepared by | Anonymous 014 |
| `snapshot_hash` | `38e1b95fe5ca6906a14b69205ea0062a8c3a7cf1c340ff472dbd0dd7f239fd6d` |
| `snapshot.tar.gz` | 5,880 bytes, sha256 `2d51f9262b083aedd30e82f7164887a01d3cdac1b19cbf52a2e29c161ccadd2c` |
| Trials | 12 (6 live, 6 frozen): all six agents |

## Contents

The archive holds `customrally`, `SaveGame.json`, `career`, `prefs`, `preparation.json` and `manifest.json`. It holds no game files, Steam login state or credentials.

## Runtime companion

The manifest also lists 22 runtime files that are not part of the save: the BepInEx mod loader, the GameCUA observer plugin `RallyNativeObserver.dll`, and two reference images of the title screen and the main menu. They are in `runtime/`:

| File | Contents |
| --- | --- |
| `runtime.tar.gz` | The 22 runtime files; 2,082,824 bytes, sha256 `2c0eca956dac104007474051f4d9eda7b4cfb3960aa829eb765908c793fa0f1e` |
| `runtime.manifest.json` | The sha256 of each of the 22 files |
| `RallyNativeObserver-source.tar.gz` | The C# source of the observer plugin |
| `UnityDoorstop-4.5.0-source.tar.gz` | The source of the Doorstop loader |
| `THIRD-PARTY-NOTICES.txt` | The licences of BepInEx, HarmonyX, MonoMod, Mono.Cecil and Doorstop |

Unpack `runtime.tar.gz` into a sibling of the snapshot directory named `<snapshot directory>.runtime`, or point `ART_OF_RALLY_SNAPSHOT_RUNTIME` at the unpacked directory.

## Use

Unpack `snapshot.tar.gz` into an empty directory and pass that directory as `--snapshot` to `python -m gamecua.cli trial`, together with a licensed installation of the game. `manifest.json` lists every file of the starting state with its sha256, and `snapshot_hash` is the digest of that manifest.
