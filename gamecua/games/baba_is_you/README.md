# Baba Is You

Experimental integration (game id `baba-is-you`, Steam app 736260): native Linux build 24529734, 1280x720, `xtest` input backend, turn based (the game waits for input, so there is no pause or frozen mode). Each episode launches the native `Chowdren` binary directly in an isolated profile containing only the frozen default `SettingsC.txt`; the native build needs no Steam API connection. Input profile `baba-keys-v1` offers one ordinary key per 0.2 s step (arrows, Z undo, R restart, Return); Return selects a level on the map and waits a turn inside a level. See [VALIDATION.md](VALIDATION.md).

## Setup and snapshot

Install the game with your own licensed account through the official Linux Steam client in a development Steam environment, then provide it as a read-only installation (on hosts where Steam needs user namespaces, set `GAMECUA_STEAM_APPARMOR_PROFILE`; evaluation environments do not use Steam). Capture the snapshot from the frozen settings file:

```bash
.venv/bin/python -m gamecua.games.baba_is_you.setup --settings /path/to/SettingsC.txt --output runs/baba-is-you/setup
```

With no slot save the game skips the main menu; preparation dismisses the splash screen with one Return and verifies the opening level by its rule-text colors on three consecutive frames. Setup is verified only if the new slot `0ba.ba` is the sole slot and contains no cleared level. A level counts as cleared when its `[baba]` entry has state `3`; the game rewrites the slot after every win and each changed slot is preserved as native evidence.

## Rubric

Current rubric `baba-victory-v4` ([victory-v4.json](../../../benchmarks/rubrics/baba-is-you/victory-v4.json)), ten milestones of 10 points; each requires the previous one and all ten lie on every route to the first ending. The budget form is `time`: levels restart or undo and no native death ends a run.

| Milestone | Native-evidence requirement | Points |
| --- | --- | --- |
| Level 0 | `0level` cleared | 10 |
| Level 1 | `0level` and `1level` cleared | 10 |
| Opening 3 | Also one of `189level` or `3level` | 10 |
| Opening 4 | Also one of `5level` or `6level`, the last opening level before the first numbered area | 10 |
| Area level | `[baba_prize]` counts a new clear inside any of the ten numbered areas | 10 |
| Area levels 4 | Four new clears counted in `[baba_prize]` across the numbered areas | 10 |
| Area 1 | A numbered area completed (`<area>level=3` in `[baba]`) | 10 |
| Two areas | Two numbered areas completed | 10 |
| Three areas | Three numbered areas completed; the gate before the final level opens at three area completions | 10 |
| Finale | `203level` (a way out?, map id `finale`) cleared | 10 |

The route facts come from the native map files and the running game. Every area completion needs at least its `unlockcount` of cleared levels inside the area (the area's `[baba_prize]` count equals its cleared levels), so four area clears precede any completion. On the main map only `0level` and `1level` are unavoidable, then one of `189level` or `3level`, then one of `5level` or `6level` before the first area; the gate before `203level` has requirement 3 of the area-completion count. An area is completed once its cleared levels reach the area's `unlockcount` (8 for the lake); the game then writes `<area>level=3` in `[baba]` and increments `[baba_clears]`. The game has no difficulty setting.

### Finer rubric `baba-victory-v5`

[victory-v5.json](../../../benchmarks/rubrics/baba-is-you/victory-v5.json) is the finer rubric: 52 independent points totaling 100, with no prerequisites, all read from the slot save by evaluator `baba-progress-6` (which keeps every v4 predicate).

| Group | Points | Native-evidence requirement |
| --- | --- | --- |
| Progress (26) | 4 x 2 | The v4 opening route: `0level`; `1level`; one of `189level`/`3level`; one of `5level`/`6level` |
| | 4 x 1 | 1, 2, 3 and 4 numbered areas entered (new `<area>level_intro=1` in `[baba]`) |
| | 7 x 2 | 1 to 7 new lake clears (`[baba_prize]` `177level`) |
| | 1 x 2 | The lake completed (`177level=3`) |
| | 3 x 2 | 10, 12 and 15 new clears across the numbered areas (`[baba_prize]`) |
| | 2 x 2 | 1 and 4 new clears in numbered areas other than the lake |
| | 1 x 2 | A second numbered area completed |
| | 4 x 2 | 8, 16, 24 and 30 newly cleared levels in total (state `3` in `[baba]`) |
| Choice (26) | 26 x 2 | A named level cleared: the six branch levels of the main map (`189`, `3`, `2`, `90`, `5`, `6`), lake levels 1 to 13 and solitary island levels 0 to 6 |

## Trial specs

| Spec | Model | Budget |
| --- | --- | --- |
| `benchmarks/trials/baba-is-you/deepseek-victory-3h.json` | `deepseek-v41-flash-thinking` | 10,800 s |
| `benchmarks/trials/baba-is-you/jev-victory-1h.json` | `jev-1-14` | 3,600 s |

Both use input profile `baba-keys-v1`.

```bash
.venv/bin/python -m gamecua.cli trial --trial-spec benchmarks/trials/baba-is-you/deepseek-victory-3h.json --snapshot runs/baba-is-you/setup --seconds 300 --output runs/baba-is-you/trial-001
.venv/bin/python -m gamecua.cli score-trial --run-dir runs/baba-is-you/trial-001
.venv/bin/python -m gamecua.cli export-trial --run-dir runs/baba-is-you/trial-001 --output runs/baba-is-you/portable-001
```

`resume-trial` recovers an interrupted Trial.

## Known limitations

- The rubrics are uncalibrated beyond the delivery runs recorded in [VALIDATION.md](VALIDATION.md); `baba-victory-v3` and its two delivery runs were rescored under v4, and every 0.7.x cell under v5.
- Escape opens the in-game menu; the language model may type it freely and can return to the title screen, which offers other level packs, a level editor, save erasure and exiting the game. Progress in other level packs earns nothing, and exiting ends the Trial as a process failure.
- Software rendering only was used for validation.
