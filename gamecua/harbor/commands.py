"""The harbor-* commands that package a Trial and run it as a Harbor job."""

import asyncio
import json
from pathlib import Path

from ..storage import write_json
from .packages import generate, job_config


def add_commands(commands):
    package = commands.add_parser("harbor-package")
    package.add_argument("--trial-spec", type=Path, required=True)
    package.add_argument("--snapshot", type=Path, required=True)
    package.add_argument("--installation", type=Path, required=True)
    package.add_argument("--steam-environment", type=Path)
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--seconds", type=float)
    for name in ("harbor-run", "harbor-config"):
        run = commands.add_parser(name)
        run.add_argument("--package", type=Path, required=True)
        run.add_argument("--bindings", type=Path, required=True)
        run.add_argument("--output", type=Path, required=True)


def execute(args):
    if args.command == "harbor-package":
        result = generate(args.trial_spec, args.output, args.seconds)
        binding = Path(result["package"]).with_suffix(".bindings.local.json")
        write_json(
            binding,
            {
                "identity": result["identity"],
                "installation": str(args.installation.resolve()),
                "snapshot": str(args.snapshot.resolve()),
                "steam_environment": str(args.steam_environment.resolve())
                if args.steam_environment
                else None,
            },
        )
        binding.chmod(0o600)
        return {
            "package": result["package"],
            "bindings": str(binding),
            "identity": result["identity"],
            "kind": result["kind"],
        }
    configuration = job_config(args.package, args.bindings, args.output)
    if args.command == "harbor-config":
        return {"configuration": str(configuration)}
    from harbor.job import Job
    from harbor.models.job.config import JobConfig

    async def run():
        job = await Job.create(JobConfig.model_validate_json(configuration.read_text()))
        return await job.run()

    result = asyncio.run(run())
    return {
        "configuration": str(configuration),
        "statistics": result.stats.model_dump(mode="json"),
        "results": str(args.output.resolve() / "execution/result.json"),
        "kind": json.loads((args.package / "environment/case.json").read_text())["kind"],
    }
