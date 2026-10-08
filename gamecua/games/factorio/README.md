# Factorio

Experimental integration of licensed Linux Factorio 2.0/2.1 base-game freeplay, singleplayer on Nauvis. The ending is the first native rocket launch. The catalog remains `configured` until the acceptance and calibration runs are complete.

Factorio is `realtime`: production, pollution, enemies and research advance while the model decides. `live` leaves that clock running. `frozen_steps` uses the shared `ProcessPause` to stop all threads of the verified native game process with a pidfd, then resumes it for a nominal one-second host-time step per action. The actual simulation advance can differ from that host-time interval. Model decision time still consumes the same wall-clock budget. Steam and the observer run separately. Pause acceptance must confirm stationary native ticks and resumed ticks in the actual game.

## One-life audit and bootstrap-v4

The current offline rescore rubric is `factorio-bootstrap-v4`. It has 100 distinct native targets, each worth one point. The score equals the number of reached targets. Maintainer review of this rubric is pending; do not start a new model run under it before approval.

All 100 targets are progress points. The chosen ratio is 100 progress / 0 collection. This uses the same quantitative evidence available in every valid historical cell. It avoids guessing inventory, building or recipe state from screenshots. Five families have 16 targets each: iron ore produced, iron plates produced, copper plates produced, gears produced, and iron products finished by newly player-built furnaces. Their thresholds are 1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100, 150, 250, 500 and 1000. Red-science consumption has 20 targets: 1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50, 60, 75, 90, 100, 125, 150, 175 and 200.

Each target is a different baseline-relative native counter threshold. Production reads `produced.iron-ore`, `produced.iron-plate`, `produced.copper-plate` or `produced.iron-gear-wheel`; new-furnace production reads `automated_iron`; research consumption reads `consumed.automation-science-pack`. The rubric descriptions include these exact fields. Each target is awarded once. Higher thresholds require additional production; they are correlated progress tiers, not independent samples. Furnace credit requires player-built furnace provenance and is distinct from force-wide plate production. Research credit requires native consumption, not science crafting or inventory possession.

The scope is early factory supply and red-science research. It omits oil, blue science, Rocket silo research and the ending. The ceilings are intended for approximately two hours of ordinary early-game play, including the fourfold research cost of the frozen Death world marathon start. This is a design bound, not a measured two-hour human completion claim or statistical calibration. Maintainer review must assess reachability and weighting before any new run. A full bootstrap score is not a rocket win; the existing native victory detector is unchanged.

Version-2 native telemetry contains every required field. The collector and historical evidence schema are unchanged. Version-1 pilot telemetry does not support this complete rubric and must not be presented as a v4 zero. All formal cells audited here use version 2. Images before 0.7.0 are void for this migration; preserve their files without rescoring.

For a multi-life historical language-model Trial whose first life ended in native death within three hours, run:

```bash
python -m gamecua.cli score-trial \
  --run-dir /path/to/isolated/restored/trial \
  --rubric benchmarks/rubrics/factorio/bootstrap-v4.json \
  --episode-limit 1
```

For a Trial already alive for its full three-hour budget, omit `--episode-limit 1`. The current shared scorer does not treat a deadline as coverage of an explicit episode-limit override. Check the actual first-life duration and outcome in the audit; do not infer eligibility from a score alone. Append new assessments in isolated copies and publish only the appended results. Verify scoring inputs against the original bundle index before and after scoring. Keep frozen specs, old scores and original evidence unchanged.

The new `deepseek-one-life-3h-{live,frozen}-v4.json` specs declare one life, 10,800 seconds and fresh context. They are review artifacts, not authorization to launch. Their model id preserves the existing DeepSeek configuration; new execution still requires the provider configuration and shared failure-policy readiness. Do not silently change an existing Trial's provider, generation settings, save or session. Jev specs and scores remain unchanged for this issue.

Interrupted cells remain incomplete. An earlier autosave cannot substitute for an exact stop-time save. If exact native state and session recovery cannot be established, prepare a per-point timeline reconstruction and obtain the owner's explicit acceptance before uploading it. A preserved subtotal is not a completed comparable model result.

## Installation and fixed start

Use the official Linux64 full or Steam build. Demo and headless builds are rejected. Steam App ID 427520 requires the officially installed build, an authenticated official client and per-game Cloud disabled with the account owner's authorization. Keep account state and licensed files in private storage.

The delivery start is base-only freeplay on seed 12345 using the native `death-world-marathon` preset. This is the hardest combined named preset; custom difficulty sliders have no finite maximum. The native preset uses a fourfold technology price, increased enemy bases, a smaller starting area and its original pollution/evolution settings. Record the actual installed preset and save derivation in `preparation.json`. Do not substitute the historical standard-map snapshot or operator fixtures.

Create the map with the licensed game's `--create`, `--map-gen-seed 12345` and `--preset death-world-marathon` options. Load it through the graphical client, dismiss only the opening cutscene and welcome, and save before movement, mining, crafting, construction or research. Freeze that native save with:

```bash
python -m gamecua.games.factorio.setup \
  --installation /path/to/licensed/factorio \
  --source /path/to/private/saves/start.zip \
  --seed 12345 \
  --preset death-world-marathon \
  --procedure "Actual version, native death-world-marathon preset and preparation actions" \
  --output /path/to/private/factorio-snapshot
```

Publish the final prepared save as a snapshot directory, `snapshots/factorio/<snapshot-name>/`. Include the deterministic `snapshot.tar.gz`, its unchanged `snapshot.manifest.json`, and a README with the preparer, map seed, preset, procedure, recorded snapshot hash and consuming experiment folders. A changed start gets a new directory.

Each episode restores it into a new native profile. Exactly one normal-speed player and only the base game plus the read-only evidence mod are allowed. Space Age, quality, elevated rails, console commands and cheat mode are excluded.

## Controls and model forms

Both models use `factorio-kbm-v1`, at `benchmarks/inputs/factorio/kbm-v1.json`. The language model receives its controls reference and retains the shared free mouse/keyboard action interface. Jev chooses one ordinary input per step and locates mouse targets with native Box questions. The profile has no empty input. It contains movement, pointer movement, clicks, dragging, inventory, research, rotation, quickbar slots, zoom and native interaction keys.

Mining is rebound to J in every isolated profile. Point at an object, then hold J. This lets Jev hold mining through its ordinary keyboard input. The same binding applies to the language model. It does not add a game action, target selector or strategy. A short right click can still split inventory stacks. Verify the binding in the native game before delivery.

The factual interview brief is in `game.json`. The shared interview runs separately before the clock; it may describe the rubric. Gameplay context contains screenshots, ordinary controls and the model's own history, without evaluator telemetry or goals.

## Historical rocket-v3 rubric

`factorio-rocket-v3` is an uncalibrated 100-point rubric with ten milestones, worth 10 points each:

- Produce at least 10 new iron plates.
- Produce at least 10 new copper plates.
- Produce at least 10 new iron gear wheels.
- Complete at least five iron plate products in total in furnaces built by the player during the episode.
- Complete Automation research that was incomplete at the episode baseline.
- Consume an automation science pack in powered lab research after that baseline.
- Consume a logistic science pack in research after that baseline.
- Consume a chemical science pack in research after that baseline.
- Complete Rocket silo research that was incomplete at that baseline.
- Launch a new rocket in base-game freeplay after that baseline.

Iron and copper plates and gears supply the mandatory factory, science and rocket chains. Productive new furnaces establish iron supply. Automation unlocks assembling machines and lies on the logistic-science research route. Science consumption, Rocket silo research and the launch measure the remaining rocket route. Optional combat, exploration and item stockpiles earn nothing. The early thresholds come from `factorio-production-pilot-v1`; the five research/rocket predicates from `factorio-rocket-v2` keep their original meanings. The older rubrics remain unchanged.

All predicates subtract their own episode baseline, and native identity changes or counter regressions are rejected. Furnace products are summed across newly built furnaces; they do not require five products from one furnace. Science pack production alone earns no science-consumption points. The launch count comes from the native force. Research completion or a model's victory claim does not count as a launch. A milestone earns points once per Trial, even when more than one episode reaches it.

The collector emits version-2 samples, which already preserve every v3 predicate. The evaluator still reads version-1 samples for the historical `factorio-production-pilot-v1` rubric and preserves its original attribution. Its 180-second non-thinking functional run is not thinking-model calibration.

## Historical 0.7.6 delivery trials

All four specifications use the same input profile and rocket rubric:

- `deepseek-thinking-3h-live.json`: official `deepseek-flash`, thinking enabled, reasoning effort high, 10,800 seconds.
- `deepseek-thinking-3h-frozen.json`: the same model and budget, nominal one-second host-time frozen steps.
- `jev-1h-live.json`: native TypeSafe `jev-1.14.0`, 3,600 seconds.
- `jev-1h-frozen.json`: the same Jev model and budget, nominal one-second host-time frozen steps.

Set `DEEPSEEK_API_KEY` and `TYPESAFE_API_KEY` only in environment variables or ignored local configuration. The game subprocess excludes provider keys. A licensed Steam home is leased to one environment; run its cells sequentially. Create a fresh evaluation environment for each cell, with the same read-only installation and snapshot. Use the canonical `env-trial` command with the full budget, then `score-trial` and `export-trial`. Run all new formal Trials on harness 0.7.6. Keep formal evidence out of `main`.

The historical specs used 3 h language-model and 1 h Jev budgets without an episode limit. In that protocol the benchmark restored the fixed start after character death. Death started a new episode within the language-model Trial, with bounded same-model knowledge and the original deadline. The one-life rule above supersedes this language-model behavior for new runs. Jev ends at its first native death. Recovery requires the same process, native stream and screenshot; it never replays uncertain actions or refunds time. Preserve incomplete experiments and report failures separately from scores. Record model interview answers with the delivery results. Follow the shared Jev ineffective-loop rule if it applies.

See [VALIDATION.md](VALIDATION.md) for dated evidence and acceptance limits.

## Completed 0.7.5 delivery

The 2026-10-30/31 delivery has one independent comparison-eligible Trial in each required cell, all with score 0/100. Both thinking-high DeepSeek Trials completed their full three-hour budgets. Jev live and frozen stopped at 933.272 and 359.471 seconds under the current README's permitted ineffective-loop rule, with canonical `manual_stop: true`; their configured maximum budgets remain one hour. The separate initial TypeSafe regional failure is excluded from model results.

Every canonical export is losslessly archived in sub-limit parts, with restoration instructions and readable scores/interviews. Use the matching 0.7.5 source commit specified by the summary for offline scoring, rather than older code on the data branch. The source snapshot bytes remain unchanged.

These runs establish the delivered configuration and native early-production behavior. They do not establish rocket completion, positive higher-tier native evaluator acceptance or statistical weight calibration. These are historical v2 scores; the 0.7.6 retroactive assessments use v3 and preserve the original model attribution and interviews.

## 0.7.6 migration and result reuse

The four delivery specs now select `factorio-rocket-v3`. No new model calls are needed for this migration. Use harness 0.7.6 to append an assessment from each restored canonical export:

```bash
python -m gamecua.cli score-trial \
  --run-dir /path/to/restored/cell \
  --rubric benchmarks/rubrics/factorio/rocket-v3.json
```

Omit `--episode-limit`: all original episodes belong to the time-budget Trial. Preserve the frozen `rubric.json`, original scores, model specs and interview answers. The historical interviews described v2 and are not new v3 predictions.

All four remain comparison-eligible. The new score files and verification records sit in each original cell's `rescore-076/` folder next to its unchanged multipart bundle. Each score appends a `retroactive` block. Every scoring input matches its published bundle-index SHA-256. Reassessments ran on isolated copies and left the original scores and scoring inputs unchanged.

DeepSeek live earned productive-furnace, iron-plate and copper-plate milestones. Frozen earned productive-furnace and iron-plate milestones. Neither reached science consumption, Automation research or rocket progress. Each cell is one independent Trial; awards can come from different episodes within that Trial. Jev retains the historical ineffective-loop stops and their actual durations. These results meet the requested at-most-40 difficulty target but do not statistically calibrate the rubric.

## Optional HTTP 413 recovery pause

Selected provider-recovery runs set `GAMECUA_FACTORIO_PAUSE_ON_413=1`. The Factorio backend then owns an authenticated private Unix pause channel under `/state`. An operational provider relay can request a pause after an upstream HTTP 413 and confirm recovery before returning a successful model response. The shared model client, Trial workflow, input profile and native scoring stay unchanged.

The pause uses the existing pidfd identity checks on the verified native Factorio process. It belongs to one pending request digest. Repeated errors do not create another pause or episode. Recovery releases only a pause that this mechanism acquired; it leaves an existing frozen-step pause intact. Backend shutdown releases its owned pause and closes its private channel. Channel capabilities stay outside portable evidence.

All retries and error pauses consume the original Trial wall-clock budget. They do not replay game inputs, reset the Trial or refund time. The operational relay reports persistent transient 413 responses as retryable gateway failures to the existing shared retry policy. That policy still has its original limits. If pause or resume cannot be confirmed during an active Trial, the request fails closed.

Record this as the `native_game_pause_during_http413_recovery_v1` protocol variant. Normal live inference remains realtime; only provider-error recovery can stop native simulation. Disclose actual error-pause intervals when comparing with uninterrupted live runs. A failed or incomplete cell remains separate from model scores even when the campaign continues to its next independent cell.

## Additional 0.7.6 model delivery: 2026-11-03

Every configured budget was 10,800 seconds without an episode limit. Opus and Grok completed both cells with canonical scores of 0/100. The two GPT cells ended early with provider failures, remain incomplete and are excluded from score comparisons. Their canonical subtotals are not completed model zeros. Original exports and earlier interrupted records remain unchanged.

The live Trial earned the copper-plate, productive-furnace and iron-plate milestones. No rocket launch or win was verified. Both started in new evaluation environments with empty initial context and used the same snapshot, input profile and v3 rubric. Episodes after death remain parts of their original Trial, not additional samples.

The follow-up protocol is `factorio-gpt-bounded-retry-v1`. It uses the supported canonical Trial agent factory to configure the unchanged shared VisionAgent and RetryPolicy: at most 96 attempts per request, a 360-second request bound, a 10,800-second retry budget clipped by the original Trial deadline, and exponential backoff starting at five seconds with a 120-second base cap. Shared jitter, Retry-After and nonretryable classifications remain in effect. The private opaque relay has a 350-second total request bound. Interview retry settings remain the shared defaults. This is a separate cohort, not a retroactive change to the original campaign or shared core. Every wait consumes the original wall-clock budget; no time or quota was refunded.

GPT requested high reasoning, JSON output and `max_tokens: 12288`. Opus and Grok configured only `max_tokens: 12288` and otherwise used provider defaults. In particular, Grok high reasoning was not explicitly requested; the corrected original summary supersedes the earlier monitoring description. Preserve the exported model specifications and returned-model attribution instead of inferring undocumented provider defaults.

All six completed new exports passed canonical eligibility checks, credential scans, lossless multipart round-trip verification and published-blob checks. A completed input record establishes that the input was dispatched, not that it reached the model's intended target. The preserved native counters support the appended scores, but these single-Trial cells and different recovery protocols do not establish a general model ranking. No retrospective repair or replacement Trial was run.
