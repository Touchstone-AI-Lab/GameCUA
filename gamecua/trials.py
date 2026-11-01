"""Runs a Trial under one wall-clock budget covering inference, actions, restarts and downtime."""

import json
import signal
import sys
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from .actions import validate
from .context import load_checkpoint
from .evidence import score
from .execution import desktop_lease, inherited_context
from .provider import PROMPT, ProviderFailure, RetryPolicy, VisionAgent
from .provider_recovery import ProviderRecovery, ProviderTerminal
from .recording import Recording
from .specs import GameSpec, InputProfile, ModelSpec, ProviderLedger, Rubric, TrialRecord, TrialSpec
from .storage import write_json

DURATION_FIELDS = {"wait": "seconds", "drag": "duration", "control": "duration"}


def policy_prompt(spec, profile=None):
    prompt = PROMPT
    if spec.action_execution == "frozen_steps":
        prompt += (
            "\nExecution mode: the game is paused while you decide. Each action uses a nominal "
            f"{spec.step_seconds:g} s host-time step, with input durations capped at that step. "
            "Input is released before any integration-specific rendering wait, then the game "
            "pauses before the next screenshot. Native simulation time depends on game speed, "
            "native pause and performance; it is not measured by the host-time step. "
            "Rendering waits and inference both consume the same wall-clock budget."
        )
    if profile is not None:
        from .typed import describe_profile

        prompt += (
            "\nControls reference: the same inputs a typed-choice model is offered, explaining "
            "controls only, not goals. Any listed key may be used with the actions above.\n"
            + describe_profile(profile)
        )
    return prompt


def stored_profile(root):
    path = root / "inputs.json"
    return InputProfile.model_validate_json(path.read_text()) if path.exists() else None


def step_action(action, seconds):
    action = validate(action)
    field = DURATION_FIELDS.get(action["type"])
    if field and action.get(field, 0) > seconds:
        return {**action, field: seconds}, True
    return action, False


class Budget:
    def __init__(self, state, seconds, clock=time.time, monotonic=time.monotonic):
        self.state, self.seconds, self.clock, self.monotonic = state, seconds, clock, monotonic
        self.lock = threading.RLock()
        self.paused_at = None

    def ledger(self):
        return self.state.get("provider_recovery") or {}

    def allowance(self):
        return self.seconds + self.ledger().get("timeout_credit_seconds", 0)

    def start(self):
        with self.lock:
            if self.state["started_at"] is None:
                started = self.clock()
                self.state.update(started_at=started, deadline=started + self.seconds)

    def elapsed(self):
        """Wall-clock seconds since gameplay started, excluding operator pauses."""
        with self.lock:
            if self.state["started_at"] is None:
                return 0.0
            if self.paused_at is not None:
                tick = self.monotonic()
                self.ledger()["operator_pause_seconds"] += tick - self.paused_at
                self.paused_at = tick
            excluded = self.ledger().get("operator_pause_seconds", 0)
            return max(0.0, self.clock() - self.state["started_at"] - excluded)

    def credit(self, seconds):
        with self.lock:
            ledger = self.ledger()
            ledger["timeout_count"] += 1
            ledger["timeout_credit_seconds"] += seconds

    def pause(self):
        with self.lock:
            self.elapsed()
            self.paused_at = self.monotonic()

    def resume(self):
        with self.lock:
            self.elapsed()
            self.paused_at = None

    def remaining(self):
        return max(0.0, self.allowance() - self.elapsed())

    def touch(self):
        with self.lock:
            elapsed = self.elapsed()
            self.state.update(
                elapsed_seconds=elapsed,
                chargeable_seconds=min(self.allowance(), elapsed),
                last_seen=self.clock(),
            )


class Trial:
    provider_recovery = None

    def __init__(
        self,
        directory,
        spec=None,
        rubric=None,
        game=None,
        model=None,
        backend=None,
        agent_factory=VisionAgent,
        recorder=Recording,
        start_gate=None,
        inputs=None,
        interview=False,
    ):
        self.root = Path(directory).resolve()
        self.start_gate = Path(start_gate) if start_gate else None
        self.stop, self.lock = threading.Event(), threading.RLock()
        self.recorder, self.backend, self.interview = recorder, backend, interview
        if spec:
            self.create(spec, rubric, game, model, inputs)
        else:
            self.state = json.loads((self.root / "trial.json").read_text())
            spec = TrialSpec.model_validate_json((self.root / "trial.spec.json").read_text())
            rubric = Rubric.model_validate_json((self.root / "rubric.json").read_text())
            game = GameSpec.model_validate_json((self.root / "game.json").read_text())
            model = ModelSpec.model_validate_json((self.root / "model.json").read_text())
            gap = max(0.0, time.time() - self.state["last_seen"])
            self.state["infrastructure_downtime_seconds"] += gap
            self.state["evidence_gaps"].append(
                {
                    "from_seconds": self.state["elapsed_seconds"],
                    "to_seconds": time.time() - self.state["started_at"]
                    if self.state["started_at"]
                    else 0,
                    "reason": "infrastructure_interruption",
                    "charged": True,
                }
            )
        self.spec, self.rubric, self.game, self.model = spec, rubric, game, model
        self.profile = stored_profile(self.root)
        self.agent_factory = agent_factory
        if agent_factory is VisionAgent and model.provider == "typesafe":
            from .typed import typed_factory

            self.agent_factory = typed_factory(self.profile)
        if spec.provider_failure_policy == "freeze_retry_timeout_credit":
            ledger = self.state.setdefault(
                "provider_recovery", ProviderLedger().model_dump(mode="json")
            )
            ledger["state"] = "ready"
            self.provider_recovery = ProviderRecovery(self)
        self.budget = Budget(self.state, spec.total_seconds)
        self.persist()

    def create(self, spec, rubric, game, model, inputs):
        self.root.mkdir(parents=True)
        files = {
            "trial.spec": spec,
            "rubric": rubric,
            "game": game,
            "model": model,
            "inputs": inputs,
        }
        for name, value in files.items():
            if value is not None and (name != "inputs" or spec.inputs_id):
                write_json(self.root / f"{name}.json", value.model_dump(mode="json"))
        environment = self.root.parent / "environment.json"
        if environment.exists():
            write_json(self.root / "environment.json", json.loads(environment.read_text()))
        (self.root / "system_prompt.txt").write_text(
            policy_prompt(spec, inputs if spec.inputs_id else None)
        )
        self.state = TrialRecord(id=uuid.uuid4().hex).model_dump(mode="json")

    def persist(self):
        with self.lock:
            self.budget.touch()
            write_json(self.root / "trial.json", self.state)
            if self.state.get("provider_recovery") is not None:
                write_json(
                    self.root / "summary.json",
                    {
                        "trial_id": self.state["id"],
                        "status": self.state["status"],
                        "reason": self.state["reason"],
                        "policy": self.spec.provider_failure_policy,
                        "base_seconds": self.spec.total_seconds,
                        "allowance_seconds": self.budget.allowance(),
                        "elapsed_seconds": self.state["elapsed_seconds"],
                        "provider_recovery": self.state["provider_recovery"],
                        "events": "events.jsonl",
                    },
                )

    def event(self, kind, **fields):
        with self.lock, (self.root / "events.jsonl").open("a") as file:
            file.write(
                json.dumps({"type": kind, "elapsed": self.budget.elapsed(), **fields}) + "\n"
            )

    def watch(self):
        while not self.stop.wait(1):
            credit_pending = (
                self.provider_recovery is not None and self.provider_recovery.full_timeout_in_flight
            )
            if (self.root / "STOP").exists() or (
                self.budget.remaining() <= 0 and not credit_pending
            ):
                self.stop.set()
            try:
                self.persist()
            except (OSError, RuntimeError, ValueError) as error:
                print(f"Trial state not saved: {type(error).__name__}: {error}", file=sys.stderr)

    def deadline(self):
        if self.state["started_at"] is None:
            return float("inf")
        return time.monotonic() + self.budget.remaining()

    def finish(self, status, reason):
        self.state.update(status=status, reason=reason)
        episodes = self.state["episodes"]
        if episodes and episodes[-1]["status"] in ("running", "interrupted"):
            episodes[-1].update(
                status="interrupted" if status == "interrupted" else "truncated", reason=reason
            )
        for segment in episodes[-1].get("segments", []) if episodes else []:
            if segment["status"] == "running":
                segment.update(status="interrupted", reason=reason)
        self.persist()
        self.event("trial_stopped", status=status, reason=reason)

    def conclude(self, failure=None):
        if self.budget.remaining() <= 0:
            self.finish("completed", "deadline")
        elif (self.root / "STOP").exists():
            self.finish("cancelled", "stop_file")
        elif self.stop.is_set():
            self.finish("interrupted", "signal_interruption")
        else:
            self.finish("interrupted", failure or "signal_interruption")

    def episode(self):
        number = len(self.state["episodes"]) + 1
        episode = {
            "id": f"episode-{number:03d}",
            "trial_id": self.state["id"],
            "status": "preparing",
            "reason": None,
            "segments": [],
        }
        self.state["episodes"].append(episode)
        folder = self.root / "episodes" / episode["id"]
        folder.mkdir(parents=True)
        self.persist()
        setup = self.backend.prepare(folder, self.stop, self.deadline())
        write_json(folder / "setup.json", setup)
        if not setup["verified"]:
            episode.update(status="setup_failure", reason="setup_unverified")
            self.state["protocol_failures"].append(
                {"reason": "setup_unverified", "episode_id": episode["id"]}
            )
            self.state["eligible"] = False
            raise RuntimeError("Episode setup not verified")
        episode.update(status="running", checkpoint=self.backend.checkpoint())
        if self.start_gate and self.state["started_at"] is None:
            self.start_gate.with_suffix(".ready").touch()
            while not self.start_gate.exists():
                if self.stop.wait(0.1) or (self.root / "STOP").exists():
                    raise InterruptedError("Cancelled before gameplay start")
        self.budget.start()
        self.event(
            "episode_started", episode_id=episode["id"], context_policy=self.spec.episode_context
        )
        self.persist()
        return episode

    def ask(self):
        from .interview import conduct

        record = conduct(
            self.spec,
            self.game,
            self.rubric,
            self.model,
            self.profile,
            event=lambda item: self.event("interview_provider", **item),
            stop=self.stop,
        )
        write_json(self.root / "interview.json", record)
        self.event(
            "interview",
            answered=bool(record.get("answers")),
            skipped=record.get("skipped"),
            failure=record.get("failure"),
        )

    def make_agent(self, directory, context, prompt):
        agent = self.agent_factory(
            RetryPolicy(recovery=self.provider_recovery),
            lambda item: self.event("provider", **item),
            model_spec=self.model,
            prompt=prompt,
        )
        if hasattr(agent, "bind_context"):
            initial = None
            if context["session_source"]:
                initial = load_checkpoint((self.root / context["session_source"]).parent)
                if context["provenance"]["kind"] == "death_inheritance":
                    initial["inheritance"] = True
            agent.bind_context(directory / "context", initial)
        return agent

    def play(self, episode):
        folder = self.root / "episodes" / episode["id"]
        context = inherited_context(
            self.root, episode, self.state["episodes"], self.spec.episode_context
        )
        memory, history = context["memory"], context["history"]
        segment = {
            "id": f"segment-{len(episode['segments']) + 1:03d}",
            "episode_id": episode["id"],
            "status": "running",
            "reason": None,
        }
        episode["segments"].append(segment)
        directory = folder / "segments" / segment["id"]
        directory.mkdir(parents=True)
        limit = getattr(self.spec, "episode_limit", None)
        if limit and context["provenance"]["kind"] != "recovery":
            number = len(self.state["episodes"])
            notice = f"Attempt {number} of {limit}."
            context["attempt_notice"] = " ".join(
                part for part in (context["attempt_notice"], notice) if part
            )
        write_json(directory / "initial_agent_context.json", context)
        prompt = policy_prompt(self.spec, self.profile)
        if context["attempt_notice"]:
            prompt += "\n" + context["attempt_notice"]
        (directory / "policy_prompt.txt").write_text(prompt)
        recorder = self.recorder(
            directory, self.game, self.spec.recording_fps, self.budget.elapsed, self.stop
        )
        agent = self.make_agent(directory, context, prompt)
        observe = getattr(agent, "set_observation_path", lambda path: None)
        report = getattr(agent, "record_execution", lambda record: None)
        frozen = self.spec.action_execution == "frozen_steps"
        count = 0
        try:
            if frozen:
                self.backend.freeze()
                self.event("game_frozen", step_seconds=self.spec.step_seconds)
            while not self.stop.is_set() and self.budget.remaining() > 0:
                terminal = self.backend.poll(self.budget.elapsed())
                if terminal:
                    episode.update(status="completed", reason=terminal)
                    segment.update(status="completed", reason=terminal)
                    return terminal
                count += 1
                name = f"{count:05d}"
                observed_at = time.monotonic()
                before = self.backend.adapter.capture()
                before.save(directory / f"{name}_before.png")
                observe(directory / f"{name}_before.png")
                episode["checkpoint"] = {
                    **self.backend.checkpoint(),
                    "frame": str((directory / f"{name}_before.png").relative_to(self.root)),
                }
                self.persist()
                self.event("request_started", episode_id=episode["id"], step=count)
                try:
                    decision, stats = agent.decide(
                        before, memory, history, self.stop, self.deadline()
                    )
                except ProviderTerminal as exc:
                    episode.update(status="completed", reason=exc.terminal)
                    segment.update(status="completed", reason=exc.terminal)
                    return exc.terminal
                except ProviderFailure as exc:
                    self.event("request_failed", step=count, category=exc.category)
                    if exc.category == "model_output" and not self.stop.is_set():
                        continue
                    raise
                self.state["effective_seconds"] += stats.get("successful_request_seconds", 0)
                record = {
                    "step": count,
                    "decision": decision,
                    **stats,
                    "elapsed": self.budget.elapsed(),
                    "execution_status": "rejected",
                    "executed": False,
                    "before": f"{name}_before.png",
                }
                path = directory / f"{name}.json"
                self.event("request_finished", step=count)
                reason = None
                if self.stop.is_set() or self.budget.remaining() <= 0:
                    reason = "deadline"
                else:
                    fresh = self.backend.adapter.capture()
                    delta = float(
                        np.abs(np.asarray(fresh, float) - np.asarray(before, float)).mean()
                    )
                    record["pre_execution_pixel_delta"] = delta
                    record["observation_age_seconds"] = time.monotonic() - observed_at
                    if (
                        self.game.timing == "turn_based"
                        and not frozen
                        and delta > getattr(self.spec, "stale_pixel_delta", 15.0)
                    ):
                        reason = "stale_observation"
                    elif (
                        self.game.timing == "realtime"
                        and not frozen
                        and record["observation_age_seconds"]
                        > getattr(self.spec, "observation_age_limit_seconds", 30.0)
                    ):
                        reason = "observation_age_limit"
                if reason:
                    record["reason"] = reason
                    write_json(path, record)
                    report(record)
                    if reason == "deadline":
                        break
                    continue
                terminal = self.backend.poll(self.budget.elapsed())
                if terminal:
                    record.update(reason="native_terminal", native_terminal=terminal)
                    write_json(path, record)
                    report(record)
                    episode.update(status="completed", reason=terminal)
                    segment.update(status="completed", reason=terminal)
                    return terminal
                record["execution_status"] = "pending"
                write_json(path, record)
                started = time.monotonic()
                if frozen:
                    action, clamped = step_action(decision["action"], self.spec.step_seconds)
                    boundary = None
                    self.backend.thaw()
                    try:
                        self.backend.adapter.execute(
                            action, stop=self.stop, deadline=self.deadline()
                        )
                        self.stop.wait(
                            max(
                                0,
                                min(
                                    started + self.spec.step_seconds - time.monotonic(),
                                    self.budget.remaining(),
                                ),
                            )
                        )
                        self.backend.adapter.release_all()
                        settle = getattr(self.backend, "settle_action", None)
                        if settle is not None:
                            boundary = settle(self.stop, self.deadline())
                    finally:
                        self.backend.adapter.release_all()
                        self.backend.freeze()
                    record["frozen_step"] = {
                        "host_seconds": time.monotonic() - started,
                        "nominal_seconds": self.spec.step_seconds,
                        "action_clamped": clamped,
                    }
                    if boundary is not None:
                        record["frozen_step"]["render_boundary"] = boundary
                else:
                    self.backend.adapter.execute(
                        decision["action"], stop=self.stop, deadline=self.deadline()
                    )
                    settle = getattr(self.backend, "settle_action", None)
                    if settle is None:
                        self.stop.wait(min(0.3, self.budget.remaining()))
                    else:
                        self.backend.adapter.release_all()
                        record["render_boundary"] = settle(self.stop, self.deadline())
                self.backend.adapter.capture().save(directory / f"{name}_after.png")
                record.update(
                    execution_status="completed",
                    executed=True,
                    after=f"{name}_after.png",
                    action_seconds=time.monotonic() - started,
                )
                self.state["effective_seconds"] += record["action_seconds"]
                write_json(path, record)
                report(record)
                memory = decision["memory"]
                history.append({"step": count, "action": decision["action"]})
                self.persist()
        finally:
            if self.provider_recovery is not None:
                self.provider_recovery.thaw(recovered=False)
            if frozen:
                self.backend.thaw()
            agent.close()
            self.backend.adapter.release_all()
            recorder.close()
            if segment["status"] == "running":
                segment.update(
                    status="interrupted",
                    reason="deadline" if self.budget.remaining() <= 0 else "interruption",
                )
            self.persist()
        return None

    def recover(self, active):
        folder = self.root / "episodes" / active["id"]
        uncertain = any(
            json.loads(p.read_text()).get("execution_status") == "pending"
            for p in folder.glob("segments/*/[0-9]*.json")
        )
        if uncertain or not self.backend.recover(folder, active["checkpoint"]):
            self.state["eligible"] = False
            self.state["protocol_failures"].append(
                {"reason": "recovery_unverifiable", "episode_id": active["id"]}
            )
            return False
        active.update(status="running", reason=None)
        for segment in active["segments"]:
            if segment["status"] == "running":
                segment.update(status="interrupted", reason="process_interruption")
        self.event("episode_recovered", episode_id=active["id"])
        return True

    def run(self, install_signals=True, acquire_lease=True):
        handlers = {}
        if install_signals:
            for sig in (signal.SIGINT, signal.SIGTERM):
                handlers[sig] = signal.signal(sig, lambda *_: self.stop.set())
        watcher = None
        try:
            with desktop_lease(acquire_lease):
                if self.budget.remaining() <= 0:
                    self.finish("completed", "deadline")
                    return self.state
                episodes = self.state["episodes"]
                active = episodes[-1] if episodes else None
                if active and active["status"] in ("running", "interrupted"):
                    if not self.recover(active):
                        self.finish("interrupted", "recovery_unverifiable")
                        return self.state
                else:
                    if self.interview and not (self.root / "interview.json").exists():
                        self.ask()
                    active = self.episode()
                self.state.update(status="running", reason=None)
                watcher = threading.Thread(target=self.watch, daemon=True)
                watcher.start()
                while not self.stop.is_set() and self.budget.remaining() > 0:
                    terminal = self.play(active)
                    if terminal == "victory":
                        self.finish("completed", "verified_run_completion")
                    elif terminal == "death" and self.model.provider == "typesafe":
                        self.finish("completed", "death_without_memory")
                    elif terminal == "death" and len(episodes) >= (
                        getattr(self.spec, "episode_limit", None) or float("inf")
                    ):
                        self.finish("completed", "episode_limit")
                    elif (
                        terminal == "death"
                        and not self.stop.is_set()
                        and self.budget.remaining() > 0
                    ):
                        active = self.episode()
                        continue
                    break
                if self.state["status"] == "running":
                    self.conclude()
        except (ProviderFailure, InterruptedError) as exc:
            provider = isinstance(exc, ProviderFailure)
            if provider and not self.stop.is_set() and self.budget.remaining() > 0:
                self.state["eligible"] = False
            if (
                provider
                and exc.category == "provider"
                and (self.budget.remaining() <= 0 or not self.stop.is_set())
                and not any(self.root.glob("episodes/*/segments/*/[0-9]*.json"))
            ):
                self.state["eligible"] = False
                self.state["protocol_failures"].append(
                    {"reason": "provider_unavailable", "scope": "trial"}
                )
            self.conclude(type(exc).__name__)
        except Exception as exc:
            self.state["eligible"] = False
            self.finish("interrupted", type(exc).__name__)
            self.event("infrastructure_error", error_type=type(exc).__name__)
            raise
        finally:
            self.stop.set()
            if watcher:
                watcher.join(timeout=2)
            self.backend.close(preserve=self.state["status"] == "interrupted")
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            self.persist()
        return self.state


def run_series(directory, count, create):
    import statistics

    directory = Path(directory)
    directory.mkdir(parents=True)
    results = []
    for i in range(count):
        root = directory / f"trial-{i + 1:03d}"
        trial = failure = None
        try:
            trial = create(root)
            trial.run()
        except Exception as exc:
            failure = type(exc).__name__
        try:
            path, result = score(root)
            results.append(
                {
                    "trial_id": result["trial_id"],
                    "directory": str(root),
                    "score": result["score"],
                    "scoreable": result["scoreable"],
                    "completion_status": result["completion_status"],
                    "comparison_eligible": result["comparison_eligible"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "outcomes": [e["outcome"] for e in result["episodes"]],
                    "failure": failure
                    or (result["trial_reason"] if not result["comparison_eligible"] else None),
                    "termination_reason": result["trial_reason"],
                    "scoring": str(path),
                }
            )
        except (OSError, ValueError, KeyError) as exc:
            results.append(
                {
                    "directory": str(root),
                    "score": None,
                    "scoreable": False,
                    "comparison_eligible": False,
                    "completion_status": "incomplete",
                    "failure": failure or "evidence_unscoreable",
                    "assessment_error": type(exc).__name__,
                }
            )
        if trial and trial.state["status"] == "interrupted":
            if hasattr(trial.backend, "stop_process"):
                trial.backend.stop_process()
            break
    valid = [r["score"] for r in results if r.get("comparison_eligible")]
    report = {
        "requested_count": count,
        "trials": results,
        "valid_count": len(valid),
        "incomplete_trials": [r for r in results if r.get("completion_status") == "incomplete"],
        "score_mean": statistics.mean(valid) if valid else None,
        "score_min": min(valid) if valid else None,
        "score_max": max(valid) if valid else None,
    }
    write_json(directory / "series.json", report)
    return report
