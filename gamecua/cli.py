"""Command line for catalog checks, Trials, scoring, game setup helpers, environments and Harbor."""

import argparse
import json
import os
from datetime import datetime, timezone
from functools import partial
from importlib import import_module
from pathlib import Path

from .catalog import Catalog
from .evidence import export, score
from .specs import TrialSpec
from .trials import Trial, run_series

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    path = Path.cwd() / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())


def parser():
    cli = argparse.ArgumentParser(
        description="Fixed-budget, evidence-backed game trials", allow_abbrev=False
    )
    cli.add_argument("--catalog", type=Path, default=ROOT / "benchmarks")
    commands = cli.add_subparsers(
        dest="command",
        required=True,
        parser_class=partial(argparse.ArgumentParser, allow_abbrev=False),
    )
    for name in ("catalog", "validate"):
        commands.add_parser(name, help="Validate and list current configurations")
    snapshot = commands.add_parser("snapshot-sts", help="Read-only capture of a prepared STS save")
    snapshot.add_argument("--encounter", required=True)
    snapshot.add_argument("--output", type=Path, required=True)
    snapshot.add_argument("--installation", type=Path)
    stardew = commands.add_parser(
        "snapshot-stardew", help="Read-only capture of a prepared Stardew Valley save profile"
    )
    stardew.add_argument("--source", type=Path, required=True)
    stardew.add_argument("--output", type=Path, required=True)
    isaac = commands.add_parser(
        "snapshot-isaac", help="Create a zero-progression fixed-seed Isaac snapshot"
    )
    isaac.add_argument("--installation", type=Path)
    isaac.add_argument("--output", type=Path, required=True)
    isaac.add_argument("--seed")
    silksong = commands.add_parser(
        "snapshot-silksong", help="Read-only capture of a prepared Silksong save profile"
    )
    silksong.add_argument("--source", type=Path, required=True)
    silksong.add_argument("--output", type=Path, required=True)
    silksong.add_argument("--installation", type=Path)
    for name in ("trial", "series"):
        command = commands.add_parser(name, help="Execute new independent fixed-budget trials")
        command.add_argument("--trial-spec", type=Path, required=True)
        command.add_argument("--snapshot", type=Path, required=True)
        command.add_argument("--installation", type=Path)
        command.add_argument("--output", type=Path)
        command.add_argument("--seconds", type=float)
        command.add_argument("--start-gate", type=Path)
        if name == "series":
            command.add_argument("--repeats", type=int, choices=range(1, 21), default=2)
    for name in ("resume-trial", "score-trial", "export-trial"):
        command = commands.add_parser(name)
        command.add_argument("--run-dir", type=Path, required=True)
        if name == "export-trial":
            command.add_argument("--output", type=Path, required=True)
        if name == "score-trial":
            command.add_argument("--episode-limit", type=int)
    from .environments.commands import add_commands

    add_commands(commands)
    from .harbor.commands import add_commands as add_harbor_commands

    add_harbor_commands(commands)
    return cli


def execute(args):
    if args.command.startswith("harbor-"):
        from .harbor.commands import execute as execute_harbor

        return execute_harbor(args)
    if args.command.startswith("env-"):
        from .environments.commands import execute_environment

        return execute_environment(args)
    if args.command in ("catalog", "validate"):
        catalog = Catalog(args.catalog)
        result = {
            kind: [
                {"id": x.id, "status": getattr(x, "status", "configured")}
                for x in getattr(catalog, kind).values()
            ]
            for kind in ("games", "models", "rubrics", "trials")
        }
        if args.command == "validate" and catalog.pause_gaps():
            result["pause_gaps"] = catalog.pause_gaps()
        return result
    if args.command == "snapshot-isaac":
        from .games.the_binding_of_isaac_rebirth.setup import (
            DEFAULT_SEED,
            create_snapshot,
            default_installation,
        )

        return str(
            create_snapshot(
                args.installation or default_installation(), args.output, args.seed or DEFAULT_SEED
            )
        )
    if args.command == "snapshot-sts":
        from .games.slay_the_spire.integration import capture_snapshot
        from .games.slay_the_spire.setup import default_game_dir

        return str(
            capture_snapshot(args.installation or default_game_dir(), args.output, args.encounter)
        )
    if args.command == "snapshot-stardew":
        from .games.stardew_valley.setup import capture_snapshot as capture_stardew

        return str(capture_stardew(args.source, args.output))
    if args.command == "snapshot-silksong":
        from .games.hollow_knight_silksong.setup import capture_snapshot as capture_silksong
        from .games.hollow_knight_silksong.setup import default_installation

        return str(
            capture_silksong(args.source, args.installation or default_installation(), args.output)
        )
    if args.command == "score-trial":
        path, result = score(args.run_dir, args.episode_limit)
        return {"output": str(path), **result}
    if args.command == "export-trial":
        return str(export(args.run_dir, args.output))
    load_env()
    if args.command == "resume-trial":
        trial = Trial(args.run_dir)
        support = import_module(f"gamecua.games.{trial.spec.game_id.replace('-', '_')}.integration")
        trial.backend = support.Backend(trial.root)
        return trial.run()
    values = json.loads(args.trial_spec.read_text())
    if args.seconds is not None:
        values["total_seconds"] = args.seconds
    spec = TrialSpec.model_validate(values)
    catalog = Catalog(args.catalog)
    support = import_module(f"gamecua.games.{spec.game_id.replace('-', '_')}.integration")

    def create(root):
        trial = Trial(
            root,
            spec,
            catalog.rubrics[spec.rubric_id],
            catalog.games[spec.game_id],
            catalog.models[spec.model_id],
            start_gate=args.start_gate,
            inputs=catalog.inputs.get(spec.inputs_id),
            interview=True,
        )
        trial.backend = support.Backend(trial.root, args.snapshot, args.installation)
        return trial

    root = args.output or ROOT / "runs" / spec.game_id / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    if args.command == "series":
        return run_series(root, args.repeats, create)
    return {"directory": str(root), **create(root).run()}


def main():
    print(json.dumps(execute(parser().parse_args()), indent=2))


if __name__ == "__main__":
    main()
