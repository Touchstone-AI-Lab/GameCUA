# Civilization VI

Experimental integration of the officially licensed Steam game (App ID 289070). The 0.7.0 cohort targets the Windows DX11 build through Steam Proton, Gathering Storm, Deity difficulty, Ancient Era, an Aztec human player and one AI opponent. Only Science Victory is enabled. Both models load the same private undeveloped save and use the same input profile. This turn-based game requires live runs only.

## Current 0.7.6 delivery

Civilization VI declares `budget: time`: a game normally outlasts a Trial, and defeat is rare. The required live pair remains `deepseek-v41-flash-thinking` for 10,800 charged seconds and `jev-1-14` for 3,600 charged seconds. Both new `civilization-vi-science-route-v3-prince-box-3h` and `civilization-vi-jev-science-route-v3-prince-box-1h` specs use `civilization-vi-native-box-v1` and `civilization-vi-science-route-v3`. No attempt limit is added.

The Prince development condition was accepted on 2026-10-29. V3 carries forward that explicitly labeled difficulty and the same city-free snapshot `b7cc49a985705a0e1e90f0713600d50978dbe7fdced8448da1fcfe3f5ceb860f`. Its preparation, native read-only collector and input execution are unchanged. This is not a claim that historical Prince runs used Deity or a 0.7.6 execution image.

V3 has ten distinct milestones worth 10 points each. All are on the native Gathering Storm Science Victory route. They are factual evaluator conditions, never gameplay instructions for the no-rules agent.

| Milestone | Preserved native evidence and relation to the ending |
| --- | --- |
| City | A human-owned city after the city-free start; a city supplies the production queue needed for space infrastructure. Founding or capturing a city can satisfy this. |
| Rocketry | Completed technology required by Launch Earth Satellite. |
| Spaceport | Completed, unpillaged human-owned district required by the space-race projects. |
| Satellite | Completed Launch Earth Satellite; prerequisite for Launch Moon Landing. |
| Satellites | Completed technology required by Launch Moon Landing. |
| Moon | Completed Launch Moon Landing; prerequisite for Launch Mars Colony. |
| Nanotechnology | Completed technology required by Launch Mars Colony. |
| Mars | Completed Launch Mars Colony; prerequisite for Launch Exoplanet Expedition. |
| Exoplanet | Completed Launch Exoplanet Expedition. |
| Science Victory | Native human Science Victory, all four completed projects and the required expedition distance. |

Project prerequisites were checked against the licensed installation's `Base/Assets/Gameplay/Data/Projects.xml` and `DLC/Expansion2/Data/Expansion2_Projects.xml`. Milestones are awarded once when a complete preserved checkpoint first verifies them inside the original budget. Partial research, boosts, partial construction, elapsed turns, exploration, optional combat and model claims earn nothing. A missing or stale final checkpoint remains unscoreable; player/team identity, source checksums and native victory requirements fail closed. Historical awards remain earned after a later loss of a city or Spaceport. This is a new scale, not a normalization of the old development score.

Finished development-v2 Trials can be rescored through the unchanged canonical command:

```bash
python -m gamecua.cli score-trial --run-dir /path/to/preserved-trial \
  --rubric benchmarks/rubrics/civilization-vi/science-route-v3.json
```

Do not pass `--episode-limit` for this time-budget game. The command appends a score with `retroactive` provenance; it does not edit the frozen Trial spec, rubric, original score, actions, clock or interview. The old interview remains a prediction about the old rubric. A canonical typed Jev cost-saving stop remains a manual completion with its actual charged duration, not a full-hour run. Original source/image, input-profile differences and recording gaps must remain disclosed when publishing a retroactive comparison. Evidence without the required native technology/district inventory cannot be assigned missing milestones as zero.

The following sections preserve the historical science-v1 and development-v2 conditions.

## Historical science-v1 cohort

| Model spec | Trial spec | Budget | Inputs |
| --- | --- | --- | --- |
| `deepseek-v41-flash-thinking` | `civilization-vi-science-v1-live-3h` | 10,800 s | `civilization-vi-grid-v1` |
| `jev-1-14` | `civilization-vi-jev-science-v1-live-1h` | 3,600 s | `civilization-vi-grid-v1` |

DeepSeek uses the shared official-service transport with thinking enabled and reasoning effort high; Jev uses the shared native Typesafe transport. Supply `DEEPSEEK_API_KEY` or `TYPESAFE_API_KEY` privately. The input profile contains a 20 by 12 left-click grid and ordinary keyboard controls without strategic advice. The independent pre-run language-model interview receives the game introduction and rubric. Gameplay receives no evaluator goals or native state. Jev has no interview.

## Science rubric

`civilization-vi-science-v1` is uncalibrated. Each milestone requires its preceding milestone and earns 20 points, for a total of 100.

| Milestone | Required native evidence |
| --- | --- |
| Satellite | Complete Launch Earth Satellite |
| Moon | Complete Launch Moon Landing |
| Mars | Complete Launch Mars Colony |
| Exoplanet | Complete Launch Exoplanet Expedition |
| Science Victory | The human team is the native science victor and its expedition has reached the required distance |

Attribution uses `Game.GetLocalPlayer()` so an AI using the same civilization cannot contribute. Production progress, exploration, optional achievements and model victory claims earn no points. Native elimination or another team's victory ends the episode. Earned points remain separate from completion and comparison eligibility.

## Private setup

Use the researcher's own licensed account, official Steam client and installed Windows game. Select DX11 in Steam. Validate actual NVIDIA rendering, official executable mapping, game capture and input before evaluation. An OpenGL readiness probe alone does not validate software rendering of the Proton game.

For the validated Proton configuration, set the game's Steam launch options to `python -m gamecua.games.civilization_vi.runtime %command%`. This preserves the official Steam launch chain, selects the installed DX11 executable, limits shader compiler threads and disables the two Steam Vulkan layers used in this host's compatibility setup. It is a game launcher, not an alternative Trial runner.

Prepare the specified configuration through ordinary game menus in a development environment. Disable community mods, preserve official DLC and set `EnableTuner 1` in the isolated preparation profile for evaluator access. Tuner access disables Steam achievements. The collector has no gameplay write commands, and neither model receives its channel or output. Both cohorts use identical settings.

Save the undeveloped first turn. Preserve private 1280 by 720 loading references and `plan.json`: guarded ordinary menu clicks load the prepared start save (captured as `GameCUAStart`), `initial_frame` permits exactly one Shift+Return preparation turn, and `evaluation_frame` verifies the resulting undeveloped map. Capture the snapshot while the initial native state is available:

```bash
GAMECUA_CIV6_RUNTIME=steam_proton \
python -m gamecua.games.civilization_vi.setup \
  --profile /path/to/private/native-profile \
  --save /path/to/private/first-turn.Civ6Save \
  --civilization CIVILIZATION_AZTEC \
  --reference /path/to/private/load-reference \
  --output /path/to/private/science-snapshot
```

Capture and reload fail closed unless native state verifies Deity, Gathering Storm, only Science Victory, the same human player and zero initial science projects. The snapshot manifest freezes setup. Preparation and the independent interview finish before the canonical clock starts; gameplay begins after the single documented preparation turn. Independent Trials start with empty agent context.

The Windows profile and Documents save directory are isolated separately and restored on clean shutdown.

## Execution and publication

Create fresh canonical evaluation environments with the same frozen snapshot, source, renderer and input profile. Reuse one Steam home exclusively, stopping the previous environment first. An operator-intervened development environment cannot become an evaluation environment.

```bash
python -m gamecua.cli env-trial --environment /path/to/deepseek-environment \
  --trial-spec benchmarks/trials/civilization-vi/science-v1-live-3h.json --seconds 10800
python -m gamecua.cli env-trial --environment /path/to/jev-environment \
  --trial-spec benchmarks/trials/civilization-vi/jev-science-v1-live-1h.json --seconds 3600
```

Use only `trials.py` through the shared CLI. Inference, retries and downtime follow the persisted charged budget. Language-model death may restart within the same Trial with bounded same-model knowledge; Jev ends at its first native death without memory. Recovery requires the same live process, bound profile, native state and frame. Never reload a save to replay uncertain actions. Recording uses two frames per second.

Append assessments with `score-trial`, then use `export-trial`. Publish cohort results outside `main`, including interviews, actions, recordings, native evidence and errors. Keep keys, Steam state, rotating native autosaves and mutable process logs private. The prepared start save is in `snapshots/civilization-vi/`. Interrupted segments are not independent episodes; exclude incomplete and failed Trials from aggregate comparisons.

## Validation status

The new cohort remains `configured` until native science collection and the autonomous runs are verified. Synthetic tests are integration checks, never model results. The historical early-empire rubric, Linux pilot and non-thinking observations retain their original attribution and do not calibrate this rubric. See `VALIDATION.md` for dated evidence and remaining limitations.


The researcher-requested development trials use Prince difficulty, an Ancient Era Aztec start, one AI opponent and only Science Victory enabled. Its development rubric is a separately labeled research condition, not the release science-v1 cohort. The frozen v2 rulebook allocates 40 points to basic development and 60 to advanced development. The canonical `score()` workflow selects the rubric's explicit `endpoint` assessment, preserving fractional category awards and returning an unknown total when a required ledger or endpoint is unresolved. Historical science-v1 results and their original assessments remain unchanged.

Development trials record at five frames per second and preserve each ordinary action's before/after images. The private read-only native channel additionally records attributed city, technology, civic, treasury, district, building, governor, trade-route, unit, visibility, improvement, pillage and citizen-work state. Native event subscriptions retain original arguments and cached unit identities; they never execute gameplay commands. Evaluator projections and scoring state are never supplied to the playing agent. The native unit-added callback updates the unit-type cache before a later death can remove the unit. Ambiguous event attribution remains unresolved rather than being assigned zero.

## Official native Box cohort: 0.7.4

`civilization-vi-native-box-v1` uses the official 0.7.4 input contract with left click, right click, pointer movement, native Box drag, two scroll directions and the 15 existing ordinary keys. Jev receives one input Choice and the official pointer Box questions in the same request. Box centers map to the selected physical input through the unchanged upstream executor. There are no extra targeting stages, derived candidate crops, cooldown exclusions or external playing agent.

`civilization-vi-jev-development-v2-prince-box-1h` freezes a 3,600-second Jev budget, Prince snapshot, development-v2 rubric and five-fps window recording. `civilization-vi-development-v2-prince-box-3h` is the paired language-model run with the same input profile. The earlier grid-v1 development specs were removed; historical grid-v1 results retain their original profiles and scores, and their different executor/input conditions must be disclosed rather than treated as a matched native-Box comparison. Preserve the official base-image digest, integration source revision and unchanged upstream typed transport hashes in the run receipt.

The optional Jev cost-saving stop follows the root README: review the last 30 consecutive actions or repeating action groups and their preserved screenshots before creating the Trial-root `STOP` file. Retain the observed loop evidence and the exact closure reason in the delivery record, and use the canonical scorer without editing an existing assessment. Infrastructure errors remain distinct from ineffective model behavior. This policy does not enable the separately archived harness-research targeting or cooldown methods.
