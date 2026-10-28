# Papers, Please validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `papers-please-story-v9`, 51 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/papers-please/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** `snapshots/papers-please/fresh-story-1.4.11.124/`.
- **Records:** `papers-please/` on the `v1-official-exp` branch.
- **Checks:** 31 offline tests in `tests/papers_please/` pass; rescoring all 12 recorded cells with this release reproduces their recorded scores.
