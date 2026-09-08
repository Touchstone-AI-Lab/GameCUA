"""Generates a Harbor task package and job configuration for one Trial spec."""

import json
import shutil
from importlib.metadata import version
from pathlib import Path

from ..catalog import Catalog, digest
from ..environments.manager import IMAGE, ROOT, docker
from ..specs import TrialSpec
from ..storage import write_json
from . import INSTRUCTION, VERSION


def generate(spec_path, output, seconds=None, image=IMAGE):
    """Write a Harbor task package for one Trial spec at the given budget."""
    spec = TrialSpec.model_validate_json(Path(spec_path).read_text())
    catalog = Catalog(ROOT / "benchmarks")
    game = catalog.games[spec.game_id]
    seconds = 10800 if seconds is None else seconds
    spec = spec.model_copy(update={"total_seconds": float(seconds)})
    image_id = docker("image", "inspect", image, "--format", "{{.Id}}")
    inputs = {
        "game": game,
        "model": catalog.models[spec.model_id],
        "rubric": catalog.rubrics[spec.rubric_id],
        "trial": spec,
    }
    provenance = {
        "schema_version": 1,
        "game_id": game.id,
        "case_id": spec.id,
        "kind": "formal_budget" if seconds == 10800 else "smoke",
        "total_seconds": seconds,
        "harbor_version": VERSION,
        "harness_version": version("gamecua"),
        "image": image_id,
        "input_hashes": {k: digest(v) for k, v in inputs.items()},
    }
    identity = digest(provenance)
    provenance["identity"] = identity
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment, tests = output / "environment", output / "tests"
    environment.mkdir()
    tests.mkdir()
    configuration = environment / "configuration"
    for kind, name, value in (
        ("games", "game", game),
        ("models", "model", inputs["model"]),
        ("rubrics", "rubric", inputs["rubric"]),
        ("trials", "trial", spec),
    ):
        (configuration / kind).mkdir(parents=True, exist_ok=True)
        write_json(configuration / kind / f"{name}.json", value.model_dump(mode="json"))
    write_json(environment / "case.json", provenance)
    (output / "instruction.md").write_text(INSTRUCTION + "\n")
    (tests / "test.sh").write_text("#!/bin/sh\nset -eu\npython -m gamecua.harbor.verification\n")
    (tests / "test.sh").chmod(0o755)
    (output / "task.toml").write_text(f'''schema_version = "1.3"
[task]
name = "gamecua/{game.id}-{identity[:12]}"
[metadata]
identity = "{identity}"
kind = "{provenance["kind"]}"
game = "{game.id}"
[agent]
timeout_sec = {seconds + 180}
[verifier]
timeout_sec = 120
[environment]
docker_image = "{image_id}"
build_timeout_sec = 300
cpus = 2
memory_mb = 2048
''')
    return {"package": str(output), **provenance}


def job_config(package, bindings, output):
    from harbor.models.job.config import JobConfig

    package, bindings, output = (
        Path(package).resolve(),
        Path(bindings).resolve(),
        Path(output).resolve(),
    )
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    metric = output / "eligible_metric.py"
    shutil.copyfile(Path(__file__).with_name("metric.py"), metric)
    config = {
        "job_name": "execution",
        "jobs_dir": str(output),
        "n_concurrent_trials": 1,
        "n_attempts": 1,
        "retry": {"max_retries": 0},
        "agents": [
            {
                "import_path": "gamecua.harbor.bridge:GameAgent",
                "override_setup_timeout_sec": 360,
                "model_name": json.loads(
                    (package / "environment/configuration/models/model.json").read_text()
                )["id"],
            }
        ],
        "environment": {
            "import_path": "gamecua.harbor.bridge:GameEnvironment",
            "kwargs": {"bindings": str(bindings)},
        },
        "metrics": [{"type": "uv-script", "kwargs": {"script_path": str(metric)}}],
        "tasks": [{"path": str(package)}],
    }
    JobConfig.model_validate(config)
    write_json(output / "job.json", config)
    return output / "job.json"
