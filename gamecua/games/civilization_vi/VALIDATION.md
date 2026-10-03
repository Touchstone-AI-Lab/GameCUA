# Sid Meier's Civilization VI validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `civilization-vi-base-development-v1`, 52 milestones, 100 points.
- **Trial specs:** 6 in `benchmarks/trials/civilization-vi/` (5 language model, 1 Jev; 6 live).
- **Starting state:** `snapshots/civilization-vi/standard-aztec-prince-20261112-v1/`.
- **Records:** `civilization-vi/` on the `v1-official-exp` branch.
- **Checks:** 33 offline tests in `tests/civilization_vi/` pass; rescoring all 6 recorded cells with this release reproduces their recorded scores.
