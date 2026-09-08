"""Repository hygiene: the demo bundle holds no credentials, schemas match contracts and authored text is English."""

import json
import re
from pathlib import Path

import pytest

from gamecua.specs import GameSpec, Milestone, ModelSpec, Rubric, TrialRecord, TrialSpec

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "experiments"


def test_bundle_contains_no_credential_files_or_key_prefixes():
    for path in BUNDLE.rglob("*"):
        if path.is_file():
            assert path.name != ".env"
            if path.suffix in (".json", ".jsonl", ".txt", ".html", ".md"):
                assert "tgp_v1_" not in path.read_text()


def test_published_schemas_match_contracts():
    for schema in (GameSpec, ModelSpec, Milestone, Rubric, TrialSpec, TrialRecord):
        path = ROOT / "benchmarks/schemas" / (schema.__name__ + ".schema.json")
        assert json.loads(path.read_text()) == schema.model_json_schema()


def authored_text_paths(root):
    archived_trials = {
        path.parent
        for path in (root / "experiments").rglob("trial.spec.json")
        if all(
            (path.parent / name).is_file() for name in ("trial.json", "model.json", "rubric.json")
        )
    }
    for directory in (
        "gamecua",
        "benchmarks",
        "experiments",
        "configs",
        "tests",
        "scripts",
    ):
        for path in (root / directory).rglob("*"):
            if path.is_file() and path.suffix in (
                ".py",
                ".md",
                ".json",
                ".jsonl",
                ".html",
                ".toml",
                ".txt",
            ):
                if (
                    directory == "experiments"
                    and path.suffix in (".json", ".jsonl")
                    and archived_trials.intersection(path.parents)
                ):
                    continue
                yield path


def test_repository_authored_text_is_english():
    for path in authored_text_paths(ROOT):
        assert not re.search(r"[\u3400-\u9fff]", path.read_text()), str(path)
    for name in ("README.md", "AGENTS.md", "VALIDATION.md"):
        assert not re.search(r"[\u3400-\u9fff]", (ROOT / name).read_text()), name


def test_english_guard_preserves_original_trial_json(tmp_path):
    trial = tmp_path / "experiments/slay-the-spire-2/campaign/trial"
    trial.mkdir(parents=True)
    for name in ("trial.spec.json", "trial.json", "model.json", "rubric.json"):
        (trial / name).write_text("{}")
    output = trial / "episodes/episode-001/segments/segment-001/00001.json"
    output.parent.mkdir(parents=True)
    raw = json.dumps({"observation": chr(0x4E2D) + chr(0x6587)}, ensure_ascii=False).encode()
    output.write_bytes(raw)
    assert output not in set(authored_text_paths(tmp_path))
    assert output.read_bytes() == raw


@pytest.mark.parametrize("kind", ["delivery", "guide", "incomplete_trial"])
def test_english_guard_still_checks_authored_experiment_text(tmp_path, kind):
    folder = tmp_path / "experiments/slay-the-spire-2/campaign"
    folder.mkdir(parents=True)
    for name in ("trial.spec.json", "trial.json", "model.json", "rubric.json"):
        if kind != "incomplete_trial" or name == "trial.json":
            (folder / name).write_text("{}")
    path = folder / "README.md" if kind == "guide" else folder.parent / "delivery.json"
    if kind == "incomplete_trial":
        path = folder / "00001.json"
    path.write_text(chr(0x4E2D) + chr(0x6587), encoding="utf-8")
    assert path in set(authored_text_paths(tmp_path))
    assert re.search(r"[\u3400-\u9fff]", path.read_text(encoding="utf-8"))
