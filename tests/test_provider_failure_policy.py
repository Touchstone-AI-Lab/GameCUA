"""The freeze_retry_timeout_credit policy: fake slow and failing providers, the charged clock and the scorer's evidence cap."""

import json
import threading
from types import SimpleNamespace

import pytest
from test_trials import (
    CATALOG,
    FakeBackend,
    FakeRecorder,
    InterruptedAgent,
    add_episode,
    combat,
    make_trial,
)

from gamecua.evidence import effective_deadline, score, time_allowance
from gamecua.provider import (
    InvalidDecision,
    InvalidResponse,
    ProviderFailure,
    RetryPolicy,
    with_retries,
)
from gamecua.provider_recovery import (
    BACKOFF,
    ProviderRecovery,
    ProviderTerminal,
    refresh_key,
)
from gamecua.specs import ProviderLedger, TrialRecord, TrialSpec
from gamecua.storage import write_json
from gamecua.trials import Budget, Trial

POLICY = "freeze_retry_timeout_credit"


@pytest.fixture
def harness(monkeypatch, tmp_path):
    ticks = [1000.0]
    monkeypatch.setattr("gamecua.provider_recovery.time.monotonic", lambda: ticks[0])
    monkeypatch.setattr("gamecua.provider_recovery.time.time", lambda: ticks[0])
    state = TrialRecord(id="recovery-test").model_dump(mode="json")
    state["provider_recovery"] = ProviderLedger().model_dump(mode="json")
    budget = Budget(state, 10800, lambda: ticks[0], lambda: ticks[0])
    budget.start()
    actions, events = [], []
    backend = SimpleNamespace(
        adapter=SimpleNamespace(release_all=lambda: actions.append("release")),
        freeze=lambda: actions.append("freeze"),
        thaw=lambda: actions.append("thaw"),
    )
    trial = SimpleNamespace(
        root=tmp_path,
        lock=threading.RLock(),
        state=state,
        budget=budget,
        backend=backend,
        spec=SimpleNamespace(action_execution="live"),
        model=SimpleNamespace(api_key_env="PROVIDER_TEST_KEY"),
        event=lambda kind, **fields: events.append({"type": kind, **fields}),
        persist=budget.touch,
    )
    waits = []

    def wait(seconds):
        waits.append(seconds)
        ticks[0] += seconds
        return False

    stop = SimpleNamespace(is_set=lambda: False, wait=wait)
    recovery = ProviderRecovery(trial)
    trial.recovery = recovery
    return SimpleNamespace(
        trial=trial,
        recovery=recovery,
        ticks=ticks,
        actions=actions,
        events=events,
        waits=waits,
        stop=stop,
        policy=RetryPolicy(recovery=recovery),
    )


def run(h, attempt, purpose="decision"):
    return with_retries(h.policy, lambda e: None, h.stop, None, attempt, purpose)


def kinds(h):
    return [e["type"] for e in h.events]


def test_invalid_coordinates_keep_sanitized_diagnostics_without_provider_pause(
    harness, monkeypatch
):
    from gamecua.provider import parse_reply

    secret = "synthetic-sensitive-value"
    monkeypatch.setenv("DIAGNOSTIC_TEST_TOKEN", secret)
    raw = json.dumps(
        {
            "observation": secret,
            "hypothesis": "Coordinate validation",
            "action": {"type": "pointer", "x": 200, "y": 0.5},
            "terminal_candidate": False,
        }
    )
    events = []

    def attempt(timeout):
        return parse_reply(raw), {}, "synthetic"

    with pytest.raises(ProviderFailure) as failure:
        with_retries(harness.policy, events.append, harness.stop, None, attempt)
    assert failure.value.category == "model_output"
    assert len(events) == harness.policy.invalid_output_attempts
    assert all("Expected finite number in [0, 1]" in e["validation_reason"] for e in events)
    assert secret not in json.dumps(events)
    assert all("[REDACTED]" in e["rejected_output_excerpt"] for e in events)
    assert harness.actions == []
    assert harness.trial.state["provider_recovery"]["timeout_credit_seconds"] == 0


@pytest.mark.parametrize(
    "failure",
    [
        InvalidResponse("empty"),
        ConnectionError("offline"),
        RuntimeError("HTTP 401"),
        InvalidDecision("Missing answer"),
    ],
)
def test_failed_request_freezes_then_success_thaws_without_credit(harness, failure):
    calls = []

    def attempt(timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise failure
        return "ok", {}, "same-model"

    result, stats = run(harness, attempt)
    assert result == "ok" and stats["attempts"] == 2
    assert harness.actions == ["release", "freeze", "thaw"]
    assert harness.waits == [1.0] and calls == [600, 600]
    ledger = harness.trial.state["provider_recovery"]
    assert ledger["timeout_credit_seconds"] == 0 and ledger["freezes"] == 1
    assert ledger["state"] == "ready" and ledger["request_failures"] == 1
    assert kinds(harness) == [
        "provider_request_failed",
        "provider_game_frozen",
        "provider_retry",
        "provider_game_recovered",
    ]
    assert all("timestamp" in e for e in harness.events)


def test_600_second_timeout_credits_once_and_resends_immediately(harness):
    calls = []

    def attempt(timeout):
        calls.append(timeout)
        if len(calls) == 1:
            harness.ticks[0] += timeout
            raise TimeoutError()
        return "ok", {}, None

    run(harness, attempt)
    assert harness.waits == []
    ledger = harness.trial.state["provider_recovery"]
    assert ledger["timeout_count"] == 1 and ledger["timeout_credit_seconds"] == 600
    budget = harness.trial.budget
    assert budget.allowance() == 11400 and budget.remaining() == 10800
    assert harness.trial.state["deadline"] == 1000 + 10800
    assert effective_deadline(harness.trial.state) == 1000 + 10800 + 600
    credit = next(e for e in harness.events if e["type"] == "provider_timeout_credit")
    assert credit["seconds"] == 600 and credit["allowance_seconds"] == 11400


@pytest.mark.parametrize("seconds", [1, 599])
def test_a_shorter_timeout_never_earns_credit(harness, seconds):
    calls = []

    def attempt(timeout):
        calls.append(timeout)
        if len(calls) == 1:
            harness.ticks[0] += seconds
            raise TimeoutError()
        return "ok", {}, None

    run(harness, attempt, "compaction")
    assert harness.trial.state["provider_recovery"]["timeout_credit_seconds"] == 0
    assert harness.waits == [1.0]


def test_only_timeouts_earn_credit_not_other_slow_failures(harness):
    calls = []

    def attempt(timeout):
        calls.append(timeout)
        if len(calls) == 1:
            harness.ticks[0] += 700
            raise ConnectionError("reset after a long wait")
        return "ok", {}, None

    run(harness, attempt)
    assert harness.trial.state["provider_recovery"]["timeout_credit_seconds"] == 0


def test_a_timeout_cut_short_by_the_allowance_earns_nothing(harness):
    harness.ticks[0] += 10790

    def attempt(timeout):
        assert timeout == 10
        harness.ticks[0] += timeout
        raise TimeoutError()

    with pytest.raises(ProviderFailure):
        run(harness, attempt)
    assert harness.trial.state["provider_recovery"]["timeout_credit_seconds"] == 0
    assert harness.trial.budget.remaining() == 0


def test_backoff_grows_to_twenty_then_the_next_failure_pauses_for_the_operator(harness):
    resume = harness.trial.root / "RESUME_PROVIDER"
    original_wait = harness.stop.wait
    state = {"calls": 0}

    def wait(seconds):
        if seconds == 1 and harness.waits[-1:] == [20.0]:
            pass
        state["calls"] += 1
        if "provider_operator_report" in kinds(harness) and not resume.exists():
            harness.ticks[0] += 3600
            resume.write_text("")
            return False
        return original_wait(seconds)

    harness.stop.wait = wait

    def attempt(timeout):
        if "provider_operator_resumed" in kinds(harness):
            return "ok", {}, None
        raise ConnectionError("down")

    result, _ = run(harness, attempt)
    assert result == "ok"
    assert harness.waits[: len(BACKOFF)] == list(BACKOFF) == [1, 2, 4, 8, 16, 20]
    ledger = harness.trial.state["provider_recovery"]
    assert ledger["operator_reports"] == 1 and ledger["operator_pause_seconds"] == 3600
    budget = harness.trial.budget
    assert budget.elapsed() == pytest.approx(sum(BACKOFF), abs=1)
    assert harness.trial.state["deadline"] == 1000 + 10800
    assert effective_deadline(harness.trial.state) == 1000 + 10800 + 3600
    assert not resume.exists()
    report = next(e for e in harness.events if e["type"] == "provider_operator_report")
    assert report["reason"] == "backoff_exhausted"
    assert kinds(harness).index("provider_operator_resumed") > kinds(harness).index(
        "provider_operator_report"
    )
    assert harness.actions[-1] == "thaw"


def test_repeated_timeouts_cannot_earn_unlimited_time(harness):
    resume = harness.trial.root / "RESUME_PROVIDER"
    original_wait = harness.stop.wait
    harness.stop.wait = lambda s: (
        (resume.write_text("") or False) if not resume.exists() else original_wait(s)
    )
    seen = []

    def attempt(timeout):
        seen.append(timeout)
        if len(seen) > len(BACKOFF) + 1:
            return "ok", {}, None
        harness.ticks[0] += timeout
        raise TimeoutError()

    run(harness, attempt)
    ledger = harness.trial.state["provider_recovery"]
    assert ledger["timeout_count"] == len(BACKOFF) + 1 and ledger["operator_reports"] == 1


def test_operator_pause_survives_a_restart_without_being_charged(harness):
    budget = harness.trial.budget
    budget.pause()
    harness.ticks[0] += 3600
    budget.touch()
    state = json.loads(json.dumps(harness.trial.state))
    assert (
        state["elapsed_seconds"] == 0
        and state["provider_recovery"]["operator_pause_seconds"] == 3600
    )
    harness.ticks[0] += 100
    restored = Budget(state, 10800, lambda: harness.ticks[0], lambda: harness.ticks[0])
    assert restored.elapsed() == pytest.approx(100, abs=1)
    assert restored.remaining() == pytest.approx(10700, abs=1)


def test_frozen_steps_never_freeze_or_thaw_natively(harness):
    harness.trial.spec.action_execution = "frozen_steps"
    calls = []

    def attempt(timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise ConnectionError("down")
        return "ok", {}, None

    run(harness, attempt)
    assert harness.actions == ["release"]
    frozen = next(e for e in harness.events if e["type"] == "provider_game_frozen")
    assert frozen["already_frozen"] and not frozen["native_pause"]


def test_cancellation_does_not_retry_or_credit(harness):
    def attempt(timeout):
        harness.stop.is_set = lambda: True
        harness.ticks[0] += 600
        raise TimeoutError()

    with pytest.raises(ProviderFailure):
        run(harness, attempt)
    assert harness.actions == [] and harness.waits == []
    assert harness.trial.state["provider_recovery"]["timeout_credit_seconds"] == 0


def test_native_death_while_the_provider_fails_stops_the_retries(harness):
    harness.trial.backend.poll = lambda elapsed: "death"

    def attempt(timeout):
        raise InvalidResponse("empty")

    with pytest.raises(ProviderTerminal) as failure:
        run(harness, attempt)
    assert failure.value.terminal == "death" and harness.waits == []


def test_a_received_but_invalid_answer_is_not_a_provider_failure(harness):
    def attempt(timeout):
        raise InvalidDecision("Invalid structured decision", '{"observation": 1}')

    with pytest.raises(ProviderFailure) as failure:
        run(harness, attempt)
    assert failure.value.category == "model_output"
    assert harness.actions == [] and harness.waits == []
    assert harness.trial.state["provider_recovery"]["freezes"] == 0


def test_the_watchdog_waits_for_a_timeout_in_flight_but_obeys_stop(tmp_path):
    waits = iter([False, True])
    stopped = []
    trial = SimpleNamespace(
        root=tmp_path,
        stop=SimpleNamespace(wait=lambda t: next(waits), set=lambda: stopped.append(True)),
        budget=SimpleNamespace(remaining=lambda: 0),
        provider_recovery=SimpleNamespace(full_timeout_in_flight=True),
        persist=lambda: None,
    )
    Trial.watch(trial)
    assert not stopped
    (tmp_path / "STOP").touch()
    waits = iter([False, True])
    trial.stop.wait = lambda t: next(waits)
    Trial.watch(trial)
    assert stopped


def test_default_policy_serializes_and_budgets_exactly_as_before():
    assert "provider_recovery" not in TrialRecord(id="old").model_dump(mode="json")
    state = TrialRecord(id="old").model_dump(mode="json")
    clock = [100.0]
    budget = Budget(state, 30, lambda: clock[0], lambda: clock[0])
    budget.start()
    clock[0] = 112
    assert budget.allowance() == 30 and budget.remaining() == 18


def test_only_the_named_key_is_refreshed_from_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROVIDER_TEST_KEY", "old")
    monkeypatch.setenv("OTHER_KEY", "keep")
    (tmp_path / ".env").write_text("OTHER_KEY=changed\nPROVIDER_TEST_KEY=new\n")
    assert refresh_key("PROVIDER_TEST_KEY")
    assert __import__("os").environ["PROVIDER_TEST_KEY"] == "new"
    assert __import__("os").environ["OTHER_KEY"] == "keep"


def policy_trial(tmp_path, seconds=10, backend=None):
    spec = TrialSpec(
        id="policy-trial",
        game_id="slay-the-spire",
        model_id="deepseek-flash",
        rubric_id="sts-progress-pilot",
        total_seconds=seconds,
        provider_failure_policy=POLICY,
    )
    return Trial(
        tmp_path / "trial",
        spec,
        CATALOG.rubrics[spec.rubric_id],
        CATALOG.games[spec.game_id],
        CATALOG.models[spec.model_id],
        backend=backend,
    )


def grant_credits(trial, count):
    for number in range(1, count + 1):
        trial.provider_recovery.credit(number)


def test_evidence_after_the_base_budget_counts_only_with_recorded_credit(tmp_path):
    trial = policy_trial(tmp_path)
    add_episode(trial, "episode-001", [("save", combat(), 100.0)])
    trial.budget.start()
    trial.finish("completed", "deadline")
    assert time_allowance(trial.root, trial.spec) == 10
    assert score(trial.root)[1]["score"] == 0
    grant_credits(trial, 1)
    trial.persist()
    result = score(trial.root)[1]
    assert time_allowance(trial.root, trial.spec) == 610
    assert result["score"] > 0 and result["time_allowance_seconds"] == 610
    assert result["provider_recovery"]["timeout_count"] == 1
    assert (trial.root / "summary.json").exists()


def test_the_default_policy_still_drops_late_evidence(tmp_path):
    from test_trials import make_trial

    trial = make_trial(tmp_path / "default")
    add_episode(trial, "episode-001", [("save", combat(), 11.0)])
    trial.budget.start()
    trial.finish("completed", "deadline")
    assert score(trial.root)[1]["score"] == 0
    assert "provider_recovery" not in score(trial.root)[1]


class FlakyAgent:
    attempts = 0

    def __init__(self, policy, event, **kwargs):
        self.policy, self.event = policy, event

    def decide(self, image, memory, history, stop, deadline=None):
        def attempt(timeout):
            FlakyAgent.attempts += 1
            if FlakyAgent.attempts == 1:
                raise ConnectionError("offline")
            return (
                {
                    "observation": "screen",
                    "hypothesis": "guess",
                    "memory": "",
                    "terminal_candidate": False,
                    "action": {"type": "wait", "seconds": 0.1},
                },
                {},
                "model",
            )

        decision, stats = with_retries(self.policy, self.event, stop, deadline, attempt)
        stop.set()
        return decision, stats

    def close(self):
        pass


def test_a_live_trial_freezes_the_game_through_a_failure_and_records_it(tmp_path):
    FlakyAgent.attempts = 0
    backend = FakeBackend(tmp_path / "trial")
    calls = []
    backend.freeze = lambda: calls.append("freeze")
    backend.thaw = lambda: calls.append("thaw")
    trial = policy_trial(tmp_path, seconds=60, backend=backend)
    trial.agent_factory, trial.recorder = FlakyAgent, FakeRecorder
    trial.run(install_signals=False, acquire_lease=False)
    assert calls == ["freeze", "thaw"]
    events = [json.loads(line) for line in (trial.root / "events.jsonl").read_text().splitlines()]
    names = [e["type"] for e in events]
    assert names.index("provider_request_failed") < names.index("provider_game_frozen")
    assert names.index("provider_game_frozen") < names.index("provider_game_recovered")
    summary = json.loads((trial.root / "summary.json").read_text())
    assert summary["provider_recovery"]["freezes"] == 1
    assert summary["provider_recovery"]["state"] == "ready"
    assert summary["allowance_seconds"] == 60


def test_a_process_that_died_while_frozen_resumes_as_a_charged_interruption(tmp_path):
    trial = policy_trial(tmp_path, seconds=60)
    trial.state["provider_recovery"]["state"] = "frozen"
    trial.persist()
    backend = FakeBackend(trial.root)
    resumed = Trial(
        trial.root, backend=backend, agent_factory=InterruptedAgent, recorder=FakeRecorder
    )
    assert resumed.state["provider_recovery"]["state"] == "ready"
    assert resumed.provider_recovery is not None
    write_json(trial.root / "check.json", {})


def test_the_watcher_still_stops_the_trial_when_saving_fails(tmp_path, monkeypatch):
    trial = make_trial(tmp_path / "trial")
    trial.budget.start()
    monkeypatch.setattr(trial, "persist", lambda: (_ for _ in ()).throw(OSError("disk full")))
    watcher = threading.Thread(target=trial.watch, daemon=True)
    watcher.start()
    (trial.root / "STOP").touch()
    assert trial.stop.wait(5)


def test_the_harbor_guard_moves_by_the_recorded_credit_and_pause(tmp_path):
    from gamecua.harbor.bridge import recovery_shift

    record = tmp_path / "trial.json"
    assert recovery_shift(record) == 0
    record.write_text(
        json.dumps(
            {"provider_recovery": {"timeout_credit_seconds": 600, "operator_pause_seconds": 30}}
        )
    )
    assert recovery_shift(record) == 630
