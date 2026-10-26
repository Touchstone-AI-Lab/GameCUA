# Hollow Knight: Silksong validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `hollow-knight-silksong-points-v1`, 52 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/hollow-knight-silksong/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** `snapshots/hollow-knight-silksong/moss-start-v5/`.
- **Records:** `hollow-knight-silksong/` on the `v1-official-exp` branch.
- **Checks:** 25 offline tests in `tests/hollow_knight_silksong/` pass; rescoring all 12 recorded cells with this release reproduces their recorded scores.
