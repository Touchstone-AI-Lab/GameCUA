# Don't Starve survival benchmark

## Frozen cohort: operator-directed, maintainer review pending

On 2026-11-10 the operator directed Frozen execution of the two new models with the previously supplied credentials. Two sequential Frozen cells are authorised: `gpt-6-astra` and `claude-opus-5-5`, one life each, 10,800 charged seconds each, `frozen_steps` with three-second host steps, `dont-starve-controls-v5`, and the unchanged `prepared-longday-v4` snapshot.

This operator go-ahead is **not** maintainer rubric approval. Pull request #225 still has no review, and `dont-starve-survival-collection-v6` remains an unreviewed candidate. Scores from these cells are recorded under the rubric id they started with and are not presented as reviewed results.

Execution uses the derived image `gamecua-environment:0.7.6-dont-starve-v6-frozen-20261110` (`sha256:91053a809651a72bf3bcad3af18f6ec82f81e9850a75b4153b0ef4f570669d3d`). It overlays the installed 0.7.6 base `sha256:f524b59c7f24aec1109efa6b64e65db4c998eb73bb4e7cb54d3a480977910b2e` with only the Don't Starve game module and benchmark JSON. All ten checked shared core modules are byte-identical across base, derived image and host; no core module is patched, no clock is hidden and no new retry semantics are introduced. The disclosed 0.7.6 provider failure policy (`charged_retry_then_interrupt`) is unchanged, which the protocol permits.

The source snapshot recorded before the Frozen configuration changes is commit `1fec015d`. The image records 295 source-input hashes, so committing the Frozen specs and documentation does not alter an in-flight Trial. See [VALIDATION.md](VALIDATION.md) for the recorded execution state.

## Current published delivery

All four current cells are comparison eligible. Original assessments and historical evidence remain unchanged.

| Model | Execution | Runtime / evidence | v5 score / 100 | Completion |
| --- | --- | --- | --- | --- |
| DeepSeek Flash, thinking high | Live | 0.7.2 retained; first two attempts | 10 | Two native deaths already preserved |
| DeepSeek Flash, thinking high | Frozen, 3 s steps | 0.7.2 retained; first two attempts | 30 | Two native deaths already preserved |
| Jev 1.14.0 | Live | Fresh 0.7.6; one attempt, 7,200 s cap | 10 | First native death at 649.955 charged seconds |
| Jev 1.14.0 | Frozen, 3 s steps | Fresh 0.7.6; one attempt, 7,200 s cap | 10 | First native death at 1,351.320 charged seconds |

The four old delivery Trials were rescored with explicit episode limits: two for DeepSeek and one for Jev. The old Jev live/frozen scores are 10/0 but neither covers one attempt, so they remain excluded from the current comparison. New Jev Trials use empty context and end at their first verified native death without manual stops. Their 46/196 executed actions all match the native typed answers.

The `dont-starve-continuous-survival-v5` rubric retains the approved five-day continuous-survival target and refines v4 into ten 10-point thresholds at half-day intervals. One native day is 480 seconds. Each threshold requires living native-age advance after verified setup and at least the corresponding number of additional whole clock cycles. All ten thresholds measure direct progress toward the same survival target. Existing age, optional crafting and survival time from another life earn no credit. The whole-day predicates and all published historical rubric files are unchanged; five additional half-day predicates use fields already preserved by the native observer. This continuous-game setting does not claim Adventure Mode completion.

`game.json` declares `budget: "attempts"`: a native survival death ends a world. New language-model specs permit two attempts within 21,600 seconds, with bounded summarized memory inherited after the first death; Jev permits one attempt within 7,200 seconds. The shared workflow ends at the attempt limit, a verified win or the time cap, whichever comes first. Both cohorts have live and frozen specs and share controls-v5. The fixed undeveloped Wilson Long Day snapshot, default resources and disabled DLC retain the previously documented team latency-based difficulty exception.

All current cells use the same undeveloped Wilson snapshot: official Linux Steam app 219740, DLC disabled, native Long Day option, default resources and HUD size 10. Native preparation saved at age 22.700001183897, cycle 0 and health 150 with empty inventory. Snapshot SHA256 is `459353d6d4af14f903a23ae529aab5249ddf027f44ae0f5e325a03f208a2afc9`. Long Day is the declared difficulty adjustment under the team's latency exception; maximum custom settings were not benchmarked. A historical autonomous 2,400-second frozen calibration survived the first night and scored 20 under v4 before the original campaign configuration was frozen. Its gate and starting bytes are retained; it is excluded from formal results.

The retained DeepSeek trials use official-service `deepseek-flash`, thinking enabled with high effort, original 0.7.2 runtime and `dont-starve-controls-v4`. New Jev trials use the official 0.7.6 base plus the game integration and `dont-starve-controls-v5`: 27 unchanged keyboard/scroll choices and four native Box pointer choices for left click, right click, hover and drag. Five Box questions provide the targets, including separate drag source and destination. The historical 0.7.4 120-second autonomous Box calibration completed 14 actions before that release's formal freeze; controls-v5 and the pointer implementation are retained. Left-click execution was observed in that calibration; tests cover all pointer modes. No operator actions substitute for autonomous experiment actions.

Use `survival-v5-deepseek-{live,frozen}-6h.json` and `survival-v5-jev-{live,frozen}-2h.json` for new Trials; frozen execution uses three-second host-time steps. The retained historical DeepSeek Trials keep controls-v4 and original 0.7.2 attribution. Retrospective scoring considers only their first two attempts and appends a new immutable score. It does not relabel their controls or original budget, and no identical-profile aggregate comparison is claimed. Controls describe native bindings without recipes, strategies, setup details or evaluator goals. The game-specific 0.2-second pointer hover is charged normally.

`trials.py` remains the sole execution workflow. Both modes charge inference, retries, later preparations and downtime. Language-model death restarts within the same trial and original budget with bounded same-model summarized knowledge. Jev ends at its first native death. Recovery stays in the original episode and never replays uncertain actions. The rubric interview remains separate from gameplay; Jev has no interview or inherited memory.

The current shared optional Jev stop rule requires the last 30 consecutive actions or action groups to repeat the same fixed behavior while the screen shows no large change. Preserve the reviewed action/frame hashes and reason `manually observed ineffective loop; experiment closed to save tokens`, request the canonical Trial `STOP`, and score normally. The 2026-10-26 stops used the historical researcher rule; their original assessments remain unchanged. In a retrospective assessment with `--episode-limit 1`, a stop without a native death does not cover the attempt budget and is comparison-ineligible. The historical 0.7.4 validation table quotes the original scores. Repeated keys or slightly different Box coordinates alone do not establish a loop; actual game frames must show no progress.

Use the managed environment with this game integration and an exclusively prepared, licensed official Steam client. Store the prepared save under `snapshots/dont-starve/`, then provide a local copy through the environment snapshot binding. Keep `DEEPSEEK_API_KEY` and `TYPESAFE_API_KEY` in private environment configuration. For example, after creating an evaluation environment:

```bash
python -m gamecua.cli env-trial \
  --environment runs/dont-starve/formal-jev-live/environment \
  --trial-spec benchmarks/trials/dont-starve/survival-v5-jev-live-2h.json \
  --seconds 7200 --name trial
python -m gamecua.cli score-trial \
  --run-dir runs/dont-starve/formal-jev-live/environment/work/trial
```

The original 9,213 export files used for this migration retain their hashes. Live Jev video has one declared 1.004-second startup sampling gap; frozen video has no sampling gap. Both native streams are continuous and both encoders closed successfully. Earlier independent retrieval verified all 12,240 preserved 0.7.2 files and 1,165 new 0.7.4 files against their sealed indexes. Offline canonical scoring reproduced all four historical v4 cells, three earlier calibrations, both qualifying Jev cells, both excluded frozen attempts and the Box smoke. Exact reproduction images are disclosed for two earlier calibrations whose original images are unavailable. Original assessments, native evidence, screenshots and recordings are preserved. Fetch Git LFS objects before checking hashes or reproducing scores. Private native process output, Steam account state and credentials are excluded. See [VALIDATION.md](VALIDATION.md) for stop evidence and limitations.

Its evidence and scores are unchanged. Its frozen DeepSeek trial scheduled only 851.5 action-window seconds across two episodes, below the old first tier of 1,920 seconds even without death. The approved five-day target, three-second steps and native first-night calibration addressed that execution-horizon mismatch before fresh v4 trials.

Short calibrations are excluded from formal comparisons. Experiment results are not kept on `main`.

## Configuration versions

Use `survival-v5-*` and `dont-starve-controls-v5` for new trials. Earlier inputs, rubrics and trial definitions are retained for historical campaign attribution; they are not additional current delivery cells. Their files and the historical scoring predicates remain unchanged.

Observation-age reruns permit one extra Live specification per model that exceeded the observation-age rejection line: `claude-opus-5-5-live-3h.json` keeps the original model, inputs and rubric, and sets `observation_age_limit_seconds` to 240 with `freeze_retry_timeout_credit`. It replaces only the Live `claude-opus-5-5` result, which is recorded in [VALIDATION.md](VALIDATION.md).

## Starting state

The exact prepared start is [`snapshots/dont-starve/prepared-longday-v4/`](../../../snapshots/dont-starve/prepared-longday-v4/README.md). Its README provides preparation, restoration and validation commands. Extract `snapshot.tar.gz` into an empty directory, run `gamecua.games.dont_starve.setup.validate_snapshot` on that directory, and require hash `459353d6d4af14f903a23ae529aab5249ddf027f44ae0f5e325a03f208a2afc9` before binding it to an evaluation environment. This matches both current Jev Trials and both retained DeepSeek Trials. Keep saves in `snapshots/`; a changed start gets a new snapshot name.
