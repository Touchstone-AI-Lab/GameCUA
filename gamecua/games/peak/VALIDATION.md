# PEAK validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `peak-ascent-points-v1`, 100 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/peak/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** a new game, as described in `snapshots/peak/new.txt`.
- **Records:** `peak/` on the `v1-official-exp` branch.
- **Checks:** 40 offline tests in `tests/peak/` pass; rescoring all 12 recorded cells with this release reproduces their recorded scores.
