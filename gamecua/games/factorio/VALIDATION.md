# Factorio validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `factorio-bootstrap-v4`, 100 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/factorio/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** `snapshots/factorio/deathworld-marathon-2.1.24-seed12345-v1/`.
- **Records:** `factorio/` on the `v1-official-exp` branch.
- **Checks:** 23 offline tests in `tests/factorio/` pass; rescoring all 12 recorded cells with this release reproduces their recorded scores.
