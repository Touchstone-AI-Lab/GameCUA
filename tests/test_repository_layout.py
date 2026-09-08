import importlib.util
from pathlib import Path

import pytest

from gamecua.models import CompatibleClient, create_client
from gamecua.specs import ModelSpec

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("provider", ["together", "openai_compatible"])
def test_provider_labels_use_shared_transport(provider):
    spec = ModelSpec(
        id="transport-fixture",
        provider=provider,
        model="vision-fixture",
        base_url="https://service.invalid/v1",
        api_key_env="TEST_PROVIDER_KEY",
    )
    client = create_client(spec)
    assert isinstance(client, CompatibleClient)
    client.close()


def test_main_rejects_formal_results(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "repository_layout", ROOT / "scripts/check_repository_layout.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: "")
    (tmp_path / "experiments/slay-the-spire/demo").mkdir(parents=True)
    assert module.validate_layout(tmp_path, "main") == []
    (tmp_path / "experiments/slay-the-spire/formal-campaign").mkdir()
    assert "Only demos" in module.validate_layout(tmp_path, "main")[0]
    assert module.validate_layout(tmp_path, "experiments") == []


@pytest.mark.parametrize(
    ("base", "head", "allowed"),
    [("experiments", "results/sts2-a10-paired", True), ("main", "experiments", False)],
)
def test_result_pull_requests_validate_the_destination(tmp_path, monkeypatch, base, head, allowed):
    spec = importlib.util.spec_from_file_location(
        "repository_layout", ROOT / "scripts/check_repository_layout.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: "")
    monkeypatch.setenv("GITHUB_BASE_REF", base)
    monkeypatch.setenv("GITHUB_HEAD_REF", head)
    monkeypatch.setenv("GITHUB_REF_NAME", "102/merge")
    (tmp_path / "experiments/slay-the-spire-2/formal-paired").mkdir(parents=True)
    if allowed:
        module.main()
    else:
        with pytest.raises(SystemExit, match="Only demos belong in experiments/ on main"):
            module.main()
