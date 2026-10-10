"""Native stage pause and bounded native steps, with a process stop during known transitions."""

import json
import time
import uuid
from pathlib import Path

from ...pause import ProcessPause
from ...storage import write_json


class Pause:
    def __init__(self, directory, binding, identity, wait_checkpoint):
        self.directory, self.binding = Path(directory), binding
        self.wait_checkpoint = wait_checkpoint
        self.process = ProcessPause(identity, lambda: identity, name="Art of Rally")
        self.owned = self.transition = False
        self.last_ack = None

    def request(self, paused, timeout, checked=False, **extra):
        identifier = uuid.uuid4().hex
        write_json(
            self.directory / "request.json",
            {
                "binding": self.binding,
                "id": identifier,
                "paused": paused,
                "allow_transitions": True,
                **extra,
            },
        )
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if checked:
                self.wait_checkpoint()
            try:
                ack = json.loads((self.directory / "ack.json").read_bytes())
            except (FileNotFoundError, json.JSONDecodeError):
                ack = {}
            if ack.get("id") == identifier:
                if ack.get("error"):
                    raise RuntimeError(f"Native pause failed: {ack['error']}")
                return ack
            time.sleep(0.005)
        raise TimeoutError("Native pause acknowledgement timed out")

    def freeze(self):
        self.wait_checkpoint()
        if self.process.fd is not None:
            self.process.freeze()
            return self.last_ack
        try:
            ack = self.request(True, 120 if self.transition else 5, checked=True)
            self.transition = ack.get("disposition") == "transition_unfrozen"
            if self.transition:
                self.owned = False
                self.wait_checkpoint()
                self.process.freeze()
                ack = {**ack, "disposition": "transition_process_frozen"}
            else:
                self.owned = True
            self.last_ack = ack
            return ack
        except BaseException:
            self.owned = True
            self.thaw()
            raise

    def thaw(self):
        try:
            self.process.thaw()
        finally:
            self.last_ack = None
            if self.owned:
                self.owned = False
                self.request(False, 5)

    release = thaw


class NativeStep:
    def __init__(self, pause, seconds):
        self.pause, self.seconds = pause, seconds
        self.identifier = self.record = None
        self.transition_frozen = self.aborted = False

    def guard(self):
        if self.stop.is_set() or time.monotonic() >= self.deadline:
            raise InterruptedError("Native step cancelled or original deadline reached")

    def start(self, stop, deadline):
        self.stop, self.deadline = stop, deadline
        self.identifier = uuid.uuid4().hex
        pause = self.pause
        write_json(
            pause.directory / "request.json",
            {
                "binding": pause.binding,
                "id": self.identifier,
                "paused": False,
                "allow_transitions": True,
                "step_seconds": self.seconds,
            },
        )
        end = min(deadline, time.monotonic() + 5)
        while time.monotonic() < end:
            self.guard()
            try:
                ack = json.loads((pause.directory / "ack.json").read_bytes())
            except (FileNotFoundError, json.JSONDecodeError):
                ack = {}
            if ack.get("id") == self.identifier:
                if ack.get("error"):
                    raise RuntimeError(f"Native step failed: {ack['error']}")
                pause.owned = pause.transition = False
                pause.last_ack = None
                return
            stop.wait(0.005)
        self.guard()
        raise TimeoutError("Native step resume acknowledgement timed out")

    def sample(self):
        self.guard()
        try:
            record = json.loads((self.pause.directory / "step.json").read_bytes())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if record.get("id") != self.identifier:
            return None
        if record.get("error"):
            raise RuntimeError(f"Native step failed: {record['error']}")
        if record["state"] == "completed":
            self.pause.owned = True
        elif record["state"] == "transition" and not self.transition_frozen:
            self.pause.freeze()
            self.transition_frozen = True
        self.record = record
        return record

    def wait_until(self, target):
        target = min(target, self.seconds)
        while True:
            record = self.sample()
            if record is not None and (
                record["state"] != "running" or record["elapsed_seconds"] >= target - 0.000001
            ):
                return record
            self.stop.wait(0.005)

    def finish(self):
        while True:
            record = self.wait_until(self.seconds)
            if record["state"] != "running":
                return record
            self.stop.wait(0.005)

    def abort(self):
        if (
            self.aborted
            or self.identifier is None
            or (self.record and self.record["state"] != "running")
        ):
            return
        ack = self.pause.request(True, 2)
        self.pause.owned = ack.get("disposition") != "transition_unfrozen"
        self.aborted = True


class NativeWait:
    def __init__(self, step, stop, deadline):
        self.step, self.stop, self.deadline = step, stop, deadline
        self.elapsed = 0.0

    def is_set(self):
        return self.stop.is_set()

    def start(self):
        if self.step.identifier is None:
            self.step.start(self.stop, self.deadline)

    def wait(self, seconds):
        self.start()
        self.elapsed = min(self.elapsed + seconds, self.step.seconds)
        self.step.wait_until(self.elapsed)
        return self.stop.is_set()


class StepAdapter:
    def __init__(self, backend):
        self.backend = backend

    def __getattr__(self, name):
        return getattr(self.backend.desktop, name)

    def execute(self, action, *, stop=None, deadline=None):
        desktop, step = self.backend.desktop, self.backend.native_step
        if step is None:
            return desktop.execute(action, stop=stop, deadline=deadline)
        self.backend.native_step = None
        self.backend.executing_native_step = step
        native_stop = NativeWait(step, stop, deadline)
        try:
            desktop.execute(action, stop=native_stop, deadline=deadline)
            native_stop.start()
            step.finish()
        finally:
            try:
                desktop.release_all()
            finally:
                if step.record is None or step.record["state"] == "running":
                    step.abort()
