# PEAK

PEAK (Steam App ID 3527290, `game.json` id `peak`) is a Windows game integrated experimentally under official Proton on WSL; roster status is `experimental` (`game.json` status `configured`). The budget is native attempts. Timing supports `live` and process-paused `frozen` inference on the same real-time game. Input uses XTest with a captured mouse at 1280x720. The model starts at the native title screen with empty context and discovers the airport and expedition itself. Preparation metadata, telemetry and scoring rules never enter its prompt. Contributor: Guobin Zhang.

## Kimi K3.1 Pro on 0.7.14

The Kimi campaign uses the unchanged main model `kimi-k3-1-pro`, high effort, one life within 10,800 seconds per independent Live/Frozen trial. Live explicitly passes `--observation-age-limit 240`. Both immutable images use official 0.7.14 with the local PEAK native-pause and Mesa25 compatibility; shared execution, scoring, Steam preparation and model files are unchanged.

Live completed at its original deadline with canonical **0/100**, 61 decisions and 7 age rejections (**11.48%**). It reached the airport but no expedition, selected difficulty or island.

The independent Frozen replacement completed at its original deadline with **13/100**, 208 executed actions and no age rejections. The agent selected default **PEAK** and reached **Level_102**; native evidence verifies a 4 m anchor and 17 m maximum height, yielding thirteen one-meter ascent milestones. No death or victory occurred. Its immutable image disables Proton FSYNC and NTSYNC following two fresh-prefix, 50-cycle native readiness checks. The original Frozen trial failed with `SuspendThread loop failed`; its incomplete serialized zero is excluded, and its evidence and uncertain action remain preserved. Different runtime conditions and Live's absence of an expedition preclude a matched causal comparison. This completed run does not establish universal rendering stability; see `VALIDATION.md` for the diagnostic limits.

All 1,342 archived source files and all 1,181 original files in the two [HF Kimi cells](https://huggingface.co/datasets/Zhuhan/GameCUA-V1-Exp/tree/main/peak/kimi-k3) were verified against source hashes. The interrupted Frozen original is separately archived on GitHub and correctly skipped by the official HF tool. Historical records are preserved; deferred DeepSeek reconstruction tables remain unpublished.

## Grok Live observation-age rerun

The 2026-11-14 independent Grok 4.7 Live rerun uses high effort, one life within the original 10,800-second allowance, and explicit `--observation-age-limit 180`. Its immutable runtime is based on official 0.7.11 and retains the previously validated local Steam/PEAK/graphics compatibility layer; shared execution, scoring, CLI and spec files match the official image exactly. The existing Frozen cell is unchanged.

The rerun completed at its original deadline with **0/100**, scoreable and comparison eligible: 566 decisions, 566 executed actions, and **0/566 observation-age rejections**. Twenty-two observations were older than 30 seconds; the oldest, 115.16 seconds, still executed. The model reached the airport but never started an expedition, selected a difficulty or reached a daily island. This zero does not measure climbing performance. The affected historical Live record had 102/102 rejected decisions and remains preserved; provider and runtime changes prevent a matched causal comparison.

Both remote copies were verified against the original source files. The spec table below remains the historical campaign configuration; this rerun's configuration is preserved in its published `model.json` and `trial.spec.json`.

## One life and three hours

PEAK runs both live and frozen. Historical Jev specifications and results remain preserved. The 0.7.6 sections below describe historical work, not the new language-model budget.

**The local experiment owner explicitly instructed the operator to proceed without waiting for rubric review on 2026-11-12.** This is an owner-authorized exception to the review gate, not a claim of core-maintainer approval. The rubric remains uncalibrated. New cells use `reasoning_effort: high`, empty independent context, and the same `peak-controls-v1` input profile:

| New specs in `benchmarks/trials/peak/` | Model | Mode / cap |
| --- | --- | --- |
| `ascent-points-v1-opus-live.json`, `ascent-points-v1-opus-frozen.json` | `claude-opus-5-5` | live / frozen, one life, 10,800 s each |
| `ascent-points-v1-astra-live.json`, `ascent-points-v1-astra-frozen.json` | `gpt-6-astra` | live / frozen, one life, 10,800 s each |
| `ascent-points-v1-grok-live.json`, `ascent-points-v1-grok-frozen.json` | `grok-4.7` | live / frozen, one life, 10,800 s each |

The [validation record](VALIDATION.md) lists completed cells, actual difficulty/map checks and preserved incomplete trials. The archive contains 26,992 original files; both remote copies were verified. GitHub automatic Source code downloads are not the evidence archives. The validation record distinguishes title-only deadline zeros from observed expedition performance. Different image revisions or a shared daily scene name do not establish a matched comparison.

The additional owner-authorized Jev Live cell uses `ascent-points-v1-jev-live.json`, the current fine rubric and the same `jev-1-14` model and `peak-controls-v1` input profile. Its budget remains one native attempt within 7,200 seconds, not the language-model budget. Local manual-stop decisions and their explicit owner instructions belong in the experiment record; no automatic loop-stop policy is added to the shared runner.

Frozen steps retain the historical 1.0 s step length. Both modes use shared `freeze_retry_timeout_credit`: pause the native game on request failures, a 600 s request timeout, recorded timeout credit, bounded retry backoff and an operator pause at exhaustion. The original deadline stays recorded. Resume only through the canonical provider-recovery workflow with the same model/session and existing allowance. Do not modify shared recovery code or silently extend a trial. API keys belong only in ignored local configuration (`CLAUDE_API_KEY`, `GPT_API_KEY`), never in a trial spec or result bundle. An immutable updated environment must pass separate native readiness checks before the new campaign.

The PEAK observer's 180-second scene-loading grace excludes only confirmed native-process pause intervals overlapping its latest sample. These intervals are kept in private runtime recovery state. A process that has actually run without new telemetry for more than 180 seconds still fails. This changes the observer watchdog only; inference, ordinary retries and game actions continue to consume the same Trial budget.

PEAK allows at most 10 seconds to confirm a native process stop. Every surviving native thread must be stopped before frozen inference begins; an exiting thread causes a fresh check, not a false confirmation. PID identity is rechecked throughout. Failed confirmation releases the stop and raises an error. Slow confirmations and timeout thread states are retained in private local diagnostics. Confirmation overhead remains charged to the original Trial deadline; it grants no extra game time or model allowance. This game-local mitigation does not establish the root cause of the intermittent Wine/driver stalls described in the validation record.

### Candidate: `peak-ascent-points-v1`

`benchmarks/rubrics/peak/ascent-points-v1.json` has 100 equal points: `ascent-001m` through `ascent-100m`. Point N requires a verified conscious sample in the same expedition with `rows[].height_meters - run_start.height_meters >= N`. The saved observer reads `Character.localCharacter.refs.stats.heightInMeters`. Each threshold is distinct and awarded once; falling and reclimbing cannot accumulate height. The score is the number of reached thresholds (100 points total), not distance travelled, survival time or a model claim.

All points use the existing native evidence and beach anchor. Episode binding, setup hash, run identity, sequence, finite fields and known native segments must validate. Airport, uninitialized, dead, passed-out and terminal samples cannot earn new fine ascent points. The terminal frame's large height jump is excluded. Native death/victory detection remains independent of obtaining 100 points: 100 m is an early-ascent scoring horizon, not a declaration that PEAK was won. The 100-progress/0-collection ratio and proposed two-hour horizon require maintainer review; see `VALIDATION.md`. The observer, old rubric files, old trial specs and original scores are preserved.

The existing live calibration was directly rescored under that owner authorization with:

```bash
python -m gamecua.cli score-trial --run-dir <calibration076-001/work/trial> --rubric benchmarks/rubrics/peak/ascent-points-v1.json --episode-limit 1
```

Only the first life counts. Frozen records 005 and 006 need a separate first-life/10,800-second reconstruction table and explicit human acceptance before publication; the scorer's retrospective episode override does not impose a three-hour cut. Do not alter their original evidence, deadlines, rubrics, scores or summaries, and do not use a manual pass to bypass review. New one-life trials are scored normally without a retrospective episode-limit override.

## Setup and snapshot

- Use your own licensed account, the official Steam client and official Proton. The checked route uses Proton Experimental, DirectX 11 through WineD3D, and Mesa D3D12 on the WSL NVIDIA device. The Steam runtime's inner container did not expose the required WSL driver libraries, so direct official Proton execution with the authenticated client is the local deployment route. The native process must load the WSL graphics libraries and open `/dev/dxg`; software fallback is rejected.
- If the system Mesa version renders PEAK incorrectly, `GAMECUA_PEAK_MESA_LIBDIR` can select an isolated, privately prepared Mesa library directory. It must contain `libGLX_mesa.so.0`, `dri/d3d12_dri.so` and the bundle's runtime dependencies. The launcher prepends it to the WSL library path while retaining the mandatory D3D12 hardware settings. Expose the same directory inside each execution container and preserve the exact bundle and provenance across episodes and cohorts. On the GTX 1660 Ti, the local diagnostic combination uses Mesa 25.2.8, `WINE_D3D_CONFIG=csmt=0x0` and the Unity argument `-disable-gpu-skinning`; Mesa 25 alone did not repeat reliably. Set `GAMECUA_PEAK_CPU_SKINNING=1` to supply that argument through the Trial backend. `GAMECUA_PEAK_DIRECT_RENDERING=1` additionally selects Unity's documented `-force-gfx-direct` option, disabling Unity graphics worker jobs. Keep this optional setting disabled (`0`, the backend default) for the locally validated v7 condition: two forced-direct diagnostic starts were black, while two default-worker starts rendered; three further production-limit cold starts and a native-death restart passed with it disabled. Historical v6 experiments retain their recorded setting. Bake these settings and the bundle into a private immutable execution image; a host shell setting alone does not enter an environment worker. This remains an experimental workaround with rendering limitations; see `VALIDATION.md`.
- `setup.capture_snapshot` freezes a clean title-screen Proton profile, official binary hashes, the observer build and preparation provenance. Each Trial episode uses an isolated prefix and a writable loader overlay. Preparation can retry an unrendered empty title in up to three separate prefixes, all within the original preparation deadline. They occur before model input and do not grant extra Trial episodes or game attempts; gameplay detected during preparation is rejected.
- `evaluator.cs` is a read-only observer loaded with BepInEx 5.4.23.5 in an independent copy of the licensed installation. It samples native height, map segment, run ID and character win/loss fields without input, game-state writes, game-method patches or evaluation UI. This is an instrumented condition; the unmodified game does not export this stream. `progress.py` scores episode-bound samples.
- Game binaries, loader downloads, compiled DLLs, Steam state, local deployment helpers and keys stay private and are not published.
- Native daily island rotation is preserved; different islands or difficulty settings are not matched comparison conditions.

## Historical 0.7.6 rubric

The 0.7.6 delivery rubric is `benchmarks/rubrics/peak/progress-v2.json` (`peak-progress-v2`, uncalibrated). It has ten milestones of 10 points each:

| Milestones | Native evidence |
| --- | --- |
| `rise-10m`, `rise-25m`, `rise-50m`, `rise-100m`, `rise-200m` | Conscious height above the same expedition's verified beach start |
| `shore-complete` | Advance beyond SHORE |
| `second-region-complete` | Advance beyond the day's second region to ALPINE |
| `alpine-complete` | Advance from ALPINE to CALDERA |
| `caldera-complete` | Advance from CALDERA to THE KILN or beyond |
| `summit-victory` | Native character statistics confirm victory |

All milestones measure ascent or required regional progress toward the summit. Each is awarded once per Trial. Heights and regional prerequisites must belong to one native expedition; progress from separate deaths cannot be combined. Unconscious height, historical account achievements and model terminal claims earn no credit. The previous eight-milestone `progress-v1.json` and historical trial remain unchanged.

The hardest native difficulty was originally requested. The local calibration instruction was updated on 2026-11-01: start at default PEAK, consider increasing native difficulty when a valid DeepSeek result reaches approximately 40 or more, and retain default when genuine gameplay earns less. Preserve the actual condition and do not describe a default run as highest difficulty. The first complete DeepSeek live calibration earned 30/100 at default PEAK, so the local campaign provisionally retains default difficulty. This single result does not validate the unobserved late-game milestones or constitute a matched live/frozen comparison; see `VALIDATION.md`.

## Historical controls and Trial specs

Both cohorts use `peak-controls-v1`: WASD movement, sprint, jump/climb, interaction, inventory and ordinary pointer controls. Arrow keys translate to mouse motion at 600 pixels per second; J/K translate to left/right mouse holds. These deterministic aliases do not observe game state or automate a route. The language model retains free keyboard and mouse actions.

| Specs under `benchmarks/trials/peak/` | Model | Budget |
| --- | --- | --- |
| `progress-v2-deepseek-live.json`, `progress-v2-deepseek-frozen.json` | `deepseek-v41-flash-thinking` | Two native attempts within 21,600 seconds |
| `progress-v2-jev-live.json`, `progress-v2-jev-frozen.json` | `jev-1-14` | One native attempt within 7,200 seconds |

The shared DeepSeek spec requests `deepseek-flash`, thinking enabled and high reasoning effort on the official platform. Secrets belong in private environment/configuration, never the catalog. Frozen inference stops and resumes the identified native PEAK process; interruption and shutdown release the pause.

Run through the canonical workflow, using independent evaluation environments for independent trials:

```bash
python -m gamecua.cli env-trial --environment <prepared-evaluation-environment> --trial-spec benchmarks/trials/peak/progress-v2-deepseek-live.json --seconds 21600
python -m gamecua.cli env-trial --environment <separate-evaluation-environment> --trial-spec benchmarks/trials/peak/progress-v2-jev-frozen.json --seconds 7200
python -m gamecua.cli score-trial --run-dir <completed-run>
python -m gamecua.cli export-trial --run-dir <completed-run> --output <new-portable-directory>
```

Inference, retries, later preparation and recovery consume the persisted budget. Each later attempt retains bounded same-model summarized memory; an independent trial starts empty. For a fresh final-spec trial, score normally without the retrospective `--episode-limit` override: the second death, verified win or original time cap ends the trial, whichever comes first. Report the actual episode/death count separately. Operator checks and shortened pipeline checks are not completed delivery runs. Keep formal bundles out of `main`.

Reuse completed historical evidence before rerunning: `score-trial --run-dir <old-run> --rubric benchmarks/rubrics/peak/progress-v2.json --episode-limit 2` (use 1 for Jev). Only verified covered attempts qualify; an old timer completion alone does not. Preserve old scores. The historical PEAK directory initially contained only `.gitkeep`; the newly completed live 30/100 trial is preserved and reused. Historical frozen trial 005 earned 20 partial points before its second preparation failed; it remains incomplete and excluded from aggregate comparisons. Independent v7 trial 006 later earned 20/100 and completed at its original six-hour cap in one episode without death; normal canonical scoring is eligible. Its two assessments are preserved, including the initial retrospective coverage assessment. Its original evidence and both assessments are published under the campaign's `deepseek-frozen/` directory with remote-manifest verification. Jev live 007 lost the game window after nine inputs and remains incomplete; its verified evidence is published under `interrupted-trials/`. Frozen cell 008 passed a reviewed pre-trial Steam startup recovery, then recorded 616 autonomous actions over 4,552.65 seconds. Thirty consecutive Escape open/close menu groups were visually verified as ineffective, and the documented Jev STOP rule ended the trial. Normal scoring is 0/100, completed, comparison eligible and manual_stop true; no difficulty or island was reached. Its verified canonical evidence is published under `jev-frozen/`. Jev live 007 remains incomplete. One explicitly authorized independent live trial 009 also lost its window after eight inputs near the native Quit control; its 57-file evidence package is published under `interrupted-trials/delivery076-009-jev-live/` and remains incomplete/ineligible. No valid Jev live/frozen pair is available, and no further replacement is started automatically. Historical Jev attempts 003 and 004 failed before model input; their serialized zeros remain infrastructure failures, not model scores. All current completed, incomplete and failed records are published in separate campaign directories with their actual eligibility. See `VALIDATION.md` for exact trial identities and publication status.

A private Proton preparation is still needed locally; never publish its Steam state, game/loader binaries, personal profile or license probe. This marker does not claim a fixed island or matched conditions across dates.

## Known limitations

- PEAK 3.1.0 experienced a D3D12 allocation failure and native graphics-thread crash during one autonomous island load on the recorded WSL runtime. A separate unchanged-runtime island load and three island pause/thaw checks passed afterward. Treat the interrupted trial as incomplete, retain its evidence, and do not interpret a successful short diagnostic as proof of long-run graphics stability.
- Native Title can remain unrendered despite bounded preparation retries. A failure before model execution is infrastructure failure, not a model zero. An episode still in `preparing` has no verified setup/checkpoint; the current canonical resume path would create another episode. Do not treat that path as recovery of the failed preparation or edit the preserved trial to force completion.
- The rubric is uncalibrated and the late-game milestones are not validated live; the Void segment is unsupported.
- Evaluator `peak-native-progress-4` retains the historical predicate semantics, adds the candidate fine thresholds, accepts numeric segment strings as well as named segments and rejects unsupported gameplay segments or missing run-start anchors. A preserved native regression excerpt exercises progress and death offline; a local development check also verified native loss through `Backend.poll` and a rendered, licensed, isolated restart through `Backend.prepare`. This operator check is not autonomous attempt coverage. The recorded v1 evaluator zero score and eligibility flag of the first three-hour execution must not be used as a validated result. See `VALIDATION.md`.
- Daily island rotation limits comparisons.
