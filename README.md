# GameCUA

A benchmark of verified progress in commercial games, played from screenshots with ordinary keyboard and mouse input within one fixed wall-clock budget. Shared validation is in [VALIDATION](VALIDATION.md); each game's guide and validation record live next to its code.

## Games

### V1

The 15 games of the GameCUA V1 paper.

| Game | Contributors | Category | Guide |
| --- | --- | --- | --- |
| Slay the Spire | [Zhuhan Bao](https://github.com/BaoZhuhan), [Sihan Xu](https://github.com/SihanXU) | Card strategy | [guide](gamecua/games/slay_the_spire/README.md) |
| Baba Is You | [Danni Luo](https://github.com/DanniLuo1) | Rule puzzle | [guide](gamecua/games/baba_is_you/README.md) |
| Understand | [Jiawen Bao](https://github.com/BBbb26) | Rule puzzle | [guide](gamecua/games/understand/README.md) |
| Civilization VI | [Yichi Chen](https://github.com/YiChiChen1106) | 4X strategy | [guide](gamecua/games/civilization_vi/README.md) |
| Factorio | [Rui Hu](https://github.com/MatchalatteR) | Factory automation | [guide](gamecua/games/factorio/README.md) |
| Oxygen Not Included | [Zhuoran Yin](https://github.com/PrinsYin) | Colony management | [guide](gamecua/games/oxygen_not_included/README.md) |
| Stardew Valley | [Jianing Ma](https://github.com/CoderMaurice) | Farming simulation | [guide](gamecua/games/stardew_valley/README.md) |
| Papers, Please | [Mengjiao Liu](https://github.com/MiraJLiu) | Document inspection | [guide](gamecua/games/papers_please/README.md) |
| Untitled Goose Game | [Mengyao Wen](https://github.com/yaoxiaobai-hub) | Stealth puzzle | [guide](gamecua/games/untitled_goose_game/README.md) |
| PEAK | [Guobin Zhang](https://github.com/GreyJohnny) | Physics climbing | [guide](gamecua/games/peak/README.md) |
| Don't Starve | [Wenze Cui](https://github.com/wz-2002) | Survival and crafting | [guide](gamecua/games/dont_starve/README.md) |
| Hollow Knight: Silksong | [Tongfei Wang](https://github.com/Wang-Tongfei) | Metroidvania | [guide](gamecua/games/hollow_knight_silksong/README.md) |
| The Binding of Isaac: Rebirth | [Changyi Yang](https://github.com/ChangyiYang) | Action roguelike | [guide](gamecua/games/the_binding_of_isaac_rebirth/README.md) |
| Left 4 Dead 2 | [Zhuhan Bao](https://github.com/BaoZhuhan) | Cooperative FPS | [guide](gamecua/games/left_4_dead_2/README.md) |
| art of rally | [Qifeng Chen](https://github.com/QifengChen-007) | Rally racing | [guide](gamecua/games/art_of_rally/README.md) |

### V2

Games integrated for the next release; they are not in the V1 paper, and their integrations are not in this repository yet.

| Game | Contributors | Category |
| --- | --- | --- |
| Celeste | [Shenyi Wang](https://github.com/eason241008), [Zhuhan Bao](https://github.com/BaoZhuhan) | Precision platformer |
| Slay the Spire 2 | [Guobin Zhang](https://github.com/GreyJohnny) | Card strategy |
| SUPERHOT | [Yunta Hsieh](https://github.com/Kiky-88) | Tactical FPS |
| Valheim | [Ruoyu He](https://github.com/dyyfk) | Open-world survival |
| Balatro | [Muhammad Khaquan](https://github.com/KhaquanS) | Card strategy |
| Vampire Crawlers | [Omer Tafveez](https://github.com/omertafveez-2001) | Dungeon crawler |

Core harness: [Zhuhan Bao](https://github.com/BaoZhuhan), [Xingzhi Li](https://github.com/moeleak), [Sihan Xu](https://github.com/SihanXU), [Hui Shen](https://github.com/killthefullmoon), [Yunta Hsieh](https://github.com/Kiky-88).

## Protocol

- **Cohorts.** Each game is played by language models and by Jev (`jev-1-14`) on one shared input profile. Real-time games run both `live` and `frozen_steps` (the game is paused while the agent decides); turn-based games run live.
- **Budgets.** A language model gets one life within 3 hours; Jev gets one hour and ends at its first death. Inference, retries, inputs and downtime all consume the budget. Scoring counts only evidence inside the budget, plus the recorded provider timeout credit of `freeze_retry_timeout_credit`.
- **Scoring.** Each game has one 100-point rubric of fine-grained milestones, earned once per Trial from preserved native game evidence (saves, statistics, evaluator records), never from model claims.
- **Privacy.** During play the agent sees only screenshots, its own notes, recent actions and the controls reference. Before the clock starts, a separate interview asks the language model for its expectations.
- **Context.** Independent Trials start empty. A death carries the model's own summary into the next episode; recovery keeps its episode and never replays uncertain actions.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install -e . --no-deps
cp .env.example .env && chmod 600 .env
```

Model keys go in `.env` under the variable each spec in `benchmarks/models/` names (for example `DEEPSEEK_API_KEY`, `TYPESAFE_API_KEY`). Formal Trials run in an isolated Linux container with a private X11 display and a read-only noVNC observer:

```bash
docker pull ghcr.io/touchstone-ai-lab/gamecua-environment:0.7.14
docker tag ghcr.io/touchstone-ai-lab/gamecua-environment:0.7.14 gamecua-environment:0.7.14
```

The image holds the harness, not game installations, Steam state or keys; `env-build` rebuilds it. Steam games use `env-create --steam` and `env-steam-prepare --app-id <id>` (Steam Mobile QR sign-in). Renderers: software by default, `--renderer nvidia --gpu <index>`, or `--renderer wsl-d3d12 --gpu <adapter>`.

## Running Trials

```bash
.venv/bin/python -m gamecua.cli validate
.venv/bin/python -m gamecua.cli trial --trial-spec benchmarks/trials/<game-id>/<spec>.json --snapshot <snapshot> --installation <installation> --output runs/<game-id>/trial-001
.venv/bin/python -m gamecua.cli score-trial --run-dir runs/<game-id>/trial-001
.venv/bin/python -m gamecua.cli export-trial --run-dir runs/<game-id>/trial-001 --output runs/<game-id>/portable-001
```

Inside a container use `env-create` and `env-trial`. `resume-trial` continues an interrupted Trial within its original deadline, and a `STOP` file in the Trial folder ends it (a Jev Trial stopped this way is scored as completed with `manual_stop: true`). `score-trial --episode-limit 1` scores only the first life of an older multi-episode Trial. Use `COMMAND --help` for arguments.

## Records

`benchmarks/trials/` holds the 156 Trial specs of the paper and `benchmarks/rubrics/` the current rubric of each game. The final record of every cell is on the `v1-official-exp` branch, a slim copy of the Hugging Face dataset `Zhuhan/GameCUA-V1-Exp`; the starting state of every cell is in [`snapshots/`](snapshots/README.md). The `v1-official-exp` branch does not merge into `main`.

## Contributing

A game lives in `gamecua/games/<game_module>/` (`integration.py`, `setup.py`, `progress.py`, `README.md`, `VALIDATION.md`), with its configuration in `benchmarks/{games,inputs,rubrics,trials}/<game-id>/` and tests in `tests/<game_module>/`. Keep game logic out of the shared harness; core changes need Zhuhan Bao's agreement. Before pushing:

```bash
.venv/bin/python scripts/export_schemas.py
.venv/bin/python -m pytest -q
.venv/bin/python -m gamecua.cli validate
.venv/bin/python scripts/check_repository_layout.py
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## Harbor

Harbor 0.23.0 is optional (`pip install "harbor==0.23.0" "uv==0.12.19"`). It runs one game container per Trial through the normal CLI; only eligible Trials report `reward = points / rubric maximum`.

```bash
.venv/bin/python -m gamecua.cli harbor-package --trial-spec <spec.json> --installation <installation> --snapshot <snapshot> --output build/harbor/<case>
.venv/bin/python -m gamecua.cli harbor-run --package build/harbor/<case> --bindings build/harbor/<case>.bindings.local.json --output runs/harbor/<case>
```
