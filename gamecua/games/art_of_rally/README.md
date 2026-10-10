# art of rally

## Owner-requested Live execution

On 2026-11-10 the owner explicitly requested Opus 5.5 and GPT-6-Astra runs without waiting for core-maintainer rubric review. Each uses its own credential, high reasoning effort, one episode and a 10,800-second base allowance. The native snapshot, vehicle, controls and 1280x720 software rendering remain the V8 baseline; the scoring rubric is V9. Admission binds the exact model/spec/rubric/image and records `owner_requested_unreviewed_rubric`, without claiming maintainer approval or two-hour reachability validation.

The opt-in failure policy freezes through the existing native V8 pause mechanism. Confirmed 600-second timeouts extend the allowance by 600 seconds each; other errors do not. Repeated failures exhaust a 1-to-20-second backoff and hold the same live process for an operator decision. Creating `RESUME_PROVIDER` inside that Trial directory explicitly resumes the pending request and original conversation. There is no automatic new Trial or second life. Frozen retry time remains charged; an operator pause is separately recorded. The local campaign queues Opus and then Astra on the same official Steam session and exports each completed result separately.

Both model specs set a conservative 65,536-token operational context cap because the gateway does not report a context window. This is a configured cap, not a claim about either model's maximum capacity. Owner-requested execution does not establish compliance with the core-maintainer rubric review requirement.

Native Linux integration for art of rally (Steam App ID 550320, game ID `art-of-rally`). Contributor: Qifeng Chen. The roster remains `experimental`. The four completed V8 Trials have `comparison_eligible: true` in their assessments; this is a per-Trial result, not blanket native qualification or approval for repository-wide formal comparison. See [validation and limitations](VALIDATION.md).

## V9 checkpoint rubric awaiting maintainer review

The candidate [V9 rubric](../../../benchmarks/rubrics/art-of-rally/five-stage-checkpoints-v9.json), `art-of-rally-five-stage-checkpoints-v9`, implements the finer rubric format as **95 route checkpoints plus five native finishes**, each worth one point. All 100 points measure progress. The fixed-car custom rally has no collection objective, so adding unlock, menu or inventory rewards would change the task.

Each stage selects 19 distinct directed native segments near 5%, 10%, ..., 95% of its cumulative **3D arc length**. Selection `ordered-nearest-3d-midpoint-19-v1` uses geometry alone: for each fraction in ascending order, select the nearest segment midpoint after the previous selection, reserving enough later segments for the remaining checkpoints; ties choose the lower index. Fewer than 19 eligible geometry segments is an error. The formula is frozen in the evaluator before scoring. The exact geometry hash, direction and selected indices are recorded in each assessment when that stage's clean countdown is preserved. Unvisited stages have no observed geometry mapping; none is invented from model output. This does not claim that every stage's geometry has already been captured before a new run.

A selected segment earns its one point only when the existing native physics replay verifies a complete forward crossing of both endpoint planes, within the existing lateral/height corridor and continuity bounds. Dynamic overlap ambiguity still withholds credit. Recovery never fills a skipped segment; later actual crossings can earn their own points without requiring all earlier checkpoints. Repeated/backward travel cannot duplicate credit. The finish point requires the existing accepted player gate and non-retired official result. Later stages retain all preceding native-finish requirements in the same episode; native death stops further credit.

The endpoint assessment replays original immutable `native_chunk` records once and does not trust stored projections or mutable native journals. Every awarded point identifies its geometry hash, native sequence(s), evidence chunk/hash and first verified poll time. A point is counted only in a chunk preserved within the original budget, capped at 10,800 seconds for this historical rule; a chunk first preserved after the cap is excluded, not retrospectively interpolated. The one-episode endpoint rule prevents aggregation across lives.

Historical V8 proofs were published when aggregate integer points changed, so they can omit later checkpoint gains without a V8 score change. Reading the complete immutable chunk chain avoids that omission. Missing/malformed chunks fail assessment; missing evidence is not a model zero. Selection remains fixed regardless of the observed rescored totals.

On a harness with `score-trial --rubric` support (the implementation uses release 0.7.7), score an isolated copy of a retained run with:

```bash
python -m gamecua.cli score-trial \
  --run-dir /path/to/preserved-trial-copy \
  --rubric benchmarks/rubrics/art-of-rally/five-stage-checkpoints-v9.json
```

The four audited completions each contain exactly one episode. Do not add `--episode-limit 1` solely to reclassify these deadline completions: the shared scorer's current eligibility check for that override expects a death/win endpoint. The game evaluator itself stops at the first native death and the one-episode endpoint assessment rejects multi-episode aggregation. Original V8 rubric/spec/score files remain intact; new assessments are appended with `retroactive.frozen_rubric_id`.

The four completed historical Trials rescore to **9/18/0/0** for DeepSeek frozen/live and Jev frozen/live, respectively, versus **12/24/0/0** under V8. See the dated V9 validation record for evidence counts and the assessment provenance. These are different rubrics, not a change to what the models did.

**Review status:** this is a candidate, not an approved formal-run rubric. Approximately two-hour ordinary-player reachability still needs explicit supporting validation and core-maintainer review. The five-stage setup is retained, but observed model calibration alone does not prove that criterion. New Opus 5.5 and GPT-6-Astra Trials remain Live-only, high effort, one life and 10,800 seconds, using their separate credentials. Their formal start also requires the shared request-failure policy and native smoke validation; API connectivity alone is insufficient. V9's historical cutoff does not yet implement the new timeout-extension accounting. No new-model Trial is launched by the scoring code.

## V8 release cohorts

The custom rally keeps the language-model budget of 10,800 seconds and Jev budget of 3,600 seconds in both modes, without an attempt limit. Automatic recovery remains within the current episode; existing native terminal handling is unchanged.

The V8 rubric already meets the 10 x 10 rule: 100 one-point milestones total 100, exceeding the minimum ten milestones while keeping each below the ten-point maximum. Its verified forward route coverage and ordered native finishes measure progress toward completing the five-stage rally. The rubric, trial specs and owner-approved difficulty baseline remain unchanged.

The active [Trial catalog](../../../benchmarks/trials/art-of-rally/) contains four specs sharing the [V8 integer rubric](../../../benchmarks/rubrics/art-of-rally/five-stage-integer-v8.json) and `art-of-rally-controls-v8` input profile:

| Spec filename | Model | Budget | Mode | Completed score |
| --- | --- | ---: | --- | ---: |
| `jev-five-stage-integer-v8-frozen-1h.json` | `jev-1-14` | 3600 s | frozen, 1 s step | 0/100 |
| `jev-five-stage-integer-v8-live-1h.json` | `jev-1-14` | 3600 s | live | 0/100 |
| `deepseek-five-stage-integer-v8-frozen-3h.json` | `deepseek-v41-flash-thinking` | 10800 s | frozen, 1 s step | 12/100 |
| `deepseek-five-stage-integer-v8-live-3h.json` | `deepseek-v41-flash-thinking` | 10800 s | live | 24/100 |

These results completed by 2026-10-29. They use native rendering and model capture at **1280x720**, software rendering, eight CPUs and 6 GiB memory. DeepSeek uses the shared OpenAI-compatible transport with thinking enabled and `reasoning_effort: high`; Jev uses the shared native typed-choice transport. Independent Trials start with empty context.

These remain historical 0.7.4-based custom-image Trials with their original assessments, model and evaluator attribution; this migration does not relabel them as new 0.7.6 runs. The compact publication retains non-media evidence; complete screenshots and videos remain in the original local exports.

The [dated results](VALIDATION.md) preserve Trial IDs, image/evaluator differences and incomplete attempts. Final live completed the first three stages and ended during Stage 4; completing a time budget does not mean finishing the rally. The 12-point frozen result supplies 720p thinking-model calibration. These selected completions, with disclosed restarts, do not establish a statistical model ranking.

## Credentials and preparation

Set credentials in the ignored project-root `.env`:

```dotenv
DEEPSEEK_API_KEY=your_deepseek_key
TYPESAFE_API_KEY=your_typesafe_key
```

Use plain values without shell `export` or surrounding quotes, preserving unrelated entries. The CLI loads `.env`; exported environment variables take precedence. `env-trial` forwards only the selected model's credential variable. Never put keys in Trial specs or exported evidence.

Use the official Steam client and the researcher's licensed installation. Back up personal saves and obtain the owner's authorization before disabling Steam Cloud. Game assets, credentials, loader binaries and personal deployment scripts stay outside source commits.

Capture a new snapshot instead of editing or retagging archived V7 state.

For publishing an existing V8 snapshot, its save archive may contain only `customrally`, `SaveGame.json`, `career`, `prefs`, `preparation.json` and the unchanged `manifest.json`. Keep the original loader files and both menu-reference images in a separate runtime directory, retaining their original relative paths. These images are required for startup recognition. This is a storage split, not a newly prepared or sanitized starting state.

Set `ART_OF_RALLY_SNAPSHOT_RUNTIME=/path/to/runtime` for a host run, or place the runtime directory beside the extracted snapshot with `.runtime` appended to the snapshot directory name. Container images can install the same files at `/opt/gamecua/art-of-rally/snapshot-runtime/<snapshot_hash>/`; no shared harness change or additional model input is required. The V1 runtime companion is in `snapshots/art-of-rally/v8-five-stage-720p-start-split-v1/runtime/`. Complete legacy snapshots remain supported and never fall back to external files when their own files are corrupted.

The owner-approved baseline uses Group 2 the esky v1 (`Car_Escort_V1`, livery 1), normal AI, automatic transmission, stability assist 100%, counter-steer 160%, ABS 50%, keyboard steering/brake/throttle sensitivity 50% and zero deadzones:

| Stage | Native scene ID | Direction | Conditions |
| --- | --- | --- | --- |
| Noormarkku | 9 | Reverse | Rain |
| Palus | 11 | Forward | Morning, dry |
| Kairila | 13 | Forward | Morning, dry |
| Lassila | 12 | Forward | Afternoon, dry |
| Lamppi | 10 | Forward | Morning, dry |

Effective CUSTOM damage is **0 (disabled)**. The owner chose to preserve the actual V7 vehicle, assists and environment to evaluate route completion under discrete keyboard control. Native readback confirmed damage is disabled; the earlier medium-damage description was a menu-default mismatch. Preserve the absent damage preference and its effective behavior. This is an approved lower-difficulty baseline.

## Inputs, timing and episode lifecycle

XTest supplies keyboard input with a visible cursor. The shared profile has fifteen nonempty choices: W throttle, S brake/reverse, A/D steering, Space handbrake, declared combinations and Return to confirm. It has no empty wait choice. Return can be ineffective during driving. Language models receive the same factual controls but retain the shared free-action interface. In-race pause, manual recovery and restart controls are disabled; automatic recovery and result navigation remain available. Rubric goals and native evaluator state are hidden during play; only the separate pre-run interview may describe the rubric.

Live decisions leave the game running. Frozen driving applies input, advances the requested native simulation interval and then pauses for the next decision. A short input releases within the one-second step; the remainder runs without held input. `cohort_step.NativeStepAdapter` and the native pause bridge measure native time independently of host/API latency. Known loading/results states use an owned, identity-checked process stop through `cohort_pause.CohortPause`. Unknown states or invalid acknowledgements fail. Cancellation and transition waits remain within the original Trial deadline; uncertain actions are never replayed.

Automatic off-track recovery stays in the same episode and grants no skipped route credit. Native terminal damage, retirement or an attributed in-stage restart latches death and stops further credit. DeepSeek restarts within its original budget with bounded, preserved same-model summarized context; Jev ends with `death_without_memory`. Five ordered native finishes latch victory independently of the numeric score. The shared `trials.py` owns this lifecycle.

## Scoring and native evidence

For each attempt, stage points are `floor(16 * verified_unique_segments / eligible_segments) + 4 * verified_native_finish`. Each stage retains the maximum whole-attempt total, up to 20 points; five stages total at most 100. Route and finish components from different attempts are never combined. Twenty nested one-point predicates per stage implement this with the shared milestone scorer. Every later stage requires all preceding native finishes in the same episode, with a fresh countdown and matching route identity; earning 20 points is not the prerequisite for advancing.

A segment earns coverage only after both endpoint planes are crossed forward with continuous traversal inside the frozen waypoint corridor. Validation uses native rigid-body physics samples, bounded interpolation, at most 0.05 seconds between samples and a 100 m/s displacement limit. The corridor allows 2 m lateral and 2 m height deviation. Ambiguous overlaps and degenerate links earn no credit. Recovery clears partial traversal, repeats count once, and backward driving cannot fill a gap. These bounds do not prove wheel contact or the road boundary on every bend, slope or airborne path.

Finish credit requires an attributable accepted player finish gate and valid non-retired official result. Stage-over status, a model claim or reaching the stage timer cap alone is insufficient. Current V8 evaluator revision `art-of-rally-integer-coverage-6` preserves two narrowly attributed cap cases: automatic recovery may add five seconds and one penalty before the next timer update clamps to 3599; an official 3599-second / 3599000-millisecond finish is accepted only with the immediately preceding matching `OnStageOver`. Ownership, stage order, position/physics continuity, damage and recovery checks still apply. Raw values and historical V5-V7 behavior are unchanged. The capped, penalty-bearing stage clock is separate from the Trial budget.

The collector publishes hash-linked `native_chunk` audit records and compressed, self-contained `save` proofs when points, stage completion or terminal outcome changes. The evaluator replays raw native evidence to derive predicates; numeric projections and mutable accepted-record journals are not scoring authority. Ordinary unchanged-score polls process new rows only; proof publication and final replay still cost time proportional to the preserved prefix. Persistence failures interrupt without replaying uncertain actions.

Release 0.7.4 uses the shared Trial, transport, schema-1 rubric, `score-trial` and export interfaces. Evaluator hashes are provenance, not a source-hash scoring gate. New assessments are appended; historical assessments retain their original model, image and evaluator attribution. Mutable native process output stays outside exported Trial evidence.

## V8 preparation and qualification

Each independent Trial uses a new evaluation environment.

Current limitations remain: measured one-second driving checks do not establish exact loading/results/countdown timing; geometric bounds need broader native qualification; all five finishes and every native terminal path have not been demonstrated. The 640p calibration also recorded host/native clock disagreement. The final cohorts use different immutable images after versioned clock and cap fixes, as disclosed in VALIDATION. Completed calibration and Trials do not remove these limits.

## Reproducing and publishing a campaign

1. Freeze a clean snapshot, owner-approved settings/reason, reviewed delivery record, configurations and immutable environment. Preserve known limitations and original image attribution.
2. Run short, comparison-ineligible checks with both models and both modes. Check inputs, ineffective Return selections, model transport, interview separation and lifecycle behavior.
3. Calibrate the thinking model against the approximately 40/100 target. A final run can supply calibration when its configuration is the chosen final version. The historical non-thinking V7 score cannot substitute.
4. Execute through the canonical CLI. Pass `--seconds 10800` or `--seconds 3600` to `env-trial`; its shared default is 90 seconds. Score/export through the shared workflow. Preserve interrupted attempts and declare independent repeats; never refund recovery time or replay uncertain actions.
5. Report scores, interviews, failures and protocol/image differences. Keep trial results out of `main`; the records of GameCUA V1 are on the `v1-official-exp` branch.

## Historical compatibility and retained artifacts

Retired V1/V2/V5/V6/V7 launch instructions are omitted from this guide. Their preserved Trials keep their own specs, rubrics and immutable assessments. V8 still imports earlier preparation, geometry, pause and evidence modules; filenames containing `v6`, `v7` or `development` do not make them unused.

The historical V7 non-thinking `deepseek-flash` baseline completed a three-hour budget with 17/100, native 640x360 rendering, 1280x720 capture and nominal one-second frozen steps. It remains comparison-ineligible and separate from V8 calibration. See the [dated baseline](VALIDATION.md).

The [local cleanup record](VALIDATION.md) identifies superseded raw bundles removed at the owner's request. All four final Trials and complete exports, calibration/settings/timing evidence, required snapshots and r4/r7 cap-regression traces remain in ignored local storage. Failure history is disclosed; retained evidence and scores were not rewritten.
