# Understand

Experimental integration of licensed Steam app 1299400, Windows build 7803420 (1.2.3), through official Proton Experimental and Steam Linux Runtime 4.0. The recorded model runs used upstream 9f4bd822f0f4cba78cbff3346cc116657ca71e9f (release 0.7.4 plus the merged recorder change). The source submission is based on current main 9a1c65f483dbb7cae8b99b0987a3a484217ecd0f; it introduces no changes to the shared Trial loop, model transports, executor, context policy, schemas or dependencies.

## Timing and prepared state

The puzzle board waits for input; UI animation and recorded time do not create autonomous gameplay. Timing is turn_based, with live Trials only and no pause declaration. No difficulty selector exists in the tested menu. The opening is retained: three empty native slots, active slot 1, no seeded puzzle solutions.

Use the official Steam client and the researcher's licensed account. Every episode copies original game files and the frozen native zero-progress save into an isolated private working directory and Proton prefix. Game binaries and Steam account state are not included in source or results.

The game-specific snapshot manifest verifies prepared state only; it is not a Trial evidence-admission or score hash gate.

## Shared controls and cohorts

Both specs name understand-pointer-v3: left click, movement without pressing a button, and straight left-button drag. Jev uses unchanged native Box questions: one target for click/movement and two endpoints for drag. The shared core converts selected Boxes to their centers. The language model receives the same factual descriptions and retains standard free mouse/keyboard actions. No fixed puzzle coordinates, rule hints, solution routes, custom memory or forced exploration are supplied.

A left press starts a path when none is active. Pointer motion extends it even after release. The next left press submits it. A drag presses, moves and releases, so its initial press submits an already-active path. The typed group includes no explicit wait or otherwise inert button.

| Spec | Actual configured model | Standard budget |
| --- | --- | --- |
| ending-v3-live-3h.json | deepseek-flash; thinking enabled, reasoning_effort high | 10800 s |
| jev-ending-v3-live-1h.json | jev-1.14.0 | 3600 s |

Use the shared trial/env-trial, score-trial and export-trial commands. Independent Trials start with empty context. Thinking, retries, actions and later restart downtime consume the original deadline. DeepSeek's pre-run interview is separate and never enters gameplay context. Upstream skips Jev's interview.

The owner explicitly requested a 600-second Jev exception. Keep the standard 3600-second spec unchanged and use a runtime override. This exception needs maintainer acceptance before claiming the issue's original one-hour cell.

## Native ending rubric

The current uncalibrated rubric is understand-ending-v3, using the unchanged 0.7.6 core endpoint-assessment hook to inspect the entire preserved save ledger. Here endpoint means assessment at the end of the Trial; the score deliberately measures historical verified progress, not only the last save. Each category is capped at 10 and the total is 100.

| Category | Native requirement | Points |
| --- | --- | --- |
| 1-1 progress | floor(10 * verified unique panels / 4) | 0-10 |
| 1-2 progress | floor(10 * verified unique panels / 4) | 0-10 |
| 1-3 progress | floor(10 * verified unique panels / 5) | 0-10 |
| 1-4 progress | floor(10 * verified unique panels / 6) | 0-10 |
| 2-1 progress | floor(10 * verified unique panels / 4) | 0-10 |
| 2-2 progress | floor(10 * verified unique panels / 6) | 0-10 |
| EX-10 progress | floor(10 * verified unique panels / 10) | 0-10 |
| Opening six completed | Native reveal confirms all six opening groups in the original slot | 10 |
| EX-10 completed | Native reveal confirms the complete EX-10 group in the original slot | 10 |
| Ending | Native reveal confirms END and the complete mandatory spine in the original slot | 10 |

All plausible ending routes in the inspected pinned native map contain 1-1, 1-2, 1-3, 1-4, 2-1, 2-2, EX-10 and END. Other optional content earns nothing. Equal group caps express a coverage weighting decision, not evidence that groups have equal difficulty. Complete EX-10 receives its explicit additional 10-point completion award. Without verified END the maximum is 90.

A panel counts once when its saved submitted path passes the original native checker. Whole-group reveal independently proves that all panels of that group passed, including paths overwritten later. Union these proofs across in-budget checkpoints in the frozen starting slot; panel order does not matter and later redraws do not remove earned credit. Separate whole-group bonuses require native reveal, not merely individually observed panel successes. Other slots are ignored; disappearing completion flags or changed native level-start records make resets unresolved instead of pooling independent starts. Evidence paths, checksums, baseline identity and timestamps are checked before assessment. Corrupt or unavailable assessment yields an unknown score with explicit failures, not a fabricated zero.

The original save stores the latest submitted path, not an independent persistent Boolean for each panel. A redraw can clear live UI indicators while the last submitted save is still successful. This evaluator therefore does not claim instantaneous UI status or exhaustive coverage of unpreserved changes inside an action or after the last poll. Each award retains the native source paths and panel-level proof provenance. No model interpretation or board-internal coloring is used.

Set UNDERSTAND_NATIVE_GAME to the licensed original game directory containing understand.exe with SHA-256 ad062c16e8c010661c313c84f66cfbf9e7c9f85286c9d34a3b5a8d835b784e59. On Linux install LuaJIT or Lua 5.1 for the scoring host, or set UNDERSTAND_LUA to its executable. The worker reads the game's Lua modules and map.csv in memory, calls the native loader/checker and disables save, filesystem writes, menu completion and process execution. EX-10 depends on the native transposed menu map, which is initialized using the original readcsv module. No proprietary source, assets, DLL or solved paths are distributed here. Runtime and native-source hashes are recorded in each assessment. These dependencies apply only to scoring; no evaluator rules enter the no-rules agent prompt.

The new score file records retroactive attribution. Keep understand-ending-v2, both v2 trial specs and every published v2 score unchanged. New v3 specs retain the shared pointer profile and the original 10800/3600-second time budgets. The accepted historical Jev exception remains exactly 600 seconds, never relabeled as a one-hour run. No new autonomous run is needed when the preserved evidence supports all new predicates.

## Route panel rubric for review

Its 100 progress points cover 17 groups on native routes toward END. Each panel is independently scored. Alternate routes can cover different portions of the fixed panel list, and the game records native victory separately.

Scoring uses in-budget checkpoints from the frozen starting slot in the first episode. In the native save, a group in `data[1][0]` proves that every panel in that group passed. For a group without that flag, the pinned native checker verifies the saved submitted path in `data[1][3][group][panel - 1]`. The earliest verified checkpoint supplies the charged time, relative evidence path, SHA-256 and proof method for each award.

With the pinned licensed game and the scoring runtime described above, reproduce a candidate assessment from a separate copy of a completed Trial:

```bash
UNDERSTAND_NATIVE_GAME=/path/to/licensed/Understand python -m gamecua.cli score-trial --run-dir /path/to/bundle --rubric benchmarks/rubrics/understand/route-panels-v4.json
```

The two-hour counts are calibration observations. The scored interval follows the Trial's effective allowance. See [VALIDATION.md](VALIDATION.md) for observed reachability and historical recalculations. Core-maintainer review of the candidate rubric is pending. New language-model Trials use Live, one episode and a 10,800-second cap.

## Lifecycle and recording boundary

The game layer adds in-process normal-exit continuation: owned launcher exit code 0 plus the exact missing-window condition permits one same-profile reopen per exit, preserving Trial, episode, agent and deadline. Time is charged; uncertain inputs are not replayed and nonzero crashes are not restarted. Native QA verified a reopen in 4.48 seconds with unchanged progress. A real-process regression verifies the newly launched process instead of an already-exited old PID.

Infrastructure recovery requires the original live process/window/save/pointer checkpoint. Normal-exit continuation needs the original launcher's Popen handle; it does not promise to prove and retry a later normal exit after a restored worker loses that handle. Unverifiable recovery interrupts.

The recorder is the exact upstream change. Metadata survives capture/cleanup failures, but video does not resume after window loss. No extra local recording-gap patch is applied. Both delivered runs had zero native restarts. Maintainer acceptance of normal-exit continuation as a benchmark condition remains open.

## Validation and results

The tested runtime passed 1099 tests (5 skipped), catalog validation, verify-example, layout and Ruff. The actual image passed 20 focused tests. Audits matched 42 upstream shared source/model/dependency files and 32 installed shared Python files. Runtime image: gamecua-understand:0.7.4-pr101-restart-v2-20261027, sha256:3c3f778aec98aef1dda5664cbb880c73618c9d8c924bdb4b8f06cab2846e2112.

| Cohort | Actual budget | Score | Native result |
| --- | --- | --- | --- |
| deepseek-flash, thinking enabled/high | 10800 s | 20/100 | 1-1 and 1-2 completed; 1-3 incomplete; 976 actions |
| jev-1.14.0, owner exception | 600 s | 0/100 | No completed group; 202 left clicks |

Both independent evaluation runs ended at deadline with worker exit 0, standard scoring/export and stopped containers. DeepSeek's interview predicted 20 points with 65% confidence. Its score meets the approximate <=40 numeric target without establishing complete rubric calibration. The shortened Jev result is excluded from one-hour claims; canonical core flags remain unchanged.

See [VALIDATION.md](VALIDATION.md) for dated records and outstanding acceptance items.
