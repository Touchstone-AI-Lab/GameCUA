"""The freeze_retry_timeout_credit policy: a failing provider freezes the game, and only a 600 s timeout adds 600 s to the allowance."""

import os
import re
import sys
import time
from pathlib import Path

from .provider import InvalidDecision, ProviderFailure
from .specs import TIMEOUT_CREDIT_SECONDS

REQUEST_TIMEOUT = 600.0
BACKOFF = (1.0, 2.0, 4.0, 8.0, 16.0, 20.0)
RESUME_FILE = "RESUME_PROVIDER"
TIMEOUT_ERRORS = {
    "TimeoutError",
    "APITimeoutError",
    "ReadTimeout",
    "ConnectTimeout",
    "WriteTimeout",
    "PoolTimeout",
}


class ProviderTerminal(ProviderFailure):
    def __init__(self, terminal):
        super().__init__("Native terminal during provider failure")
        self.terminal = terminal


def is_timeout(error):
    return type(error).__name__ in TIMEOUT_ERRORS


def empty_reply(error):
    return isinstance(error, InvalidDecision) and not error.excerpt


def diagnostic_text(value):
    if value is None:
        return None
    value = str(value)
    for name, secret in os.environ.items():
        if len(secret) >= 8 and any(
            word in name.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")
        ):
            value = value.replace(secret, "[REDACTED]")
    return re.sub(r"\bsk-[A-Za-z0-9_-]{8,}", "[REDACTED]", value)[:4000]


def env_file():
    return Path(os.environ.get("GAMECUA_ENV_FILE") or Path.cwd() / ".env")


def refresh_key(name):
    path = env_file()
    if not name or not path.exists():
        return False
    for line in path.read_text().splitlines():
        key, _, value = line.strip().partition("=")
        if key.strip() == name and value.strip():
            os.environ[name] = value.strip()
            return True
    return False


class ProviderRecovery:
    def __init__(self, trial):
        self.trial = trial
        self.frozen = False
        self.frozen_since = None
        self.full_timeout_in_flight = False

    def ledger(self):
        return self.trial.state["provider_recovery"]

    def emit(self, kind, **fields):
        self.trial.event(kind, timestamp=time.time(), **fields)

    def count(self, **increments):
        with self.trial.lock:
            ledger = self.ledger()
            for name, amount in increments.items():
                ledger[name] += amount
            self.trial.persist()

    def freeze(self):
        if self.frozen:
            return
        trial = self.trial
        trial.backend.adapter.release_all()
        stepped = trial.spec.action_execution == "frozen_steps"
        pausable = hasattr(trial.backend, "freeze") and hasattr(trial.backend, "thaw")
        if not stepped and pausable:
            trial.backend.freeze()
        self.frozen, self.frozen_since = True, time.monotonic()
        with trial.lock:
            self.ledger()["state"] = "frozen"
        self.count(freezes=1)
        self.emit(
            "provider_game_frozen",
            native_pause=pausable and not stepped,
            already_frozen=stepped,
        )
        poll = getattr(trial.backend, "poll", None)
        terminal = poll(trial.budget.elapsed()) if poll else None
        if terminal:
            raise ProviderTerminal(terminal)

    def thaw(self, recovered=True):
        if not self.frozen:
            return
        trial = self.trial
        stepped = trial.spec.action_execution == "frozen_steps"
        if not stepped and hasattr(trial.backend, "thaw"):
            trial.backend.thaw()
        seconds = time.monotonic() - self.frozen_since
        self.frozen, self.frozen_since = False, None
        with trial.lock:
            self.ledger()["state"] = "ready"
        self.count(frozen_seconds=seconds)
        self.emit(
            "provider_game_recovered" if recovered else "provider_game_released", seconds=seconds
        )

    def credit(self, attempt):
        trial = self.trial
        with trial.lock:
            trial.budget.credit(TIMEOUT_CREDIT_SECONDS)
            trial.persist()
        self.emit(
            "provider_timeout_credit",
            seconds=TIMEOUT_CREDIT_SECONDS,
            attempt=attempt,
            timeout_count=self.ledger()["timeout_count"],
            allowance_seconds=trial.budget.allowance(),
        )

    def wait_for_operator(self, stop, reason):
        trial = self.trial
        resume = trial.root / RESUME_FILE
        resume.unlink(missing_ok=True)
        before = self.ledger()["operator_pause_seconds"]
        with trial.lock:
            trial.budget.pause()
            self.ledger()["state"] = "operator_paused"
        self.count(operator_reports=1)
        self.emit("provider_operator_report", reason=reason, resume_file=resume.name)
        print(
            f"Trial {trial.state['id']} is paused: the provider keeps failing. Replace the key"
            f" in {env_file()} if needed (GAMECUA_ENV_FILE names another file), then"
            f" create {resume} to resume (or create STOP to end it).",
            file=sys.stderr,
            flush=True,
        )
        try:
            while not resume.exists():
                if stop.wait(1) or (trial.root / "STOP").exists():
                    raise ProviderFailure("Stopped while waiting for the operator")
            resume.unlink(missing_ok=True)
        finally:
            with trial.lock:
                trial.budget.resume()
                self.ledger()["state"] = "frozen"
            self.emit(
                "provider_operator_resumed",
                excluded_seconds=self.ledger()["operator_pause_seconds"] - before,
                key_refreshed=refresh_key(trial.model.api_key_env),
            )

    def request(self, policy, event, stop, attempt, purpose):
        trial = self.trial
        number = failures = invalid = 0
        start = time.monotonic()
        while not stop.is_set() and trial.budget.remaining() > 0:
            number += 1
            timeout = min(REQUEST_TIMEOUT, trial.budget.remaining())
            self.full_timeout_in_flight = timeout == REQUEST_TIMEOUT
            started = time.monotonic()
            try:
                result, usage, returned = attempt(timeout)
            except Exception as error:
                if stop.is_set():
                    raise ProviderFailure("Stopped") from None
                seconds = time.monotonic() - started
                if isinstance(error, InvalidDecision) and not empty_reply(error):
                    self.thaw()
                    failures = 0
                    event(
                        {
                            "type": "provider_error",
                            "attempt": number,
                            "error_type": type(error).__name__,
                            "category": "model_output",
                            "retryable": True,
                            "reason": diagnostic_text(str(error)),
                            "validation_reason": diagnostic_text(
                                getattr(error, "validation_reason", None)
                            ),
                            "rejected_output_excerpt": diagnostic_text(
                                getattr(error, "diagnostic_excerpt", error.excerpt)
                            ),
                        }
                    )
                    invalid += 1
                    if invalid >= policy.invalid_output_attempts:
                        raise ProviderFailure(
                            "Model output remained invalid", "model_output"
                        ) from None
                    continue
                timed_out = (
                    timeout == REQUEST_TIMEOUT
                    and seconds >= REQUEST_TIMEOUT - 0.5
                    and is_timeout(error)
                )
                self.count(request_failures=1)
                self.emit(
                    "provider_request_failed",
                    purpose=purpose,
                    attempt=number,
                    error_type=type(error).__name__,
                    status=getattr(error, "status_code", None),
                    timeout_600=timed_out,
                    request_seconds=seconds,
                )
                if timed_out:
                    self.credit(number)
                self.freeze()
                level = BACKOFF[min(failures, len(BACKOFF) - 1)]
                if failures >= len(BACKOFF):
                    self.wait_for_operator(stop, "backoff_exhausted")
                    failures = 0
                    continue
                failures += 1
                delay = 0.0 if timed_out else level
                self.emit(
                    "provider_retry", purpose=purpose, attempt=number + 1, delay_seconds=delay
                )
                if delay and stop.wait(min(delay, trial.budget.remaining())):
                    raise ProviderFailure("Stopped") from None
                continue
            finally:
                self.full_timeout_in_flight = False
            self.thaw()
            event(
                {"type": "provider_success", "purpose": purpose, "attempt": number, "usage": usage}
            )
            return result, {
                "usage": usage,
                "purpose": purpose,
                "returned_model": returned,
                "attempts": number,
                "latency_seconds": time.monotonic() - start,
                "successful_request_seconds": time.monotonic() - started,
            }
        raise ProviderFailure("Stopped or the Trial allowance is used up")
