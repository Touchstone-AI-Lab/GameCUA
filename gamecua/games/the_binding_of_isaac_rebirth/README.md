# The Binding of Isaac: Rebirth

The Isaac integration (Steam App ID 250900, `game.json` id `the-binding-of-isaac-rebirth`) runs the Windows Repentance build (v1.7.9b.J835, `isaac-ng.exe` SHA256 pinned) through Proton Experimental inside Steam Linux Runtime 4 and the official client; the researcher's account must own Repentance. Roster status is `experimental`. Timing is `realtime` with a `process` pause method: the integration pauses the game processes with SIGSTOP while the model decides and resumes them for exactly one step of game time in `frozen_steps` Trials. Input uses XTest (Wine ignores synthetic XSendEvent input) with a visible cursor at 1280x720. Contributor: Changyi Yang.

## Setup and snapshot

- Create the zero-progression fixed-seed snapshot with `snapshot-isaac` (`.venv/bin/python -m gamecua.cli snapshot-isaac --help`).
- Each episode resets the game's data directory inside a container-local Wine prefix (a prefix on network storage fails), disables Steam Cloud and mods in `options.ini`, dismisses the read-only-mods error shown by the non-writable installation before the clock starts, and starts the fixed seed MVSN TFS1 as Isaac on Normal. Seeded runs keep persistent progress read-only.
- Milestones come only from the game's native `log.txt`. `Game Over` or a run restart ends the episode.

## Difficulty

Runs stay on Normal rather than Hard. Models already perform poorly on Normal: no earlier Trial (non-thinking DeepSeek and Claude pilots, 1 to 3 hours, live and frozen) defeated the first boss or reached the second floor, so Hard would only compress every cohort toward zero. The release 0.7.0 DeepSeek Trials check this against the calibration ceiling of about 40.

## Input profile

`benchmarks/inputs/the-binding-of-isaac-rebirth/keys-v1.json` (`isaac-keys-v1`, 0.5 s steps) has three groups that act together each step: `move` (W, A, S, D and the four diagonals), `shoot` (the four arrow keys) and `use` (none, E bomb, Space active item, Q pill or card). Movement and firing have no idle button, so a typed-choice model always acts; `use` keeps a "none" choice because consumables are finite. The language model receives the same descriptions as its controls reference and keeps free keyboard actions.

## Budget (release 0.7.6)

`game.json` declares `"budget": "attempts"`, because a native death ends the run. The language model gets two attempts within 6 h (`episode_limit: 2`, 21,600 s), keeping a summarized memory of the first attempt. Jev gets one attempt within 2 h (7,200 s) and ends at its first death. The delivery specs are `deepseek-v41-thinking-live-2att-6h`, `deepseek-v41-thinking-frozen-2att-6h`, `jev-live-2h` and `jev-frozen-2h`. The earlier 3 h and 1 h specs stay because published runs used them.

## Budget

Language models now get one life within 3 h, live only (`episode_limit: 1`, 10,800 s); the frozen cohort is not run for new models. The specs are `gpt-6-astra-live-1life-3h` and `claude-opus-5-5-live-1life-3h`, both with `reasoning_effort: high`. Jev keeps its rule above.

## Rubric

Current rubric: `benchmarks/rubrics/the-binding-of-isaac-rebirth/floor1-v5.json` (`the-binding-of-isaac-rebirth-floor1-v5`, 15 milestones, 100 points). Models die within the first rooms, so `floor1-v4` left nearly every first life at 0 or 10; `floor1-v5` adds smaller early steps that still require real progress:

| Milestones | Points | Native evidence |
|---|---|---|
| Leave the start room | 5 | a logged room other than the start room |
| Clear the first and second floor-1 rooms that hold enemies | 2 × 5 | the room is logged, then a different room; a normal room's doors stay closed until its enemies die |
| Floor-1 distance to the boss room, steps 1 to 4 | 4 × 5 | the exported floor-1 map |
| Collectibles 1 to 3 | 3 × 5 | `Adding collectible` |
| Reach floors 2 to 6 | 5 × 10 | `Level::Init m_Stage` |

The floor-1 map marks which normal rooms hold enemies, observed in the preserved screenshots of the delivery runs on this seed: 660 and 916 (both on the only route to the boss room) hold enemies, 941 and 85 hold none, so walking through an empty room earns no clear. Survival time is not scored: the start room holds no enemies, so a model that never moves would earn time without any progress.

Delivery rubric (0.7.6): `benchmarks/rubrics/the-binding-of-isaac-rebirth/floor1-v4.json` (`the-binding-of-isaac-rebirth-floor1-v4`, ten milestones of 10 points). It keeps the four floor-1 distance steps and the two collectibles of `floor1-v3`, and replaces its two 20-point milestones with four floor milestones of 10: reach floors 2, 3, 4 and 5, each requiring the previous one, with floor 2 also requiring the boss room. Every milestone lies on the way to beating the game or always helps it. The `floor1-v3` description below still applies to the shared milestones.


`benchmarks/rubrics/the-binding-of-isaac-rebirth/floor1-v3.json` (`the-binding-of-isaac-rebirth-floor1-v3`, uncalibrated, 100 points). The release 0.7 delivery runs never left floor 1 under the earlier `floors-v2`, so every cohort scored 0. The owner therefore decided to score progress on floor 1 and collectible items. This is a recorded exception to the cohort rule against rewarding collectibles and exploration.

| Milestone | Native-evidence requirement | Points |
| --- | --- | --- |
| `floor1-closer-1` to `floor1-closer-4` | On floor 1 of the fixed seed, enter a room 3, 2, 1 and 0 room transitions from the boss room (the start room is 4); each requires the previous one | 4 × 10 |
| `collectible-1`, `collectible-2` | Pick up a first and a second collectible item in one episode (`Adding collectible`) | 2 × 10 |
| `floor-1-boss` | Defeat the floor 1 boss and reach the second floor; requires `floor1-closer-4` | 20 |
| `floor-3` | Reach the third floor; requires `floor-1-boss` | 20 |

Distances come from [floor1-mvsn-tfs1.json](floor1-mvsn-tfs1.json). It was exported once in an operator development run with the debug console's `Level:GetRooms()` (never in evaluation), and records every floor-1 room by grid index, type and variant, with its distance to the boss room through normal doors. The log identifies rooms by type and variant (`Room 1.916(...)`). Distances apply only on that exact floor: stage 1, stage type 0 and the recorded level seed. The route is start (84) → 71 → 58 → 45 → boss (44).

`floors-v2` (floors 2 to 5 and Mom) is kept because the delivery runs were run under it.

## Finer rubric

`benchmarks/rubrics/the-binding-of-isaac-rebirth/points-v1.json` (`the-binding-of-isaac-rebirth-points-v1`) has 52 scoring points totalling 100, every one read from the native `log.txt` lines the evaluator already keeps (`Room T.V(name)`, `Adding collectible`, `Level::Init m_Stage`, `Mom clear time`), so `score-trial` recomputes it from any preserved run.

- **Progress, 27 points (58 of 100):** leave the start room; clear the two floor-1 rooms that hold enemies; the four floor-1 distance steps; enter every normal floor-1 room; reach floors 2 to 8 (Mom's floor is 6, the Womb 7 and 8); defeat Mom; enter 3, 5, 8, 12, 16, 20, 25, 30, 35, 40 and 50 different rooms.
- **Collection, 25 points (42 of 100):** hold 1 to 12 collectible items; enter a shop, treasure room, mini-boss room, secret room, super secret room, arcade, challenge room, library, devil room and angel room; enter treasure rooms on 2, 3 and 4 different floors.

Ratio: Isaac's run is a descent through floors, so progress carries more weight; items and special rooms are what the game itself rewards along the way (items change the character, special rooms hold items), so they form the collection group. Everything is reachable in about 2 hours: an ordinary player reaches Mom (floor 6) in well under an hour and the Womb soon after. Curse rooms, sacrifice rooms and dice rooms earn nothing, because entering them costs health or gambles the run. A room is counted once per floor, type and variant; two rooms with the same layout on one floor count once.

## Trial specs

All specs use rubric `the-binding-of-isaac-rebirth-floor1-v3` (the delivery runs ran under `floors-v2`), input profile `isaac-keys-v1` and `trial_memory` context, in `benchmarks/trials/the-binding-of-isaac-rebirth/`:

| Spec | Model | Budget | Execution |
| --- | --- | --- | --- |
| `deepseek-v41-thinking-live-3h.json` | `deepseek-v41-flash-thinking` | 10,800 s | live |
| `deepseek-v41-thinking-frozen-3h.json` | `deepseek-v41-flash-thinking` | 10,800 s | frozen steps, 0.5 s |
| `jev-live-1h.json` | `jev-1-14` | 3,600 s | live |
| `jev-frozen-1h.json` | `jev-1-14` | 3,600 s | frozen steps, 0.5 s |
| `gpt-6-astra-live-1life-3h.json` | `gpt-6-astra` | 10,800 s, one life | live |
| `claude-opus-5-5-live-1life-3h.json` | `claude-opus-5-5` | 10,800 s, one life | live |
| `gpt-6-astra-frozen-1life-3h.json` | `gpt-6-astra` | 10,800 s, one life | frozen steps, 0.5 s, `freeze_retry_timeout_credit` |
| `claude-opus-5-5-frozen-1life-3h.json` | `claude-opus-5-5` | 10,800 s, one life | frozen steps, 0.5 s, `freeze_retry_timeout_credit` |
| `grok-4-7-live-1life-3h.json` | `grok-4.7` | 10,800 s, one life | live, `freeze_retry_timeout_credit`, rubric `points-v1` |
| `grok-4-7-frozen-1life-3h.json` | `grok-4.7` | 10,800 s, one life | frozen steps, 0.5 s, `freeze_retry_timeout_credit`, rubric `points-v1` |
| `grok-4-7-live-1life-3h-age180.json` | `grok-4-7` | 10,800 s, one life | live, observation age limit 180 s (#280 rerun), `freeze_retry_timeout_credit`, rubric `points-v1` |
| `grok-4-7-live-1life-3h-age300.json` | `grok-4-7` | 10,800 s, one life | live, observation age limit 300 s (owner-approved #280 rerun), `freeze_retry_timeout_credit`, rubric `points-v1` |
| `kimi-k3-1-pro-live-1life-3h.json` | `kimi-k3-1-pro` | 10,800 s, one life | live, observation age limit 240 s, `freeze_retry_timeout_credit`, rubric `points-v1` |
| `kimi-k3-1-pro-frozen-1life-3h.json` | `kimi-k3-1-pro` | 10,800 s, one life | frozen steps, 0.5 s, `freeze_retry_timeout_credit`, rubric `points-v1` |

Jev Trials end at the first native death (`death_without_memory`). The earlier Claude and non-thinking DeepSeek pilot specs were removed; their local results do not calibrate.

```bash
.venv/bin/python -m gamecua.cli trial --trial-spec benchmarks/trials/the-binding-of-isaac-rebirth/deepseek-v41-thinking-live-3h.json --snapshot <snapshot-dir> --installation <installation> --output runs/isaac/trial-001
.venv/bin/python -m gamecua.cli resume-trial --run-dir runs/isaac/trial-001
.venv/bin/python -m gamecua.cli score-trial --run-dir runs/isaac/trial-001
.venv/bin/python -m gamecua.cli export-trial --run-dir runs/isaac/trial-001 --output runs/isaac/portable-001
```

Release 0.7 delivery runs (one Trial each, 2026-10-26), rescored post hoc under `floor1-v3`: DeepSeek thinking 40 live and 40 frozen (reached the room next to the boss room and collected Tech X); Jev 10 live and 10 frozen (one room toward the boss, then a fixed move-up, shoot-down input every step, closed early with the optional cost-saving stop). Under `floors-v2` all four scored 0. See [VALIDATION.md](VALIDATION.md).

## Known limitations

- The rubric is uncalibrated. Floor, Mom and Epilogue log lines were observed live on 2026-10-25 in an operator development run that used the debug console (never enabled in evaluation snapshots); a room entered with the console `goto` command logs neither line, so only the floor's real boss room counts.
- Operator checks were done with llvmpipe software rendering at four CPUs (60 fps).
- A restart with R is scored as a failed attempt by the evaluator.
- One fixed seed; scores do not establish performance across seeds.
