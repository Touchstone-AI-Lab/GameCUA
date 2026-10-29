# Untitled Goose Game validation

## 2026-11-22: version 1.0.0 released

- **Version:** 1.0.0, released on harness `gamecua` 0.7.14.
- **Rubric:** `untitled-goose-game-native-tasks-v5`, 32 milestones, 100 points.
- **Trial specs:** 12 in `benchmarks/trials/untitled-goose-game/` (10 language model, 2 Jev; 6 frozen, 6 live).
- **Starting state:** a new game, as described in `snapshots/untitled-goose-game/new.txt`.
- **Records:** `untitled-goose-game/` on the `v1-official-exp` branch.
- **Checks:** 9 offline tests in `tests/untitled_goose_game/` pass; rescoring all 12 recorded cells with this release reproduces their recorded scores.
