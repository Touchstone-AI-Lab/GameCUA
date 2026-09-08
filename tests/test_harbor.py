"""Harbor compatibility and failure tests use fixtures only, never benchmark claims."""

import asyncio
import json
from pathlib import Path

import pytest
from test_trials import add_episode, combat, completed, make_trial

from gamecua.catalog import digest
from gamecua.harbor import INSTRUCTION
from gamecua.harbor.metric import aggregate
from gamecua.harbor.verification import assess
from gamecua.storage import write_json


def test_missing_rewards_are_excluded_including_all_failed_job():
    assert aggregate([None, {"reward": 0.5}, {"reward": 0}]) == {
        "eligible_count": 2,
        "excluded_count": 1,
        "eligible_mean": 0.25,
    }
    assert aggregate([None, None]) == {"eligible_count": 0, "excluded_count": 2}


@pytest.mark.parametrize("status", ["completed", "interrupted", "cancelled"])
def test_verifier_preserves_points_without_rewarding_partial_trials(tmp_path, status):
    trial = make_trial(tmp_path / "trial")
    add_episode(trial, "episode-001", [("save", combat(), 1)])
    completed(trial)
    if status != "completed":
        trial.finish(status, "signal_interruption")
    result = assess(trial.root, tmp_path / "verifier", tmp_path / "portable")
    assert result["score"] == 10
    assert (tmp_path / "verifier/reward.txt").exists() == (status == "completed")
    if status == "completed":
        assert float((tmp_path / "verifier/reward.txt").read_text()) == 0.1
    assert not (tmp_path / "portable/runtime.local.json").exists()


def test_unscoreable_trial_removes_previous_reward(tmp_path):
    output = tmp_path / "verifier"
    output.mkdir()
    (output / "reward.txt").write_text("1")
    result = assess(tmp_path / "missing", output)
    assert not result["scoreable"] and not result["comparison_eligible"]
    assert not (output / "reward.txt").exists()


def test_task_is_loadable_and_does_not_include_hidden_instruction(tmp_path, monkeypatch):
    pytest.importorskip("harbor")
    from harbor.models.task.task import Task

    from gamecua.harbor import packages

    monkeypatch.setattr(packages, "docker", lambda *args: "sha256:offline-test-image")
    output = tmp_path / "package"
    result = packages.generate(
        Path(packages.ROOT) / "tests/fixtures/catalog/trials/sts-victory-v3-live-3h.json", output
    )
    task = Task(output)
    assert task.instruction.strip() == INSTRUCTION
    assert task.config.agent.timeout_sec == 10980
    assert result["total_seconds"] == 10800 and result["kind"] == "formal_budget"
    assert not (output / "solution").exists()
    assert (output / "tests/test.sh").stat().st_mode & 0o111
    case = json.loads((output / "environment/case.json").read_text())
    assert case["identity"] == result["identity"]


def test_model_has_no_shell_access():
    pytest.importorskip("harbor")
    from gamecua.harbor.bridge import GameEnvironment

    environment = object.__new__(GameEnvironment)
    environment.model_active = True
    with pytest.raises(PermissionError):
        asyncio.run(environment.exec("cat /snapshot/state"))


def test_job_disables_retry_and_default_zero_imputing_metric(tmp_path, monkeypatch):
    pytest.importorskip("harbor")
    from gamecua.harbor import packages

    monkeypatch.setattr("harbor.models.task.task.Task", lambda _: None)
    model = tmp_path / "package/environment/configuration/models/model.json"
    model.parent.mkdir(parents=True)
    write_json(model, {"id": "deepseek-flash"})
    path = packages.job_config(tmp_path / "package", tmp_path / "binding", tmp_path / "job")
    config = json.loads(path.read_text())
    assert config["retry"]["max_retries"] == 0
    assert config["n_attempts"] == 1
    assert config["metrics"][0]["type"] == "uv-script"
    assert "env" not in config["agents"][0]


def test_case_identity_changes_with_budget():
    assert digest({"budget": 90}) != digest({"budget": 10800})


def test_gameplay_gate_waits_without_charging_budget(tmp_path):
    import threading
    from types import SimpleNamespace

    trial = make_trial(tmp_path / "trial")
    trial.start_gate = tmp_path / "start"
    trial.backend = SimpleNamespace(prepare=lambda *args: {"verified": True}, checkpoint=lambda: {})
    worker = threading.Thread(target=trial.episode)
    worker.start()
    try:
        for _ in range(100):
            if trial.start_gate.with_suffix(".ready").exists():
                break
            threading.Event().wait(0.01)
        assert trial.start_gate.with_suffix(".ready").exists()
        assert trial.state["started_at"] is None
        assert trial.budget.remaining() == trial.spec.total_seconds
        trial.start_gate.touch()
        worker.join(2)
        assert not worker.is_alive()
        assert trial.state["started_at"] is not None
    finally:
        trial.stop.set()
        worker.join(2)


def test_absolute_provider_deadline_cancels_slow_response(monkeypatch):
    import httpx

    from gamecua.catalog import Catalog
    from gamecua.models import CompatibleClient

    spec = Catalog(Path(__file__).resolve().parents[1] / "benchmarks").models["deepseek-flash"]
    monkeypatch.setenv(spec.api_key_env, "offline-test")
    cancelled = []

    async def slow(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    client = CompatibleClient(
        spec, http_client=httpx.AsyncClient(transport=httpx.MockTransport(slow))
    )
    with pytest.raises(TimeoutError):
        client.complete({"model": spec.model, "messages": []}, timeout=0.02)
    assert cancelled == [True]
    asyncio.run(client.http.aclose())


def test_provider_cancellation_closes_inflight_request(monkeypatch):
    import threading

    import httpx

    from gamecua.catalog import Catalog
    from gamecua.models import CompatibleClient

    spec = Catalog(Path(__file__).resolve().parents[1] / "benchmarks").models["deepseek-flash"]
    monkeypatch.setenv(spec.api_key_env, "offline-test")
    stop = threading.Event()
    cancelled = []

    async def slow(request):
        stop.set()
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    client = CompatibleClient(
        spec, http_client=httpx.AsyncClient(transport=httpx.MockTransport(slow))
    )
    with pytest.raises(TimeoutError, match="cancelled"):
        client.complete({"model": spec.model, "messages": []}, timeout=10, cancel=stop)
    assert cancelled == [True]
    asyncio.run(client.http.aclose())
