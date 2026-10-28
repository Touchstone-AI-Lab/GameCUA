"""Reopen the same profile after a normal native exit, keeping the Trial, agent and deadline."""

import json
import subprocess
import time

from ...desktop import X11Desktop
from ...evidence import effective_deadline
from .setup import command, environment

EXIT_GRACE_SECONDS = 5
REOPEN_SECONDS = 240
MISSING = "Expected one visible game window titled 'Understand'; found 0"


def event(path, kind, **values):
    with path.open("a") as stream:
        stream.write(json.dumps({"type": kind, **values}) + "\n")


class RestartDesktop(X11Desktop):
    def __init__(self, restarts, **kwargs):
        super().__init__(**kwargs)
        self.restarts = restarts
        self.after_action = False

    def execute(self, action, *, stop=None, deadline=None):
        self.after_action = False
        result = super().execute(action, stop=stop, deadline=deadline)
        self.after_action = True
        return result

    def raw_capture(self, focus=True):
        return super().capture(focus=focus)

    def capture(self, focus=True):
        after_action, self.after_action = self.after_action, False
        try:
            return self.raw_capture(focus=focus)
        except RuntimeError:
            if not after_action or not self.restarts.reopen("after_confirmed_input"):
                raise
            return self.raw_capture(focus=focus)


class QuitRestarts:
    def __init__(self, backend):
        self.backend = backend
        self.stop = None

    def guard(self):
        if self.stop is None or self.stop.is_set() or (self.backend.root / "STOP").exists():
            raise InterruptedError("Quit restart cancelled")
        state = json.loads((self.backend.root / "trial.json").read_text())
        started = state["started_at"]
        elapsed = max(state.get("elapsed_seconds", 0), time.time() - started)
        remaining = effective_deadline(state) - started - elapsed
        if remaining <= 0:
            raise InterruptedError("Original trial deadline reached during quit restart")
        return elapsed, remaining

    def missing(self):
        try:
            self.backend.adapter.find()
        except RuntimeError as exc:
            if str(exc) == MISSING:
                return True
            raise
        return False

    def before_poll(self):
        process = self.backend.process
        return process is not None and process.poll() is not None and self.reopen("between_turns")

    def reopen(self, phase):
        backend = self.backend
        if self.stop is None or backend.process is None or not self.missing():
            return False
        _, remaining = self.guard()
        end = time.monotonic() + min(EXIT_GRACE_SECONDS, remaining)
        while backend.process.poll() is None and time.monotonic() < end:
            self.guard()
            self.stop.wait(0.1)
        if backend.process.poll() != 0:
            return False
        elapsed, _ = self.guard()
        raw, _ = backend.native_save()
        backend.preserve_save(raw, elapsed)
        directory = backend.folder / "lifecycle"
        directory.mkdir(exist_ok=True)
        attempt = directory / f"restart-{len(list(directory.glob('restart-*'))) + 1:04d}"
        attempt.mkdir()
        journal = attempt / "events.jsonl"
        old = dict(backend.identity)
        event(journal, "normal_exit_verified", elapsed=elapsed, phase=phase, process=old)
        try:
            self.launch_existing(attempt)
            elapsed, _ = self.guard()
            backend.persist()
            event(
                journal,
                "same_profile_reopened",
                elapsed=elapsed,
                process=backend.identity,
                agent_context="unchanged",
            )
            return True
        except Exception as exc:
            event(journal, "restart_failed", error_type=type(exc).__name__)
            if backend.identity != old:
                backend.stop_process()
            raise

    def launch_existing(self, attempt):
        backend = self.backend
        _, remaining = self.guard()
        end = time.monotonic() + min(REOPEN_SECONDS, remaining)
        with (backend.profile / (attempt.name + ".local.log")).open("w") as log:
            backend.process = subprocess.Popen(
                command(backend.game),
                cwd=backend.game,
                env=environment(backend.game, backend.profile / "prefix"),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        backend.identity = backend.process_identity(backend.process.pid)
        backend.adapter.window = None
        previous = None
        while time.monotonic() < end:
            self.guard()
            if backend.process.poll() is not None:
                raise RuntimeError("Understand exited while reopening its existing profile")
            try:
                current = backend.window_identity()
                frame = backend.adapter.raw_capture()
            except RuntimeError:
                previous = None
            else:
                if current == previous:
                    frame.save(attempt / "reopened.png")
                    return
                previous = current
            self.stop.wait(0.5)
        raise RuntimeError("Existing Understand profile did not reopen before its charged deadline")
