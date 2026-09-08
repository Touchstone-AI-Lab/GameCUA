# Slay the Spire

Reference integration (roster status `verified`, Steam app 646570, V2.3.4, 1280x720, `xsend` input backend). The game is turn based, so it runs live only and needs no pause; the integration still declares a process pause, which the earlier frozen cells used. A Trial starts from the fixed-start snapshot `sts-a10-snapshot`: the same seed and floor 1 right after the opening fight, raised to Ascension 10 with the run-start effects up to A10 applied (HP 72 of 80, Ascender's Bane in the deck; see its `GOLDEN.json`). Ascension 10 was chosen over 20 after DeepSeek died three times to the same floor-6 elite on Ascension 20. Models see only screenshots and a controls reference generated from the input profile `sts-grid-v3` (a 16x9 click grid plus ordinary keys, 0.5 s steps). Validation results are in [VALIDATION.md](VALIDATION.md); the shared 0.7.0 entry is in the root `VALIDATION.md`.

## Setup and snapshot

Use your own licensed installation (Steam, official client login through `env-steam-prepare`); game files and account state are never redistributed, and the A10 delivery snapshot is `snapshots/slay-the-spire/sts-a10-snapshot/`. Prepare the fixed-start state in the game, then capture it read-only:

```bash
.venv/bin/python -m gamecua.cli snapshot-sts --encounter Cultist --output runs/slay-the-spire/setup
```

`--installation` defaults to the standard Steam directory. A prepared snapshot stays frozen within its Trial. Snapshot manifests (`snapshot.manifest.json`) pin the copied files and are checked before each episode.

## Rubric

Current rubric `sts-points-v1` ([points-v1.json](../../../benchmarks/rubrics/slay-the-spire/points-v1.json)): sixty scoring points, 30 progress and 30 collection, weighted 1 to 6 points each (100 in total): common early points are worth 1, and the points that no reference run has earned yet (gold 500, maximum HP 90, a card removed, five and six relics, five upgrades, floor 25, the act one boss defeated) are worth 3 to 6, which leaves headroom above the reference runs. Every point is read from the autosave or the run history that the game writes, so a finished run can be rescored with `score-trial --rubric`.

- **Progress (30):** reach floors 2 to 15 and 17 to 25 alive, the act one boss floor, the act one boss defeated, a first won fight, 5 and 10 enemies defeated, and 1 and 2 elites defeated. These stop at about the end of act two's first half, which a model or an ordinary player reaches in about 2 hours.
- **Collection (30):** relics owned (2 to 6), a boss relic, gold gained (150, 300, 500), maximum HP (85, 90), deck size (13, 16, 20), upgraded cards (1, 3, 5), a card removed, an uncommon and a rare card, potions obtained (1, 2, 3), a potion used, a campfire rest and a smith, a shop purchase, event choices (1, 3) and a fight won without damage. Rarity uses the Ironclad card lists in `progress.py`.
- **Specs:** [points-v1-live-3h.json](../../../benchmarks/trials/slay-the-spire/points-v1-live-3h.json) (`deepseek-v41-flash-thinking`, one life, 10,800 s, live only) and [jev-points-v1-live-2h.json](../../../benchmarks/trials/slay-the-spire/jev-points-v1-live-2h.json) (`jev-1-14`, 1 attempt, 7,200 s).

Earlier rubric (0.7.6) `sts-floors-v4` ([floors-v4.json](../../../benchmarks/rubrics/slay-the-spire/floors-v4.json)): twenty 5-point milestones that all lie on every winning route. Act one: floors 5, 7, 9, 11 and 13, the boss floor 16 and the act one boss defeated. Act two: floors 19, 22, 25, 28 and 31, boss floor 33 and the act two boss defeated. Act three: floors 36, 40, 44 and 48, boss floor 50 and the run victory. Floor numbers count map depth, so every route crosses each of them alive; elites, shops and other skippable content still earn nothing. The boss-reached and boss-defeated milestones require the previous boss step. Earlier rubric `sts-victory-v3` ([victory-v3.json](../../../benchmarks/rubrics/slay-the-spire/victory-v3.json)), an uncalibrated boss spine; elites, shops and other skippable content earn nothing. Each milestone is earned once per Trial and requires the previous one.

| Milestone | Native-evidence requirement | Points |
| --- | --- | --- |
| Act one boss reached | Reach the act one boss floor alive | 20 |
| Act one complete | Defeat the act one boss | 20 |
| Act two boss reached | Reach the act two boss floor alive | 20 |
| Act two complete | Defeat the act two boss | 20 |
| Run victory | Defeat the act three boss; the run history records victory | 20 |

## Trial specs

0.7.6 budget `attempts` (game.json): [floors-v4-live-6h.json](../../../benchmarks/trials/slay-the-spire/floors-v4-live-6h.json) (`deepseek-v41-flash-thinking`, 2 attempts, 21,600 s) and [jev-floors-v4-live-2h.json](../../../benchmarks/trials/slay-the-spire/jev-floors-v4-live-2h.json) (`jev-1-14`, 1 attempt, 7,200 s). The game is turn based, but the integration can pause the Java process (`SIGSTOP`, declared as `pause.method: process`), so frozen-step specs exist; their results stay valid, but new models run live only (a turn-based game runs live only). The pre-0.7.6 specs below stay for the published results.

| Spec | Model | Budget |
| --- | --- | --- |
| [victory-v3-live-3h.json](../../../benchmarks/trials/slay-the-spire/victory-v3-live-3h.json) | `deepseek-v41-flash-thinking` | 10,800 s |
| [jev-victory-v3-live-1h.json](../../../benchmarks/trials/slay-the-spire/jev-victory-v3-live-1h.json) | `jev-1-14` | 3,600 s |
| [jev-victory-v3-pointer-live-1h.json](../../../benchmarks/trials/slay-the-spire/jev-victory-v3-pointer-live-1h.json) | `jev-1-14` | 3,600 s |

The first two use input profile `sts-grid-v3`; the pointer spec uses `sts-pointer-v1` (Jev locates click and drag targets with native Box questions, plus E and Escape; release 0.7.4). All use and episode context `trial_memory` (death inherits bounded agent-written notes within the same deadline). Reference workflow:

```bash
.venv/bin/python -m gamecua.cli trial --trial-spec benchmarks/trials/slay-the-spire/victory-v3-live-3h.json --snapshot runs/slay-the-spire/setup --seconds 300 --output runs/slay-the-spire/trial-001
.venv/bin/python -m gamecua.cli score-trial --run-dir runs/slay-the-spire/trial-001
.venv/bin/python -m gamecua.cli export-trial --run-dir runs/slay-the-spire/trial-001 --output runs/slay-the-spire/portable-001
```

`resume-trial` recovers an interrupted Trial and `series --repeats N` runs independent repeats; omit `--seconds` for the full budget. All inference, retries, compaction, resets and recovery consume the original wall-clock deadline; only verified initial preparation is excluded. Report native milestones, outcome, time to milestones, score distribution, errors, usage and recording gaps; aggregate only eligible independent Trials, and report failures separately (episodes are not repetitions).

Reference results (one Trial each, 0.7.0): DeepSeek thinking scored 40 (act one boss defeated in episode 3), Jev scored 0 (a two-step Escape loop on floor 1).

## Known limitations

- One fixed seed with a few repeats does not establish performance across the seed distribution; rubric weights are operational choices, not calibrated difficulty weights.
- The Ascension 10 start was prepared by hand (run-start effects applied manually) from the fixed-seed save.
- The input profile includes an Escape button that can open the settings menu; Jev looped on it in the reference run.
- XTest did not deliver button events on the validation host, so the integration uses `xsend`.
- The calibration target is a DeepSeek score near 40; the single reference Trial sits at that ceiling.
