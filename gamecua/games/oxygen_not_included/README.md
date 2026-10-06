# Oxygen Not Included

## Running start for new episodes (2026-11-14)

New episodes record `simulation_start: running_before_first_decision_v1` in setup metadata.
ONI normally pauses after loading. The first backend poll, after the canonical budget starts
and before the first model observation, recognizes the native pause button and sends one
ordinary Space input only when it confirms a paused state. It requires a recognized running
indicator within five seconds. Unknown states, cancellation or an uncertain input fail closed;
the input is never retried. An already running screen receives no startup input.

The transition and its before/after screenshots are preserved in the episode directory.
Preparation and a pre-run start gate remain natively paused, avoiding uncharged simulation
while waiting for permission to start. In Frozen mode the process is thawed only for this
bounded startup transition and then frozen again before model inference. This transition
consumes the normal wall-clock budget; it is not a model action or an extra allowance.
The native speed setting is retained. During play, model-controlled native pause remains
available and is never automatically cleared by subsequent polls or recovery.

Recovery does not repeat startup. A new-policy episode without a completed startup receipt
cannot recover automatically. Historical episodes without this policy retain their original
behavior and evidence. Comparisons must disclose the changed starting condition; historical
scores are not rewritten. Scoring still requires preserved native evidence, so this change
does not convert a missing-save assessment from null to zero.

## Owner-approved no-mod fifty-item rubric (v7, 2026-11-10)

`oni-development-v7` implements the owner's approved replacement set: 20 foundation, 20 intermediate and 10 advanced questions, each worth two points. The 34 previously supported conditions are unchanged; the 16 unavailable v6 questions are replaced with native facility counts, inventory, stored energy, crop diversity and conservative manufacturing totals. V1-v6 remain available without rewriting their contracts or historical scores. V6 remains an incomplete diagnostic draft.

All fifty v7 predicates have implementations. A complete native assessment can return a score out of 100 through the canonical endpoint scorer; missing baseline/evidence, invalid native records or unresolvable initial-generator attribution cannot become a valid zero. Type-level coal/new-generator production requires no relevant initial generators. Incomplete Trials remain excluded by the shared completion and eligibility checks. The endpoint validates hashes, episode-local paths, identity, settings and monotonic clocks, and stops at the first preserved native death or the three-hour limit. Positive milestones are retained across qualifying saves. Unobserved milestones receive no points; absence does not establish that an action never occurred.

Construction means a net increase in completed prefab counts, not connected or operational equipment. Combined conditions are independent: the new grill need not be the source of colony-wide manufactured food; pipe water need not belong to the reservoir; the cultivated Bristle Blossoms need not occupy the newly built hydroponic tiles. Metal inventory has no manufacturing-provenance requirement. Smart-battery questions measure stored charge, not automation. These limitations are explicit in the owner-approved replacement wording.

The `oni-astra-development-v7-live` Trial specification uses one life, 10800 seconds, fresh context and live execution. It retains its original charged failure policy. The owner explicitly accepted the fifty-item selection and authorized implementation of the new provider-failure policy on 2026-11-11; that selection is no longer an owner approval blocker. No mod, event collector, debug operation or altered snapshot is introduced.

Implementation coverage is not gameplay calibration. The rubric remains `calibrated: false`; real positive coverage of all fifty and two-hour reachability have not been demonstrated. Exactly fifty follows the owner's explicit selection; it is not a claim that every textual requirement of the protocol or maintainer review has been satisfied.

Existing native13 runtime images predate v7. Build and validate a runtime image from the approved v7 source before any subsequent authorized model run; offline source tests do not constitute a new image smoke test.

## Opt-in provider recovery (2026-11-11)

ONI Trials may select `provider_failure_policy: "freeze_retry_timeout_credit"`, the shared policy that the core implements (see the root README, "Provider failures"). Existing specifications keep `charged_retry_then_interrupt`; Jev and external agents cannot select it.

This backend only has to provide the native pause: `freeze()` and `thaw()` use the shared identity-checked `ProcessPause`, so a failed request freezes the native process (live mode too) until a request succeeds, and a real-process test covers it. Timeouts, credits, backoff and the operator pause are the core policy's; the ONI scorer counts evidence up to `time_allowance()`.

`events.jsonl`, `summary.json` and `trial.json` carry the timestamps, timeout credits, frozen time and operator pauses. Resume still requires canonical exact-state recovery and rejects uncertain actions; it retains the episode and context.

The ONI v7 endpoint admits evidence through the original cap plus the recorded timeout-credit ledger only for this explicit new policy. Historical caps remain unchanged. Model/provider identity and high effort must be frozen into the new Trial's model specification. No credential belongs in a specification or publication. The requested next formal cell remains Live, one life and 10800 base seconds; this implementation does not start it or create another cohort.

## Owner-selected fifty-item assessment draft (2026-11-10)

`oni-development-v6` freezes the owner's selected 20 foundation, 20 intermediate and 10 advanced questions at two points each. Original candidate 61 is any supported newly built generator producing 100 kJ. No deodorizer question is included. V1-v5 contracts and original results remain unchanged, including the v5 positive-buffer steam criterion.

This is **not a completed or approved benchmark rubric**. The native implementation supports 34 predicates; 16 remain unavailable. The endpoint assessment preserves confirmed awards and reports a confirmed subtotal, but returns no final score and is not scoreable or comparison eligible. `unavailable` means missing verified evidence support; `not_observed` means no qualifying preserved positive evidence, not a proven gameplay failure. The backend rejects new v6 play before touching the game process. No executable v6 model trial is supplied until evidence coverage and maintainer review are complete.

Assessment verifies the preserved baseline and evidence hashes, colony/settings identity, native clock order, a maximum 10,800-second cutoff, and stops at the first preserved native terminal event. Use a disposable copy of a historical Trial with the canonical `score-trial --rubric benchmarks/rubrics/oxygen-not-included/development-v6.json` command; select `--episode-limit 1` only when the first of multiple episodes ended in verified death. All appended v6 assessments are incomplete diagnostic assessments, never replacement historical scores.

Construction uses completed-prefab net additions. Production uses native reports and conservative ration counters; energy use excludes battery losses. Research uses the pinned base-game research table. Three cultivated crops, new battery charge, pipe-water increase and refined-resource stock use native evidence separately from manufacturing provenance. Coal and any-generator output use strictly decoded cumulative generator-type counters **only when no relevant generators existed at setup**. Otherwise attribution is unavailable. This new v6 use does not change the v5 steam predicate or its diagnostic-only counter decision.

The 16 missing criteria concern electrolyzer/grill production attribution, chilled food inside a new refrigerator, sieve throughput, manufactured metal/refinery output, completed lavatory use, automation connection and switching histories, harvest and irrigation histories, suit readiness, groomed ranch membership, transformer downstream consumption and per-food manufacturing totals. Work starts, current logic state, global totals and inventory are insufficient substitutes. These require additional verified preserved native evidence; no synthetic events, save editing, debug mode or guessed awards are accepted.

The protocol requests more than 50 items; the owner selected exactly 50. Maintainer resolution is still required. Related threshold rewards (production, research and food) also require independence/calibration review. Ordinary-play positive acceptance and two-hour reachability are not established for this set. Do not start new model runs or publish reconstructed scores as accepted results on the strength of this draft.

Experimental integration of the native Linux Oxygen Not Included Steam build 744825 (save version 7.38, base game or Spaced Out, English 1280x720 UI) from a cycle-zero, three-duplicant standard Survival save. Roster status: `experimental` (catalog status `configured`). Timing is `realtime`; native pause is available to the agent through ordinary keyboard input. Live execution keeps running during inference; frozen execution suspends the process between actions. Inference, pauses and render settling consume wall time. Milestone points require native saves, so unsaved progress earns no credit. All four base-game live/frozen cohort outcomes are recorded below. Historical native positive controls for the original five development stages are verified separately from model results; they do not validate every v5 extension.

## Setup and snapshot

- Requires the licensed Steam installation (App ID 457140) and the authenticated official client. Workshop subscriptions may install, but enabled mods are rejected. Personal save directories are never copied into an episode.
- Each episode copies the prepared save into a private HOME. The executable is copied unchanged (Unity writes `unity.lock` beside it); game assets stay linked to the read-only installation. The prepared save determines the DLC mode; optional DLC is disabled in the profile.
- Preparation requires standard Survival, disabled fast workers and local-only saves. Evidence must preserve the exact initial difficulty and world settings (base-game Durability is `Indestructible`, Spaced Out `Default`). Preparation UI recognition covers only observed English cues and fails after a bounded timeout otherwise.
- Prepare a snapshot from an operator-created save outside personal storage:

```bash
python -m gamecua.games.oxygen_not_included.setup \
  --source /path/to/operator-cycle-zero.sav --output /private/oni-snapshot
```

Create a development Steam environment, then a fresh evaluation environment per independent Trial:

```bash
python -m gamecua.cli env-build
python -m gamecua.cli env-create --output /private/oni-evaluation \
  --installation /path/to/steamapps/common/OxygenNotIncluded \
  --snapshot /private/oni-snapshot --steam \
  --steam-environment /private/oni-steam --renderer software --cpus 8 --memory 10g
```

The 8 CPU / 10 GiB software-renderer settings were used for development, not established minimums.

## Current rubric: development-v5 (2026-11-08)

The owner approved 25 independent milestones worth 4 points each (100 total). The first ten retain the v4 predicates and numerical thresholds; cross-category prerequisites are removed. The scope remains owner-selected continuous colony development. This revision is not a claim that every item is necessary on every winning route, and maintainer acceptance or difficulty calibration of v5 is not claimed (`calibrated: false`). Existing v1-v4 rubric files, interviews, executions and published assessments are unchanged.

The owner refined the extension for auditable evidence: refined metal, plastic and steel use net inventory rather than manufacturing provenance; agriculture requires a planted edible crop rather than a completed harvest; water infrastructure requires a new liquid pump and water in liquid pipes; a new Super Computer replaces the proposed water-purification milestone. Electrical use is measured by actual consumer energy, excluding battery losses and generator overproduction. Starting a job is not proof of completion: native `Workable.numberOfUses` counts work starts and is not used for awards.

| # | Milestone | Native requirement | Points |
| --- | --- | --- | --- |
| 1 | `bed` | Complete at least one new bed after setup. Blueprints and initial buildings do not count. | 4 |
| 2 | `toilet` | Complete at least one new toilet of any supported native toilet type after setup. Handwashing is not required; blueprints and initial buildings do not count. | 4 |
| 3 | `generator` | Complete at least one new electricity-generating building of any supported native type after setup. Blueprints, initial buildings, batteries and debug devices do not count; production is assessed separately. | 4 |
| 4 | `oxygen_device` | Complete at least one new building that produces oxygen or polluted oxygen after setup, including the Sublimation Station. Blueprints, initial buildings, plants and gas storage or transport do not count; actual oxygen production is assessed separately. | 4 |
| 5 | `electricity` | Produce at least 10000 joules of new electricity after setup, established by native positive-production records. | 4 |
| 6 | `oxygen` | Produce at least 20 kilograms of new oxygen after setup, established by native positive-production records. | 4 |
| 7 | `food` | Produce at least 1000 kilocalories of new food after setup, established by native production records and conservative preserved manufacturing counters, not existing stock. | 4 |
| 8 | `research` | Complete at least one new technology after setup. | 4 |
| 9 | `expansion` | Complete at least three new technologies after setup, including at least one whose pinned native cost requires advanced research points. | 4 |
| 10 | `development` | Complete at least six new technologies after setup, including at least two whose pinned native costs require advanced research points. No waiting-cycle requirement applies. | 4 |
| 11 | `charged_battery` | Complete a new battery and preserve positive stored electrical energy in that battery. | 4 |
| 12 | `power_used` | Consume positive new electrical energy in native consumer reports. Battery charge loss and generator overproduction are excluded; a connected but unused device earns nothing. | 4 |
| 13 | `electricity_scaled` | Produce at least 100000 joules of new electricity after setup. | 4 |
| 14 | `oxygen_scaled` | Produce at least 200 kilograms of new oxygen after setup. Polluted oxygen does not count. | 4 |
| 15 | `crop_planted` | Establish at least one newly planted supported edible crop in a planting facility. A wild plant or an empty planter does not count. Harvest completion is not required. | 4 |
| 16 | `food_processing` | Produce a positive amount of new manufactured food, verified by preserved native ration production counters. Starting work, harvested raw food and existing stock do not count. | 4 |
| 17 | `food_scaled` | Produce at least 10000 kilocalories of new food after setup. | 4 |
| 18 | `piped_water` | Complete a new liquid pump and preserve more liquid water inside liquid conduits than at setup. Empty pipes and environmental pools do not count. This does not claim a particular pipe route or end-device consumption. | 4 |
| 19 | `advanced_station` | Complete at least one new Super Computer for advanced research. Blueprints and initial buildings do not count. | 4 |
| 20 | `refined_metal_stock` | Increase loose or stored supported refined-metal resource inventory by at least 100 kilograms over setup. Mining and production both count; natural solid tiles and construction materials embedded in buildings do not. | 4 |
| 21 | `plastic_stock` | Increase loose or stored plastic resource inventory by at least 100 kilograms over setup. Production provenance is not required; plastic embedded in buildings does not count. | 4 |
| 22 | `steel_stock` | Increase loose or stored steel resource inventory by at least 100 kilograms over setup. Production provenance is not required; steel embedded in buildings does not count. | 4 |
| 23 | `research_scaled` | Complete at least twelve new technologies, including at least four whose pinned native costs require advanced research points. | 4 |
| 24 | `steam_power` | Complete a new steam turbine and preserve positive energy in its native generator buffer, proving generation. Construction alone does not count; generation fully consumed before all saves may remain unverified. | 4 |
| 25 | `space_launch` | Newly earn the native base-game ReachedSpace colony achievement, verifying a rocket reached space. A launch order or a completed rocket alone does not count. | 4 |

Inventory means native resource objects, including stored resources and loose debris. Solid environmental tiles and materials embedded in buildings are excluded. The initial inventory is subtracted; acquired materials may come from mining or manufacture. Steel also belongs to refined-metal inventory. Edible crops currently supported are Mealwood, Bristle Blossom, Dusk Cap, Sleet Wheat and Nosh Sprout. Milestones are verified at preserved saves: transient battery charge, pipe contents, turbine output or consumed inventory can be missed between saves. These conservative observations do not establish continuous operation or self-sufficiency.

The extended reader uses native object identities and scalar fields, liquid-conduit serialization, electrical-consumer reports, ration production counters and the colony-local `ReachedSpace` achievement. It remains restricted to build 744825/save 7.38. The published initial save's extended baseline is independently decoded and bound to SHA-256 `69f9797471f6cfa1086e825b820dd9d4a729af0cbb43b207dc730f56b1336f35`; this supports append-only reassessment of old runs using that exact baseline. Other starting saves require newly recorded `extended_development` setup metadata. Unsupported or malformed native evidence fails closed.

Game-scoped v5 Trial specifications cover DeepSeek, Jev and Astra in live/frozen modes. They preserve standard charged wall-clock policy, the shared pointer-v3 input profile, 3 h language-model budgets and 1 h Jev budgets. The current owner authorizes only Astra execution. The private provider route and temporary outage-freeze policy are separate local configuration, not shared model or core edits. Old Astra v4 live completed at 80/100; the frozen worker was killed with exit -9 after 7466.330 effective seconds while awaiting quota. It is incomplete and must not be reported as a completed result or silently restarted. A 2026-11-08 minimal availability check still returned HTTP 429 with insufficient quota.

Historical completed runs may be canonically rescored in separate review copies where their native evidence suffices. Keep original scores and timing-policy attribution. Full local originals and recordings remain intact; publish compact evidence outside `main`, with retained native saves/JSON/initial-final screenshots/policy records and per-file omission hashes for media and SQLite. Compact copies require independent canonical rescore, credential scanning and remote hash verification. They are not complete visual evidence. Historical positive checks do not establish positive acceptance of all 25 v5 milestones. Native13 live/frozen no-model deployment checks pass. Appended v5 reassessments of the corrected historical campaign give DeepSeek 16/16 and Jev 0/0; Jev manual-stop exceptions and original execution/interview attribution remain unchanged. These are retrospective observations, not new model runs or universal calibration.

It contains 715 files (14,257,255 bytes) before the upload-status marker and discloses hashes and reasons for 1,348 omitted source files. Full originals and recordings remain local. Independent disposable-copy canonical rescoring with pinned source 62de53eea reproduces every original v4 field; current v5 rescoring also reproduces every reassessment field. Credential scanning passed, and independent GitHub API verification matches all 716 remote blobs including upload status. Original v4 interview and outage-freeze timing attribution remain disclosed. This is reduced review evidence, not complete visual evidence; no snapshot or original result was changed.

## Historical rubric: development-v4

It has four completed-building milestones, three production milestones and three research milestones, each worth 10 points. Standard Survival, the one-bed/one-toilet requirement without handwashing, production thresholds and 1/3/6-technology thresholds with advanced research remain unchanged. The owner specifically selected the two additional buildings and retained all three research thresholds. Historical v1/v2/v3 rubrics, Trial specifications, interviews and results remain frozen.

| Milestone | Native requirement since setup | Points |
| --- | --- | --- |
| Bed | At least one newly completed bed; no blueprints | 10 |
| Toilet | At least one newly completed toilet of any supported type; no handwashing requirement | 10 |
| Generator | At least one newly completed electricity-generating building of any supported type | 10 |
| Oxygen device | At least one newly completed oxygen- or polluted-oxygen-producing building | 10 |
| Electricity | Positive native production of at least 10 kJ electricity | 10 |
| Oxygen | Positive native production of at least 20 kg oxygen | 10 |
| Food | Positive native production of at least 1,000 kcal food | 10 |
| Research | At least one newly completed technology | 10 |
| Expansion | At least three newly completed technologies, including one requiring advanced research points | 10 |
| Deep development | At least six newly completed technologies, including two requiring advanced research points | 10 |

The four building milestones can be earned independently. Each production milestone requires the bed and toilet in the same episode; research requires all three production milestones, followed by expansion and deep development. Completed research may already exist when prerequisites are evidenced; no additional gameplay-order restriction or waiting period applies. The generator/oxygen-device milestones do not impose an additional prerequisite on production. These early facilities support rest, sanitation, power and oxygen, while research expands colony capabilities; the rubric measures owner-approved colony development, not a verified universal route to a game ending. Building completion alone does not prove operation or self-sufficiency. Initial buildings, production and research are excluded. Day-level positive production is counted once without adding nested contributor totals again. Earned points persist after death; restarts cannot combine prerequisites or duplicate awards.

The v4 owner revision broadens facility types without changing the other seven milestones. Toilets cover Outhouse, Lavatory and Wall Toilet. Electricity generators cover manual, coal, hydrogen, natural gas, petroleum, wood, solar (including the rocket module), steam turbines, peat and reef generators. Oxygen devices cover Oxygen Diffuser, Electrolyzer, Rust Deoxidizer, Algae Terrarium, Deodorizer and Sublimation Station. Polluted-oxygen devices qualify for the building milestone, but the separate 20 kg oxygen milestone still requires oxygen production under the unchanged native report. Batteries, gas storage/transport, debug generators, plants and creatures do not qualify. DLC-only identifiers do not enable DLC: the benchmark still requires its unchanged base-game snapshot, so those facilities are unavailable in the current scenario. The family definitions were checked against the pinned native assembly; proprietary native assets remain local.

Evaluator `oni-native-progress-8` additionally reads manufactured food from `RationTracker`, which the native client updates separately from `ReportManager.CaloriesCreated`. Its current/previous-cycle production frames are added once to the separate food report totals after subtracting overlapping baseline frames. This is a conservative lower bound on production evidenced by that save, not a reconstructed lifetime manufacturing total: older manufacturing expires from the native tracker. A qualifying preserved save retains its earned stage after that window rolls over, but manufacturing that expires before a qualifying save cannot be credited. Inventory changes, consumption and building presence do not substitute for production. The exact published cycle-zero snapshot has independently verified zero ration counters; other legacy baselines without ration metadata fail closed. Historical evaluator versions and scores remain preserved.

The base-game technology classification is pinned to build 744825's `TechTree_Generated` graph, native prerequisite-tier calculation and native point-cost table. For example, `AdvancedResearch` itself requires only basic points, while `Agriculture` requires advanced points. The native graph and proprietary assembly stay in private local storage.

### Historical survival rubric

`benchmarks/rubrics/oxygen-not-included/survival-v2.json` (`oni-survival-v2`, uncalibrated, 100 points). Each stage requires the previous one in the same episode and at least one living duplicant in the qualifying native save. Cycles are full cycles since episode setup including the initial fractional offset.

| Milestone | Requirement | Points | Cumulative |
| --- | --- | --- | --- |
| `survive-2` | Survive 2 cycles | 5 | 5 |
| `survive-4` | Survive 4 cycles | 10 | 15 |
| `survive-8` | Survive 8 cycles | 10 | 25 |
| `survive-16` | Survive 16 cycles | 15 | 40 |
| `survive-32` | Survive 32 cycles | 15 | 55 |
| `survive-64` | Survive 64 cycles | 20 | 75 |
| `survive-128` | Survive 128 cycles | 25 | 100 |

Cycle totals cannot be added across episodes. The high thresholds are not claimed reachable on the software renderer within three hours. `benchmarks/rubrics/oxygen-not-included/construction-pilot.json` (`oni-construction-pilot` v1, eight building mappings) is a historical rubric no current Trial spec references.

## Trial specs

The completed historical v1 cohort uses `deepseek-development-v1-live.json` and `deepseek-development-v1-frozen.json` (10,800 seconds each), plus `jev-development-v1-live.json` and `jev-development-v1-frozen.json` (3,600 seconds each). All four use `oni-development-v1` and `oni-pointer-v3`. Frozen execution uses a nominal one-second host interval plus the documented bounded presentation wait. All four cells used source revision `0cf2b33f373047aee83c38d4b01463ec414f4a3f` and source-built 0.7.5 image `sha256:a5dab2f327fae10a0981b45ca4d2339bd1fc55dbec560b323a4072e450c30bc8`. Their canonical assessments are scoreable and comparison eligible. Jev frozen ended through the documented manually reviewed ineffective-loop exception; it is not a full-hour run.

| Published cohort | Charged time | Score | Completion |
| --- | --- | --- | --- |

Each result directory includes unchanged canonical assessments and a lossless, hash-verified archive split into Git-compatible chunks. Follow its README to restore the original screenshots, actions, interview record, native evidence and recordings. Videos are window-only at 2 FPS without audio; preserved sampling gaps are disclosed in the delivery audit. These model results do not establish a positive example of all five scoring stages. Jev frozen stopped because of a manually observed ineffective loop; the experiment was closed to save tokens. Its package preserves the review basis and original action/frame hashes.

Start a current DeepSeek live cohort with its full budget:

```bash
python -m gamecua.cli env-trial --environment /private/oni-evaluation \
  --trial-spec benchmarks/trials/oxygen-not-included/deepseek-development-v2-live.json --seconds 10800
```

Choose the corresponding frozen or Jev specification listed above for the other cells; Jev uses `--seconds 3600`. A shorter integration check is not a full cohort. Each independent Trial needs a fresh evaluation environment and the same snapshot. All four use the shared `pure_image_no_rules` gameplay policy; rubric goals appear only in the separate pre-run interview.

Use the shared `score-trial` and `export-trial` commands after completion. `resume-trial` is only for verifiable recovery in the existing Trial: it accepts the same live native process, matching save hashes, an append-only native journal and the verified Steam session, without reloading or replaying actions. A second native save-load event within an episode fails the experiment, even when loading an autosave later than the initial snapshot. Set `DEEPSEEK_API_KEY` and `TYPESAFE_API_KEY` only in the environment or ignored `.env`.

The historical `deepseek-pilot.json` (`oni-deepseek-pilot`, model `deepseek-flash`, rubric `oni-survival-v2`) remains for attribution. It is not the current development cohort.

## Known limitations

- Native saves establish death when population and duplicant death monitors agree. If no death save exists, an immutable receipt can establish the game's explicit Colony Lost state together with its zero-population display. The receipt preserves the original window PNG, hashes, initial-save identity, native journal prefix identity and filtered native death events. Offline scoring rechecks the pixels; neither a model claim nor a count of death log lines suffices. This maps game-declared defeat (including incapacitation) to the shared `death` lifecycle event and awards no milestone points. The evaluator never forces a save; all development points still require preserved native saves.
- The save reader (`native.read_save`) is bounded: it does not decode simulation cells or arbitrary component payloads. Saves still being written are retried for at most five seconds.
- Preparation and unsaved-loss cues are specific to the pinned English UI at 1280x720. Occluded or unmatched loss cues do not establish a terminal event; native saves remain the fallback.
- Local GPU runs showed corrupted model-input frames; software rendering is the checked path. Hardware GPU rendering is unverified.
- Building presence does not prove operation or survival.

See `VALIDATION.md` for the dated record.

## Current adaptation and release boundary

The `oni-pointer-v3` input profile uses native Jev Box targets for clicks and two-target dragging, plus ordinary zoom, camera, Dig, pause and Tab to cycle simulation speed. Earlier profiles remain available for attribution: the first v1 Jev smoke chose hover in 49 of 86 decisions; v2 removed that independent choice but incorrectly described numeric keys as speed selectors. Version 3 replaces those three incorrect choices with the native Tab binding. The game supplies a factual pre-run interview brief, without strategy or route instructions. Jev completed a three-minute v2 live check; DeepSeek thinking-high completed a five-minute check with native clicks, drags, keyboard controls and scrolling, including visible excavation. These are historical functional checks, not acceptance of v3 or the required formal cohorts.

The backend declares process pause using the shared identity-checked `ProcessPause`. Real-process tests cover freeze, thaw and cleanup. Native checks show stopped threads and unchanged frozen pixels; the release boundary in both live and frozen execution additionally waits for six distinct full-window X11 DAMAGE updates, at most thirty seconds and never beyond the Trial deadline. The earlier eight-second cap failed during an ordinary native save. An uncompleted boundary fails the action rather than replaying it. Nine operator actions covered tool selection, two drags, right-click cancellation, menu transitions, native pause and camera movement. This is empirical presentation acceptance on the pinned software renderer, not an exact native simulation clock or universal guarantee under every loading condition. The historical survival rubric and Trial are unchanged.

Process stop alone is insufficient to qualify the final action image. Waiting for only two presentation updates also left a drag preview; six produced the completed orders in repeated operator checks. New cohorts use 0.7.5; historical 0.7.4 checks retain their original attribution.

The recreated base-game snapshot is [`snapshots/oxygen-not-included/base-terra-20261030-v1/`](../../../snapshots/oxygen-not-included/base-terra-20261030-v1/README.md), with derivation and checksums. It is a new standard-Survival functional baseline, not the lost historical start or final difficulty calibration. Extract its archive outside the repository and pass that folder as `--snapshot`.

Native live/frozen operator checks cover unsaved defeat, isolated restart, same-process recovery, bounded inherited notes and unchanged total budget. These are edited failure-fixture checks, not model outcomes. The completed DeepSeek live Trial additionally verifies a natural model-controlled death, identical-start restart, bounded same-model context inheritance and the unchanged original deadline. An ordinary-input operator-only Trial separately verified all five positive stages through the shared scorer, with comparison eligibility false and no model calls. Four cohort outcomes and the maintainer acceptance of continuous-development scoring are recorded above. Historical snapshots and results must retain their original identities. Keep starting snapshots and formal results out of `main`.

It is explicitly a scoring subset, not a full trajectory/video export or a model result. Independent parsing matches completed technology IDs, daily reports and ration counters.

Campaign 006 completed four fresh `*-development-v2-*.json` Trials with `oni-development-v2`, the unchanged `oni-pointer-v3` profile and independent empty contexts. All four canonical scores are 0/100 and comparison eligible. Source `e69cbe215f4f9d71903ac2c890ba0d85fb8b1af0` runs on the official 0.7.5 base digest `3ab222ed05382a43c6b3839e941cc0c78be6010cde5a0e544897c5714bd673a1`, with ONI image `sha256:8a2ed48a17b2c7e94a55942416db36571b8b0a02b9cdfba6593464de6327f161`. Candidate campaign 005 remains excluded because preparation omitted the development baseline; its original scores and exports remain diagnostic records. The historical four zero scores and operator-only 100-point check above use v1 and remain unchanged.

| Published v2 cohort | Charged time | Score | Completion |
| --- | --- | --- | --- |

Neither Jev run used its full one-hour allowance. Each stop followed review of 60 actual action screenshots covering 30 ineffective two-action loops, with the exact reason `manually observed ineffective loop; experiment closed to save tokens`. The live run repeatedly opened and closed the pause menu; the frozen run repeatedly expanded and collapsed bed diagnostics without colony progression. The published stop reports retain reviewed hashes and representative frames.

Following the maintainer's compact-record request and the Slay the Spire example, v2 publication retains native evidence, original decisions, trajectories, prompts, contexts, interview/configuration records, canonical scores, and initial/final screenshots. Per-step media, full recordings and provider session databases remain in the complete sealed local exports. Every omission and original hash is disclosed in `compact-manifest.json`. These reduced copies are not complete visual replays. Canonical rescoring in separate disposable copies matches every original assessment field, and independent GitHub tree checks verify every published blob. Original recording sampling gaps remain disclosed in each audit.

It uses the same starting snapshot, image, input profile and rubric, ordinary UI actions and the canonical Trial/scorer. The final milestone was preserved at 6,563.110 charged seconds; the operator then used the normal pause button and the Trial finished at its original 7,200-second deadline. Native evidence records three new beds, one toilet, production thresholds and seven new technologies including Agriculture and Ranching. Independent parsing agrees with the production and final technology records, and the compact rescore matches every canonical field. The complete local export and recording remain preserved; the remote copy also retains representative skill/research screenshots. This is a positive scoring check, not autonomous model performance, difficulty calibration or maintainer acceptance.

## Release 0.7.6: reuse and ten-point scoring

ONI declares `budget: time`: colony development is continuous, so language-model Trials retain 10,800 seconds and Jev Trials retain 3,600 seconds. The four `*-development-v3-{live,frozen}.json` specifications change only identity and rubric relative to v2. The shared input profile, nominal frozen host step, renderer boundary and initial snapshot remain unchanged. This migration does not test a longer frozen step or claim that presentation updates imply completed construction. No new gameplay or provider calls were needed for this migration.

The actual executions remain attributed to 0.7.5. Original contracts, interviews, scores, media archives and compact manifests are unchanged. New score files sit beside the original bundles and carry `retroactive.frozen_rubric_id`; no episode-limit override is applied to this time-budget game. Original interview predictions concern the old rubric and are not new v3 predictions. Jev has no pre-run interview.

| Preserved cohort | Original score | Retroactive v3 score | Eligibility |
| --- | --- | --- | --- |
| v1/004 DeepSeek live | 0 | 50 | Comparable; 10,800 s |
| v1/004 DeepSeek frozen | 0 | 20 | Comparable; 10,800 s |
| v1/004 Jev live | 0 | 0 | Comparable; 3,600 s |
| v1/004 Jev frozen | 0 | 0 | Comparable; reviewed manual stop at 1,528.604 s |
| v2/006 DeepSeek live | 0 | 30 | Comparable; 10,800 s |
| v2/006 DeepSeek frozen | 0 | 30 | Comparable; 10,800 s |
| v2/006 Jev live | 0 | 0 | Comparable; reviewed manual stop at 1,192.701 s |
| v2/006 Jev frozen | 0 | 0 | Comparable; reviewed manual stop at 2,584.307 s |
| Separate v2 operator check | 100 | 100 | Operator only; comparison-ineligible |

The two latest DeepSeek scores meet the approximate 40-point calibration target. The older live run scores 50 and is explicitly retained; no aggregate or universal calibration claim is made, and the rubric remains `calibrated: false` pending review. Its five awards are bed, toilet, generator, diffuser and food. Both latest DeepSeek runs earn toilet, generator and diffuser; without a completed bed they cannot unlock the production prerequisites. The operator evidence covers all ten milestones. Rejected campaign 005 remains excluded.

To reproduce the append-only reassessment on a separate restored copy:

```bash
python -m gamecua.cli score-trial --run-dir /private/copied-trial \
  --rubric benchmarks/rubrics/oxygen-not-included/development-v3.json
```

Future multi-model experiments require actual provider model IDs and funded credentials, kept in ignored configuration. The requested order is official DeepSeek (reuse qualifying evidence), GPT-6-Astra, Opus 5.5, then Grok 4.7. No new-provider result is claimed by this migration.

### Broadened facility reassessment (2026-11-01)

`oni-development-v4` and four `*-development-v4-{live,frozen}.json` Trial specifications supersede v3 for future runs. Only the three owner-selected facility descriptions and generator/oxygen-device predicates change; the seven remaining milestones, 1/3/6 research thresholds, advanced research requirements, input profile, budgets, snapshot and frozen timing are unchanged. Evaluator `oni-native-progress-11` preserves historical predicates.

Results match v3: DeepSeek v1 live/frozen 50/20, DeepSeek v2 live/frozen 30/30, all four Jev Trials 0, separate operator positive control 100 (comparison-ineligible). These remain 0.7.5 executions assessed offline with 0.7.6; no new gameplay, interview or model call occurred. All historical scores, including v3, remain preserved. The current rubric remains uncalibrated pending maintainer review, with the historical 50-point result disclosed. Later multi-model experiments await provider account/funding/local credentials.
