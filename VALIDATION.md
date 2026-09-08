# GameCUA validation

## 2026-11-22: version 1.0.0 released

- **Scope:** 15 games, each at version 1.0.0, with one current rubric per game and the 156 Trial specs of the paper in `benchmarks/trials/`.
- **Harness:** `gamecua` 0.7.14. Image `ghcr.io/touchstone-ai-lab/gamecua-environment:0.7.14` (`sha256:993072868562abbd59c5a6364c8d3687fa4b55a99a1a7e7d28d3e10b6d1e1e39`), built from `main` at `1ea58d899`; its `gamecua/` and `benchmarks/` files are byte-identical to that commit.
- **Checks:** the full offline suite passes (797 passed, 5 skipped because they need mono or Lua). `ruff check`, `ruff format --check`, `python -m gamecua.cli validate` and `scripts/check_repository_layout.py` pass.
- **Rescoring:** the recorded cells of 13 games (144 cells) were rescored with this release under the current rubrics. All 138 that can be scored on the release host reproduce their recorded scores; the 6 Understand cells need the installed game. art of rally was checked separately on four recorded Trials.
- **Records:** the final record of every cell is on the `v1-official-exp` branch, a slim copy of the Hugging Face dataset `Zhuhan/GameCUA-V1-Exp`. Every cell's starting state is in `snapshots/`.
