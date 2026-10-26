# Hollow Knight: Silksong

Experimental real-time integration (game id `hollow-knight-silksong`, Steam app 1030300): the official native Linux build (Steam build 22479045, save version 1.0.30000) through the official Steam client, 1280x720, `xtest` input backend. Timing is `realtime` with pause method `process`, so Trials run both live and `frozen_steps` (0.4 s per action). A native death ends the episode: language-model Trials have one life (`episode_limit: 1`), and Jev ends at its first death. See [VALIDATION.md](VALIDATION.md).

## Renderer and host

The integration runs only on WSL2 hosts with `env-create --renderer wsl-d3d12 --gpu <adapter>` and a named adapter, for example `--gpu NVIDIA`. The game process sets `GALLIUM_DRIVER=d3d12` and starts with `-force-glcore45 -force-clamped`, without which Mesa D3D12 renders corrupted frames. Preparation verifies the D3D12 renderer for the named adapter, an OpenGL 4.5 context without extensions, a loaded `libd3d12` and an open `/dev/dxg`. Frozen steps pause the game for longer than the default 2-second Windows GPU timeout, so on the Windows host set `TdrDelay` under `HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers` above the longest expected pause (60 seconds was used) and restart; otherwise the driver resets and the game window freezes. A Trial ends as an infrastructure failure and writes `render-stall.json` when the frame stays identical for 300 seconds while the game runs.

## Setup and snapshot

Use a licensed installation signed in through the official client, and disable this game's Steam Cloud sync with the account owner's authorization before isolated Trials. `snapshot-silksong --source <profile> --output <snapshot>` copies an operator-prepared slot-1 save, `shared.dat` and preferences read-only, refuses Steel Soul and boss-rush saves, and records the installation identity and the save's initial state in `GOLDEN.json`. Each episode copies the snapshot into an isolated XDG profile, loads it through a fixed title-screen sequence and verifies the native silk-spool HUD before the clock starts. The prepared state is the start of Moss Grotto before any kill: snapshot `moss-start-v5` is a new normal-mode game in slot 1, saved with Save and Quit right after the opening's first bind; its scripted derivation is recorded in VALIDATION.md. Saves, snapshots and installations stay in private local storage.

The game has no difficulty setting; its only other mode, Steel Soul (permadeath), unlocks after an ending, so normal mode is the hardest available at the start.

## Death and evidence

The game writes its save on every native death, and a death save records `health` 0. The integration reports such a save as the death outcome, so the episode ends there, although the game itself would respawn Hornet at her last bench or at the Moss Grotto starting point (`respawnScene` `Tut_01`). A language-model Trial with `episode_limit: 1` therefore ends at its first death, a verified ending or its deadline, and Jev ends at its first death. Before release `silksong-native-save-6` the integration kept deaths inside the episode; those Trials remain as recorded.

Milestones come only from the native save. The game writes it on every death, at benches, on Save and Quit, after the ending sequence, and when some story events queue a save; starting act two queues one. Defeating Moss Mother, the Bell Beast or the Widow does not write it. Progress after the last write before the deadline is not credited, so a run that neither dies nor rests after a milestone keeps no evidence of it.

## Rubric

Current rubric `hollow-knight-silksong-points-v1` ([points-v1.json](../../../benchmarks/rubrics/hollow-knight-silksong/points-v1.json)), uncalibrated: 52 independent points worth 100, without prerequisites, all read from the native save. Four first steps are worth 1 point and the other 48 are worth 2.

| Group | Points | Native-evidence requirement |
| --- | --- | --- |
| Progress (26) | New scenes 1 (1 point), 2 to 8, 10, 12, 14 and 16 | count of `scenesVisited` entries the prepared save lacks |
| | Moss Grotto, Bone Bottom, the Marrow, Mosshome, the Deep Docks | `visitedMossCave`, `visitedBoneBottom`, `visitedBoneForest`, `visitedMosstown`, `visitedDeepDocks` |
| | Moss Mother met and defeated, the great bone gate, the bell bench, the Bell Beast met and defeated | `encounteredMossMother`, `defeatedMossMother`, `greatBoneGateOpened`, `hasActivatedBellBench`, `encounteredBellBeast`, `defeatedBellBeast` |
| | Silkspear and Swift Step | the `Silk Spear` tool unlocked or `hasNeedleThrow`; `hasDash` |
| | Rest at a bench | `respawnType` 1 (bench respawn) |
| Collection and choice (26) | Enemy kinds 1 (1 point), 2 to 6, 8, 10 and 12; kills 5, 10, 25, 50 and 100 | Hunter's journal `EnemyJournalKillData` |
| | Shell shards held 10 (1 point), 25, 50, 100 and 200 | `ShellShards` |
| | Rosaries held 1 (1 point) and 20, counting those left in the cocoon | `geo` plus `HeroCorpseMoneyPool` |
| | A collectable item, an unlocked tool, an accepted wish, one and three characters met | `Collectables`, `Tools` (`IsUnlocked`), `QuestCompletionData` (`IsAccepted`), `met*` and `Met*` flags |

Every point stops at what an ordinary player reaches in about two hours, from the opening room to the Bell Beast, the Deep Docks and Swift Step, and rewards something the game itself encourages: exploring, fighting, collecting currency and items, gaining skills, resting and meeting its characters. The prepared save holds none of them; preparation verifies that, and the scorer awards a point from the first preserved save that records it. The two Bell Beast points need Silkspear (Mosshome) first: the beast hangs in silk that only Silkspear cuts, and on the recommended route the Deep Docks follow it.

Routes. Moss Grotto is linear, so reaching it, meeting and defeating Moss Mother, and resting at a bench (8 points) lie on every route. The ten named points from Bone Bottom to Swift Step (20 points) follow the route that guides recommend; a run that leaves Bone Bottom another way, for example through the Wormways, cannot earn them there. The other 72 points are counts that any route earns: scenes, the Hunter's journal, shell shards, rosaries, items, tools, wishes and characters. The ratio, the caps and their reasons are in VALIDATION.md.

`progress-v3` (10 × 10, each on every route to an ending), `progress-v2` (5 × 20) and `progress-v1` remain for published results:

| Milestone | Native-evidence requirement | After |
| --- | --- | --- |
| Leave the opening room | a scene the prepared save lacks | — |
| Moss Mother | `defeatedMossMother` | opening room |
| Cling Grip | `hasWalljump` | Moss Mother |
| Widow (Needolin) | `spinnerDefeated` | Moss Mother |
| Act two | `act2Started` | Widow |
| Cogwork Dancers (Melody Lift) | `UnlockedMelodyLift` | act two |
| Clawline | `hasHarpoonDash` | act two |
| Threefold Melody | `HasMelodyArchitect`, `HasMelodyLibrarian` and `HasMelodyConductor` all set | act two |
| Lace 2 | `defeatedLaceTower` | act two |
| Ending | `CompletedEndings` records any ending; this is the run's verified completion | act two |

A milestone is used only when a minimal winning route cannot avoid it: Cling Grip, Needolin, Clawline and Lace 2's Silk Heart are on the speedrun.com Low% list of the five items a glitch-free run to Grand Mother Silk must collect, and the Cogwork Dancers, the three melodies and Lace 2 are fought or learned on every route through act two. Items a minimal route skips (Swift Step, Drifter's Cloak, mask, silk and needle upgrades) and points not proven on both act one routes (the Bell Beast, single areas) earn nothing. Sources and asset traces are in VALIDATION.md.

## Input profile and Trial specs

Input profile `hollow-knight-silksong-keys-v1` has four groups: a direction group that always holds one arrow key or arrow pair, and jump (`z`), attack (`x`) and skill (`c` or `a`) groups. Every combination therefore holds at least one key for the 0.4-second step, so no answer is a pure wait. At the start Hornet has no dash, so the dash button does nothing until it is gained, and bind needs a full silk spool. The language model receives the same buttons as its controls reference.

| Spec | Model | Mode | Budget |
| --- | --- | --- | --- |
| `points-v1-live-3h.json` | `deepseek-v41-flash-thinking` | live | one life, 10,800 s |
| `points-v1-frozen-3h.json` | `deepseek-v41-flash-thinking` | frozen steps, 0.4 s | one life, 10,800 s |
| `points-v1-opus-live-3h.json` | `claude-opus-5-5` | live | one life, 10,800 s |
| `points-v1-opus-frozen-3h.json` | `claude-opus-5-5` | frozen steps, 0.4 s | one life, 10,800 s |
| `points-v1-astra-live-3h.json` | `gpt-6-astra` | live | one life, 10,800 s |
| `points-v1-astra-frozen-3h.json` | `gpt-6-astra` | frozen steps, 0.4 s | one life, 10,800 s |
| `points-v1-grok-frozen-3h.json` | `hollow-knight-silksong-grok-4-7-high` | frozen steps, 0.4 s | one life, 10,800 s |
| `jev-points-v1-live-1h.json` | `jev-1-14` | live | 3,600 s |
| `jev-points-v1-frozen-1h.json` | `jev-1-14` | frozen steps, 0.4 s | 3,600 s |

The language-model specs use `provider_failure_policy: freeze_retry_timeout_credit`. The models read `CLAUDE_API_KEY`, `GPT_API_KEY` and `GROK_API_KEY` from private local configuration. The game-specific Grok model requests `grok-4.7` with high reasoning effort; the shared Grok model is unchanged. The `progress-v3` and `progress-v2` specs remain for published results.

All are under `benchmarks/trials/hollow-knight-silksong/`. Each Trial needs a fresh evaluation environment that reuses the prepared official client; `env-trial` defaults to 90 seconds, so pass the Trial's budget:

```bash
.venv/bin/python -m gamecua.cli env-create --output runs/silksong/eval-001 --steam-environment runs/silksong/preparation --renderer wsl-d3d12 --gpu NVIDIA --snapshot runs/silksong/snapshots/moss-start-v5
.venv/bin/python -m gamecua.cli env-trial --environment runs/silksong/eval-001 --trial-spec benchmarks/trials/hollow-knight-silksong/points-v1-live-3h.json --seconds 10800
.venv/bin/python -m gamecua.cli score-trial --run-dir runs/silksong/eval-001/work/trial
```

## Known limitations

- Unsaved progress before the deadline is not scored. A run that neither dies nor rests keeps only the progress of its last save.
- The frozen-step end frame shows jumps but not attacks; attacks are visible only through their effects. The benchmark specs observe only the end frame; the opt-in frame strip (#92) exists only on the separate branch `main-hks` as a controlled experiment, whose results are never pooled with these.
- Recovery resumes a Trial only when the process identity, the save hash and the profile match the checkpoint and the screen differs from the checkpoint frame by a mean of at most 5; nothing is rolled back or replayed. In live execution the game keeps running while the executor is interrupted.
- The rubric is uncalibrated and still awaits the core maintainer's review. Earlier DeepSeek Flash Trials on `progress-v1` scored 0 and are not comparable.
- The budget form stays `time` (`game.json`). A language-model spec without `episode_limit` would restart after a death from the prepared snapshot with summarized memory; the `points-v1` specs set one life.

The 0.7.10 image predates the game-specific Grok configuration. Pass this checkout's `benchmarks` directory through the shared environment manager's `trial(..., catalog=...)` argument so the catalog is copied and frozen inside the new evaluation environment. This uses the shared execution workflow without rebuilding or modifying the image.
