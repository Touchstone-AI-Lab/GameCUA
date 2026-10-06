# Stardew Valley

Experimental integration of native Linux Stardew Valley 1.6.15 (build 24356, Steam App ID 413150) from a prepared Year 1, Spring 2 save. Roster status: `experimental` (catalog status `configured`). Timing is `realtime` with pause method `process`: in-game time advances during model latency outside menus, so Trials run live and in `frozen_steps` (2 s of game time per action). The ending is the restored Community Center. There is no native death (exhaustion or zero health makes the farmer pass out and wake the next day), so every episode, including Jev's, runs to the deadline. Native saves are written only when the farmer sleeps or passes out, so evidence lags in-day progress. There is no calibrated leaderboard. See [VALIDATION.md](VALIDATION.md).

## Setup and snapshot

- Requires the licensed official installation (tested: 1.6.15, Steam build 16826371). Game files are not redistributed. The starting save is in `snapshots/stardew-valley/`.
- The prepared state is a new standard farm with Skip Intro and the default 100% profit margin whose first night was slept to obtain the earliest native save (Year 1, Spring 2, 6:00 am, 500g, 12-slot backpack). Capture it with `gamecua.games.stardew_valley.setup.capture_snapshot(source, target)`, which copies the save read-only into a new directory outside the source profile, fails if the save changes during capture, and writes `snapshot.manifest.json`.
- Difficulty: the game has no difficulty setting. Profit margin stays at 100% because the prepared snapshot uses it and the setting only scales sale prices; a lower margin would require a new snapshot and would change no bundle requirement except the purchased Vault bundles.
- Episodes run the game directly in an isolated profile. MonoGame samples input once per frame, so clicks must be held (harness default 0.2 s).
- Frozen steps send SIGSTOP to the verified game process (`PausableProcess`); the pause is released before the game is stopped or closed.
- Runtime used so far: 1280x720, software llvmpipe, 2 CPUs, 3 GiB.

## Input profile

`benchmarks/inputs/stardew-valley/kbm-v2.json` (`stardew-kbm-v2`, step 2 s), shared by both model forms. Four groups: `move` (W, A, S, D and diagonals, one held every step), and, each with a `none` choice, `hand` (C uses the selected tool or item, X interacts), `keys` (toolbar slots 1 to 0, E, Escape, F, M) and `point` (left click on a 16 by 9 screen grid). A click replaces the keyboard choices for that step. Version 1 also offered `none` in `move`; in a Jev smoke run every group chose `none` on all 44 steps, so the farmer never left bed, and that idle choice was removed. The 2 s step balances Jev key holds (about nine tiles of walking) against frozen-step game time: 0.5 s steps would let a three-hour thinking-model Trial advance less than one in-game day.

## Jev pointer rerun on 0.7.4

`benchmarks/inputs/stardew-valley/pointer-v1.json` (`stardew-pointer-v1`) keeps the keyboard groups and 2 s step from `stardew-kbm-v2`, replacing the fixed 16 by 9 click grid with native Box-located left and right clicks. A click still replaces the keyboard choices for that step. The profile supplies controls only; it adds no evaluator goals. These reruns use release 0.7.4, which includes the native Box pointer transport introduced in 0.7.3.

The four `community-center-v2-pointer-*` and `jev-community-center-v2-pointer-*` specs share this profile and the unchanged rubric, with the usual 3 h language-model and 1 h Jev budgets. The October 27 rerun targets only Jev live and frozen; the corresponding language-model specs are configured but have not been rerun. Historical grid-profile results retain their original attribution and are not matched-input comparisons with the new pointer runs. The original specs and profile remain available.

Use a fresh evaluation environment for each run and explicitly pass the complete 3,600 s Jev budget. When using the published or release-source image with a newer local catalog, pass that catalog to `Environment.trial(..., catalog=...)` so the frozen trial includes the new profile and spec.

## Current rubric

`benchmarks/rubrics/stardew-valley/early-game-v1.json` (`stardew-early-game-v1`, uncalibrated, 100 points): one hundred 1-point milestones, so the score is the number of points reached. Every point is read from the game-written save against the setup baseline (evaluator `stardew-progress-6`), is something an ordinary player reaches in about two hours of play from the Spring 2 snapshot, and rewards what the game itself encourages. The rubric stays hidden from the model.

| Group | Points | Native-evidence fields |
| --- | --- | --- |
| Places entered: Bus Stop, Town, beach, forest, mountain, backwoods, General Store, Blacksmith, museum, Fish Shop, Ranch, Carpenter's Shop, Community Center, Wizard's Tower | 14 | `locationsVisited` |
| Mine floors 1, 5, 10, 15, 20, 30, 40 | 7 | `deepestMineLevel` |
| Skill levels 1 to 3 in farming, fishing, foraging, mining and combat | 15 | `<skill>Level` |
| Income: any, then 250, 500, 1,000, 2,500 and 5,000 gold earned | 6 | `totalMoneyEarned` |
| Farming: soil tilled, a seed, 20 and 50 seeds sown, a harvest, a crop and 15 crops shipped | 7 | `dirtHoed`, `seedsSown`, farming experience, `cropsShipped` |
| Tools and gear: a cast, copper ore, a furnace, a copper tool, the 24-slot backpack | 5 | `timesFished`, `copperFound`, `craftingRecipes`, tool `upgradeLevel`, `maxItems` |
| Quests: 1, 3 and 5 completed | 3 | `questsCompleted` |
| Community Center: door letter, Junimo scroll, Junimo text, one and three bundles, one room | 6 | `mailReceived`, bundle flags, `areasComplete` |
| **Progress points** | **63** | |
| Fish species: 1, 2, 3, 5 and 8 | 5 | `fishCaught` |
| Different items shipped: 3, 5, 8, 10, 15 and 20 | 6 | `basicShipped` |
| Minerals 1, 3, 5; artifacts 1, 2; museum donations 1, 3, 5 | 8 | `mineralsFound`, `archaeologyFound`, museum `museumPieces` |
| Different recipes crafted: 1, 3 and 5 | 3 | `craftingRecipes` counts |
| Items foraged 1, 10, 30; monsters slain 1, 10 | 5 | `itemsForaged`, `monstersKilled` |
| Villagers met 3, 5, 10, 15, 20; gifts 1, 5; one heart, two hearts, three villagers at one heart | 10 | `friendshipData`, `giftsGiven` |
| **Collection points** | **37** | |

The bundle chain keeps its order (`first-bundle` needs `junimo-text-readable`, then `three-bundles`, then `first-room`); no other point has a prerequisite. Points that need more than about two hours (three rooms, the restored Center, 10,000 gold) are left out. A Trial whose setup record predates evaluator `stardew-progress-6` lacks the new baseline fields; they count from zero, which matches the Spring 2 snapshot (no places, finds, museum pieces or counted quests).

`stardew-community-center-v2` (ten 10-point milestones toward the Community Center) remains for the October 2026 results, as do `stardew-community-center-v1` and `stardew-progress-v2`. Their predicates stay in the evaluator so earlier Trials can be rescored.

## Trial specs

All use input profile `stardew-kbm-v2`, `pure_image_no_rules`, `episode_context: trial_memory` and 2 fps recording. Language models run one-life live and frozen specs, because the game is real-time; Stardew Valley has no native death, so each runs the full 3 h. The new-model specs use `provider_failure_policy: freeze_retry_timeout_credit`. The `community-center-v2-*` specs remain for the October 2026 results.

| Spec | Model | Rubric | Mode | Budget |
| --- | --- | --- | --- | --- |
| `early-game-v1-live-3h.json` | `deepseek-v41-flash-thinking` | `stardew-early-game-v1` | live, `episode_limit: 1` | 10,800 s |
| `early-game-v1-frozen-3h.json` | `deepseek-v41-flash-thinking` | `stardew-early-game-v1` | frozen steps, 2 s, `episode_limit: 1` | 10,800 s |
| `early-game-v1-claude-opus-5-5-live-3h.json` | `stardew-valley-claude-opus-5-5-high` | `stardew-early-game-v1` | live, `episode_limit: 1` | 10,800 s |
| `early-game-v1-grok-4-7-live-3h.json` | `grok-4.7` | `stardew-early-game-v1` | live, `episode_limit: 1` | 10,800 s |
| `early-game-v1-grok-4-7-frozen-3h.json` | `grok-4.7` | `stardew-early-game-v1` | frozen steps, 2 s, `episode_limit: 1` | 10,800 s |
| `early-game-v1-gpt-6-astra-live-3h.json` | `gpt-6-astra` | `stardew-early-game-v1` | live, `episode_limit: 1` | 10,800 s |
| `early-game-v1-gpt-6-astra-frozen-3h.json` | `gpt-6-astra` | `stardew-early-game-v1` | frozen steps, 2 s, `episode_limit: 1` | 10,800 s |
| `early-game-v1-grok-4-7-live-3h.json` | `grok-4-7` | `stardew-early-game-v1` | live, observation age limit 240 s, `episode_limit: 1` | 10,800 s |
| `early-game-v1-kimi-k3-1-pro-live-3h.json` | `kimi-k3-1-pro` | `stardew-early-game-v1` | live, observation age limit 240 s, `episode_limit: 1` | 10,800 s |
| `early-game-v1-kimi-k3-1-pro-frozen-3h.json` | `kimi-k3-1-pro` | `stardew-early-game-v1` | frozen steps, 2 s, `episode_limit: 1` | 10,800 s |
| `early-game-v1-claude-opus-5-5-frozen-3h.json` | `stardew-valley-claude-opus-5-5-high` | `stardew-early-game-v1` | frozen steps, 2 s, `episode_limit: 1` | 10,800 s |
| `community-center-v2-live-3h.json` | `deepseek-v41-flash-thinking` | `stardew-community-center-v2` | live | 10,800 s |
| `community-center-v2-frozen-3h.json` | `deepseek-v41-flash-thinking` | `stardew-community-center-v2` | frozen steps, 2 s | 10,800 s |
| `jev-community-center-v2-live-1h.json` | `jev-1-14` | `stardew-community-center-v2` | live | 3,600 s |
| `jev-community-center-v2-frozen-1h.json` | `jev-1-14` | `stardew-community-center-v2` | frozen steps, 2 s | 3,600 s |

All are under `benchmarks/trials/stardew-valley/`. The older `deepseek-*` and `qwen-speed-*` specs use the historical rubric and model ids (non-thinking DeepSeek, Qwen endpoint); results from them do not calibrate. Use a fresh evaluation environment per Trial.

```bash
python -m gamecua.cli env-trial --environment <evaluation-environment> \
  --trial-spec benchmarks/trials/stardew-valley/early-game-v1-live-3h.json --seconds 10800
```

Then use the shared `resume-trial`, `score-trial` and `export-trial` commands (`--run-dir`; `--help` for arguments). Recovery continues the same episode with an unchanged deadline; downtime is charged.

## Known limitations

- One prepared state does not establish performance across farm types or starting conditions.
- Score weights are operational choices, not calibrated difficulty weights; zero is an accepted result.
- Room predicates are tested on synthetic saves; `areasComplete` was read on a real third-party save during acceptance but no autonomous Trial has restored a room.
- Evidence only appears after a day ends, so late progress in an unslept day is not scored.
- The process pause is proven on a real child process; its effect on the in-game clock still has to be checked in the real game.
- Image must include evaluator `stardew-progress-5`; record the image digest with every Trial.
