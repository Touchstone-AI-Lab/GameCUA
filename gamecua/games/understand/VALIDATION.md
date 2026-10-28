# Understand validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `understand-route-panels-v4`, 100 milestones, 100 points.
- **Trial specs:** 6 in `benchmarks/trials/understand/` (5 language model, 1 Jev; 6 live).
- **Starting state:** `snapshots/understand/frozen-zero-progress-001/`, `snapshots/understand/zero-progress-1c84b437a573/`, `snapshots/understand/zero-progress-31a3acc95951/`, `snapshots/understand/zero-progress-c88a32950333/`.
- **Records:** `understand/` on the `v1-official-exp` branch.
- **Checks:** 36 offline tests in `tests/understand/` pass; rescoring the recorded cells needs the installed game, because panel assessment runs the game's own Lua; it was not run on the release host.
