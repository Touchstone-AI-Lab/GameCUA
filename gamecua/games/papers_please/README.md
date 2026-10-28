# Papers, Please

Experimental real-time integration (game id `papers-please`, Steam app 239030): official Linux build 1.4.11.124 (Steam build 10817815), fresh English normal-difficulty story profile. The native window is 570x320, captured at 2x as 1140x640 with normalized inputs mapped back to the original window; `xtest` input backend. Timing is `realtime`: once work has begun, the workday clock and animations advance without input. The integration now uses the shared pidfd-based process pause for frozen steps; process stop/resume, frame stability and a native analog-clock probe have been checked on the licensed game. A 20-second freeze showed no gross catch-up after resume in that probe; a day-three DAY-to-NIGHT operator acceptance with repeated freezes also passed. Formal model frozen-trial acceptance remains pending. A game-scoped 200 ms cursor settling interval precedes each click or drag, and clicks hold the button for 300 ms; both are charged to the budget. See [VALIDATION.md](VALIDATION.md).

Researcher: Mengjiao Liu; initial integration by Zhuhan Bao. The current game configuration targets release 0.7.6, uses attempt budgets, and retains the shared pointer profile introduced for 0.7.4.

## Setup and snapshot

Use the licensed official Steam application with a live authenticated client. The backend creates an empty episode profile through the game's savedir switch and copies only English, normal-difficulty settings. Capture three operator views before processing a traveler (`title-menu.png`, `new-menu.png`, `office-start.png`), then run the setup module inside the official Steam development environment:

```bash
.venv/bin/python -m gamecua.games.papers_please.setup --profile PROFILE --installation INSTALLATION --references REFERENCES --output runs/papers-please/setup
```

The snapshot holds `settings.sav`, `preparation.json`, the three references and `snapshot.manifest.json`, and records installation hashes, the version and the discovered native file-format decoder key (not an account credential). Preparation verifies native menu and office pixels and reaches the first workday without processing a traveler. The native encrypted big-endian XXTEA/Haxe stash is read without executing serialized classes or writing game state. Setup references, assets, saves and account state stay private.

## Rubric

The researcher-approved rubric is `papers-please-story-v3`, uncalibrated, 100 points. Each milestone is earned once within a trial from preserved native evidence. Its day nodes follow story progression through day 29, the earliest day on which the accepted escape endings can occur; the final node is a researcher-approved native success ending.

| Milestone | Points |
| --- | --- |
| Reach native story workday 2, 5, 7, 10, 15, 20, 23, 26 or 29 after genuine processed progress | 10 each |
| Reach one of the accepted native success endings | 10 |

Success means ending 16 or 18 (successful escape regardless of accompanying family), 19 (EZIC success), or 20 (continued employment after clearance). Solo escape and partial-family escape qualify. Other endings are failures under this benchmark policy. FamilyTakeCount is not used in scoring. Failure retains previously earned milestone points; points, completion, scoreability and comparison eligibility remain separate. Incomplete trials are excluded from aggregate comparisons. Rubric calibration and full native terminal acceptance remain pending, so the configuration is not a readiness or success claim.

## Shared input profile

`benchmarks/inputs/papers-please/pointer-v1.json` is the release 0.7.4 profile for new runs. Its single mandatory group offers an ordinary left click or left-button drag. Jev locates the click target with a native Box question, or the drag origin and destination with two Box questions in the same decision request. Descriptions provide controls only. Both cohorts reference this profile, with one-second frozen steps. The retired 0.7.1 grid profile, the `story-v1` rubric and their Trial specifications were removed; their published results keep their original attribution. The game-specific desktop still reserves 200 ms for a hover update before dragging. Operator control acceptance is separate from autonomous benchmark results.

## Trial specs

The `story-v3-pointer-*` and `jev-story-v3-pointer-*` specifications under `benchmarks/trials/papers-please/` share rubric `papers-please-story-v3` and input profile `papers-please-pointer-v1`:

| Specifications | Model | Budget | Mode |
| --- | --- | --- | --- |
| `story-v3-pointer-live-6h.json` | `deepseek-v41-flash-thinking` | 21,600 s, 2 attempts | live |
| `story-v3-pointer-frozen-6h.json` | `deepseek-v41-flash-thinking` | 21,600 s, 2 attempts | frozen steps, 1 s |
| `jev-story-v3-pointer-live-2h.json` | `jev-1-14` | 7,200 s, 1 attempt | live |
| `jev-story-v3-pointer-frozen-2h.json` | `jev-1-14` | 7,200 s, 1 attempt | frozen steps, 1 s |

The preceding `story-v2` specifications and rubric remain unchanged for historical result attribution.

The researcher authorized model execution on 2026-10-26 and requested the 0.7.4 Jev migration on 2026-10-27. The 0.7.4 Jev live and frozen full-budget Trials completed at one hour each. The first two 0.7.4 DeepSeek live attempts interrupted and remain incomplete. After native progress rewinds were changed to preserve evidence and continue, an independent DeepSeek live/frozen pair completed at three hours each; both scored 20 and are comparison eligible. All experiment artifacts remain private and unchanged. Smoke results never calibrate the rubric.

All four finished 0.7.4 cells have been rescored with `story-v3` and published beside their original scores. Only the DeepSeek live cell covers its first two attempts and remains comparison eligible. The six-hour 0.7.6 DeepSeek frozen Trial is accepted as a descriptive full-budget observation, but it contains one of two attempts and is not comparison eligible. The accepted 49-minute Jev live observation is incomplete and not comparison eligible. A separate 4-hour-50-minute DeepSeek ProviderFailure is preserved as diagnostic evidence. No further Jev Trial or DeepSeek frozen rerun is planned; the current observations do not form a complete comparison cohort. See the dated record in [VALIDATION.md](VALIDATION.md).

Preserve original encrypted native evidence for independent re-scoring. Keep licensed paths and API keys in private configuration; operator acceptance and failed startup attempts are not autonomous results.

## Known limitations

- The shared `papers-please-pointer-v1` profile requires release 0.7.4 native Box drag support. Historical 0.7.1 grid smokes are not acceptance for the new Jev interface. The specified 0.7.4 Jev and DeepSeek full-budget pairs have completed; rubric calibration and native late-game ending acceptance remain pending.
- Process-pause lifecycle coverage uses a real Linux child process; this is infrastructure validation, not a native game result.

- Day-two and day-three transition evidence is verified; later rubric workdays and full native ending acceptance remain unverified. The observed bankruptcy END stash is decoded and classified as death while retaining earned milestones. Named endings are mapped from original game content under the approved policy: endings 16/18/19/20 succeed and the other distinct IDs fail. The shared escape identifier is sufficient for success, without distinguishing family composition. These source mappings await further native terminal acceptance. Unknown identifiers raise an explicit evidence error rather than receiving a guessed score. Native history snapshots that move a day or processed counter backwards are preserved and recorded as in-game state changes; they do not erase previously earned milestone points or interrupt the Trial. No actions are replayed and the total budget continues to run.
- The rubric is uncalibrated; historical non-thinking `deepseek-flash` results do not calibrate the new cohort.
- Native codec fixtures are synthetic and are not benchmark results; the real-process pause test covers process lifecycle only.
- Software rendering and API latency apply; initial preparation precedes the clock, later preparation, inference and retries consume it.

## Native evidence coverage

Daily transitions remove the temporary stash. The evaluator therefore preserves original encrypted daily story facts, active native statistics and settings using the shared `save` evidence kind, requiring the daily workday to match active statistics. Actual day-two evidence verified this path. Canonical-scoring regression coverage verifies four day milestones and append-only reassessment. Invalid active records are not silently treated as model failures. Synthetic lifecycle tests run the sole shared Trial workflow: bankruptcy restarts the LLM cohort with retained bounded observations and a persistent budget; the Jev cohort stops at first death. Synthetic fixtures are not model or native full-game acceptance results.
