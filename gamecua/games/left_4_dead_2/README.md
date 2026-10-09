# Left 4 Dead 2

Experimental roster game (Cooperative FPS, owner Zhuhan Bao). The integration uses the licensed official Linux Steam build (app 550) and the hotel chapter of a fresh Dead Center campaign on Easy (an owner decision recorded in `game.json`: on Expert the human died within 30 minutes and the run never left the first chapter), with one human survivor and three native survivor bots. Original map-spawn scripts are preserved; a read-only observer (`observer.nut`) writes player-attributed native events into private incremental files. Cheats and the developer console are disabled, and evaluator records are not shown to the agent. Timing is `realtime` with a process pause (`SIGSTOP` of the `hl2_linux` engine process), so Trials run live and in frozen steps. Process recovery is not supported. `game.json` status is `configured`. Validation history is in [VALIDATION.md](VALIDATION.md).

## Setup and snapshot

- Needs your own licensed Steam installation of Left 4 Dead 2 inside a Steam environment (`env-create --steam`, then `env-steam-prepare --app-id 550`; see the root README). Game files and Steam state are never redistributed. `snapshots/left-4-dead-2/` holds only `new.txt` for this game: each run starts a fresh campaign, and the AI Director randomizes common infected, special infected and item spawns in every run. The game has no seed setting, so no save can fix this; the owner accepted the randomness on 2026-10-29 rather than modify the game scripts.
- Capture is native 640x360 with 200 ms key taps (input time is charged). Software Vulkan needs 32-bit lavapipe; the legacy PNG capture comes from the official Steam runtime.
- Input is keyboard only so that both model forms share one profile (`benchmarks/inputs/left-4-dead-2/keys-v1.json`): WASD move, arrow keys turn and look, J fires, K shoves, E uses, R reloads, Space jumps, Left Control crouches and keys 1 to 5 select slots. `baseline.cfg` binds these keys, removes the mouse binds and makes mouse motion inert; yaw and pitch speeds are 90 degrees per second.
- `setup.create_snapshot(installation, videodefaults, output)` freezes `preparation.json`, `baseline.cfg`, the native low `video.txt` and this machine's `videodefaults.txt` in `snapshot.manifest.json`. Missing hardware defaults can reset graphics on first startup; different render hardware needs its own snapshot.
- Installation identity hashes `hl2.sh`, `hl2_linux`, `gameinfo.txt`, `update/pak01_dir.vpk` and `video_bench_low.txt`.

## Current rubric

`benchmarks/rubrics/left-4-dead-2/hotel-v1.json` (`left-4-dead-2-hotel-v1`, uncalibrated, 100 points). The task is the hotel chapter only: completing it ends the run as a victory. The score is the share of the route from the rooftop to the safe room that the living human has covered, rounded down to a whole number: 99 milestones of one point (`route-1` to `route-99`) plus one point for completing the chapter, which also awards every route point.

The route is `route.json`: the shortest path over the navigation mesh in the game's own `c1m1_hotel.nav` from the rooftop spawn area to the safe room door area, 14,263 units long, in two legs because the elevator ride adds no length. For each observer sample with the human alive, `progress.route_progress` projects the position onto the nearest part of a leg within 150 units horizontally and 100 units vertically and takes the distance along the route. The furthest distance over the Trial, minus the distance of the spawn position (281 units), divided by the remaining length, gives the percentage; at most 99 until `map_transition` on `c1m1_hotel` fires with the human alive. Combat, healing and survival earn nothing, and standing still scores 0. A position that passes close to a later part of the route (the route doubles back) can credit a point or two early.

`benchmarks/rubrics/left-4-dead-2/points-v1.json` (`left-4-dead-2-points-v1`, first batch, uncalibrated, 100 points): sixty scoring points worth 1 or 2 points each, all read from the native telemetry rows, so a finished run can be rescored with `score-trial --rubric`.

- **Progress (30):** the share of the hotel route covered alive in steps of 3 percent (`route-3` to `route-87`) plus completing the chapter.
- **Collection (30):** infected killed by the human (10 to 300), special infected killed (1 to 16), heals (1 to 4), revives (1, 2), shots fired (25, 100, 300) and time stayed alive (2 to 20 minutes). The survival points need `route-9` first, so standing still earns nothing. Every counter is counted over the baseline recorded at the start and only while the human is alive.
- **Specs:** `points-v1-live-3h.json` (`deepseek-v41-flash-thinking`, one life, 10,800 s, live only) and `jev-points-v1-live-2h.json` (`jev-1-14`, 1 attempt, 7,200 s).

## Trial specs

| Spec | Model | Budget | Mode |
| --- | --- | --- | --- |
| `benchmarks/trials/left-4-dead-2/hotel-v1-live-3h.json` | `deepseek-v41-flash-thinking` | 10,800 s | live |
| `benchmarks/trials/left-4-dead-2/hotel-v1-frozen-3h.json` | `deepseek-v41-flash-thinking` | 10,800 s | frozen, 0.5 s steps |
| `benchmarks/trials/left-4-dead-2/jev-hotel-v1-live-1h.json` | `jev-1-14` | 3,600 s | live |
| `benchmarks/trials/left-4-dead-2/jev-hotel-v1-frozen-1h.json` | `jev-1-14` | 3,600 s | frozen, 0.5 s steps |

Run them with the shared commands, for example:

```bash
.venv/bin/python -m gamecua.cli trial --trial-spec benchmarks/trials/left-4-dead-2/hotel-v1-frozen-3h.json --snapshot <prepared-snapshot> --installation <installation> --output runs/left-4-dead-2/trial-001
.venv/bin/python -m gamecua.cli score-trial --run-dir runs/left-4-dead-2/trial-001
.venv/bin/python -m gamecua.cli export-trial --run-dir runs/left-4-dead-2/trial-001 --output runs/left-4-dead-2/portable-001
```

`resume-trial` continues an interrupted trial only where recovery is supported (it is not for this game, see below). In containers use `env-trial` as in the root README.

## Known limitations

- Software rendering is slow (roughly 10-14 FPS in development; native time advanced about 84% of wall time in the 30-minute run), so failures cannot be attributed to latency alone.
- Chapter completion has not been seen in a live autonomous run; only offline tests cover it. The route positions come from the map and navigation files, and the best live run reached about 12 percent of the route.
- Process recovery is not supported (recovery is rejected).
- The hotel-v1 rubric was defined after the first Easy runs and is uncalibrated; it is not a leaderboard.
