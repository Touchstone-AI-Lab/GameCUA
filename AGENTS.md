# Repository conventions

Contributors are TouchStone AI researchers, each owning one claimed game from the README roster.

- Keep work for a claimed game inside its game-scoped locations. Do not change the core (shared files outside them); solve problems in the game layer first. For a real core problem the game layer cannot work around, open an issue with evidence and a reproduction, and message Zhuhan Bao directly. Change the core only after they agree.
- Write all repository code, comments, documentation, task definitions, schemas, fixtures, and benchmark artifacts in English.
- Keep game integration, trial configurations, model transport, execution and native-evidence scoring separate.
- Never send evaluator-only task goals or setup state to the no-rules agent during play; only the separate pre-run interview (`interview.py`) may describe the rubric.
- Do not promote templates or synthetic test fixtures to real benchmark results.
- Do not count interrupted segments as independent episodes or model terminal claims as verified wins.
- Keep API keys in environment variables or ignored local configuration; never include them in exported artifacts.
- After changing contracts, regenerate schemas with `python scripts/export_schemas.py`.
- Validate changes with `python -m pytest -q` and `python -m gamecua.cli validate`.
- Keep demos on `main` under `experiments/<game-id>/demo/`. Final cell records live on the `v1-official-exp` branch, which never merges into `main`; starting states live in `snapshots/<game-id>/<snapshot>/`.
- Keep personal deployment and campaign scripts in ignored local storage; share reusable game integration in the game modules.
- Put game-specific adapters, setup, and evaluators under `gamecua/games/<game_module>/`; game configurations, rubrics and trial specs under `benchmarks/{games,rubrics,trials}/<game-id>/`; fixtures under game-named directories. Keep only `scripts/export_schemas.py` and `scripts/check_repository_layout.py` as shared scripts.
- Allow only one comment line at the top of a code file and one at the head of a function, method or class (a one-line docstring in Python); no other comments.
- Use the shared OpenAI-compatible model transport for language models and the native typed-choice transport for Jev; configure providers through model specs and environment variables.
- Keep repository Markdown documentation limited to the root `README.md`, `AGENTS.md` and `VALIDATION.md`, plus exactly two files per game module: `gamecua/games/<game_module>/README.md` (the game guide) and `gamecua/games/<game_module>/VALIDATION.md` (its dated validation record), and `snapshots/README.md` with one `README.md` per starting state (`snapshots/<game-id>/<snapshot>/README.md`). The root README holds only shared content and one guide link per game; the root VALIDATION holds only shared harness, environment and release records. `scripts/check_repository_layout.py` rejects any other Markdown file.
- Every game declares its budget form and runs the language-model cohort (one life within 3 h in every game) and the Jev cohort (`jev-1-14`: one attempt within 2 h for attempt games, or 1 h for time games) on one shared input profile, scores with at least ten milestones of at most 10 points that each help to win, and supplies an interview brief; follow the onboarding checklist in `README.md`. Preserve historical model attribution.
- Keep trial, episode and segment identities separate. Persist the total budget, freeze the rubric, and never replay uncertain actions or grant recovery extra time beyond the provider timeout credit of `freeze_retry_timeout_credit`.
- Score only preserved game evidence; record experiment failures separately from model scores. Keep mutable native process output outside exported evidence.
- Keep `trials.py` as the sole execution workflow. Do not reintroduce retired episode runners, attach resets or seed-matrix execution. Preserve historical evidence as read-only artifacts.
- Independent trials start with empty agent context; death inherits bounded same-model summarized knowledge within the same trial, while recovery remains in its original episode. Preserve the exact inherited context without exposing evaluator state.
- Keep earned milestone points separate from scoreability, completion and comparison eligibility. Exclude incomplete trials from aggregate comparisons; score files are appended, never edited.
- Steam games require official clients and the researcher's own licensed account. Never substitute operator controls for autonomous benchmark evidence.
