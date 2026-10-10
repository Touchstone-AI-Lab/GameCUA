# art of rally validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `art-of-rally-five-stage-checkpoints-v9`, 100 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/art-of-rally/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** `snapshots/art-of-rally/v8-five-stage-720p-start-split-v1/`.
- **Records:** `art-of-rally/` on the `v1-official-exp` branch.
- **Checks:** 49 offline tests in `tests/art_of_rally/` pass; the release scorer and the previous scorer give identical V9 results on four recorded Trials; the native telemetry these cells score from is not part of the slim records.
