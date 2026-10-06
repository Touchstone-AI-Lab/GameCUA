# Stardew Valley validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `stardew-early-game-v1`, 100 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/stardew-valley/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** `snapshots/stardew-valley/snapshot-spring2/`.
- **Records:** `stardew-valley/` on the `v1-official-exp` branch.
- **Checks:** 54 offline tests in `tests/stardew_valley/` pass; rescoring all 12 recorded cells with this release reproduces their recorded scores.
