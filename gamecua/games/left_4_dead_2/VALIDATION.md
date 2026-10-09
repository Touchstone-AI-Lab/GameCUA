# Left 4 Dead 2 validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `left-4-dead-2-points-v1`, 60 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/left-4-dead-2/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** a new game, as described in `snapshots/left-4-dead-2/new.txt`.
- **Records:** `left-4-dead-2/` on the `v1-official-exp` branch.
- **Checks:** 12 offline tests in `tests/left_4_dead_2/` pass; rescoring all 12 recorded cells with this release reproduces their recorded scores.
