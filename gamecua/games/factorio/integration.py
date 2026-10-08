"""Isolated Factorio episodes with evaluator-only native telemetry."""

import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

from Xlib import X

from ...desktop import X11Desktop
from ...pause import PausableProcess, ProcessPause
from ...storage import write_json
from .progress import facts
from .setup import command, configure, environment
from .transport_pause import TransportPause


class Backend(PausableProcess):
    """Launch, observe, pause and stop one Factorio process per episode."""

    pause_name = "Factorio"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = X11Desktop(title="Factorio", title_prefix=True, input_backend="xtest")
        self.process = self.process_id = self.profile = self.folder = self.initial = None
        self.offset = 0
        self.transport_pause = (
            TransportPause(self) if os.environ.get("GAMECUA_FACTORIO_PAUSE_ON_413") == "1" else None
        )

    def process_identity(self):
        """Return the pid and kernel start time of the game process."""
        pid = self.process.pid if self.process else self.process_id["pid"]
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": fields[19]}

    def log_path(self):
        """Return the native telemetry stream written by the evidence mod."""
        return self.profile / "script-output/gamecua/evaluation.jsonl"

    def checkpoint(self):
        """Identify the running process for recovery."""
        return {"process": self.process_identity()}

    def freeze(self):
        """Suspend every thread of the game process."""
        if self.pause_handle is None:
            self.pause_handle = ProcessPause(
                self.process_id, self.process_identity, name=self.pause_name
            )
        self.pause_handle.freeze()

    def stop_process(self):
        """Terminate the game process."""
        if self.transport_pause is not None:
            self.transport_pause.reset("game_stop")
        self.release_pause()
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        elif self.process_id:
            try:
                os.kill(self.process_id["pid"], signal.SIGTERM)
            except OSError:
                pass
        self.process = self.process_id = None

    def read_rows(self):
        """Return complete telemetry rows written since the last read."""
        path = self.log_path()
        if not path.exists():
            return []
        with path.open("rb") as file:
            file.seek(self.offset)
            raw = file.read()
        end = raw.rfind(b"\n") + 1
        self.offset += end
        return [json.loads(line) for line in raw[:end].splitlines()]

    def persist_runtime(self):
        """Store what recovery needs to reattach to the running episode."""
        write_json(
            self.root / "runtime.local.json",
            {
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "profile": str(self.profile),
                "process": self.process_id,
                "offset": self.offset,
            },
        )

    def prepare(self, folder, stop, deadline):
        """Start a fresh profile from the snapshot and wait for the first native sample."""
        self.stop_process()
        if self.snapshot is None or self.installation is None:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        preparation = json.loads((self.snapshot / "preparation.json").read_text())
        steam = preparation["installation"]["distribution"] == "steam"
        self.folder = Path(folder).resolve()
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        configure(self.profile, self.snapshot, self.installation, {"session_id": uuid.uuid4().hex})
        self.offset = 0
        with (self.profile / "stdout.local.log").open("w") as log:
            self.process = subprocess.Popen(
                command(self.installation, self.profile),
                cwd=self.profile,
                env=environment(self.profile, steam=steam),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.process_id = self.process_identity()
        end = min(deadline, time.monotonic() + 180)
        rows = []
        while time.monotonic() < end and not stop.is_set():
            if self.process.poll() is not None:
                raise RuntimeError("Factorio exited; inspect private profile logs")
            rows.extend(self.read_rows())
            if rows:
                try:
                    window = self.adapter.find()
                    pid = window.get_full_property(
                        self.adapter.d.intern_atom("_NET_WM_PID"), X.AnyPropertyType
                    )
                    if pid and int(pid.value[0]) == self.process.pid:
                        frame = self.adapter.capture()
                        break
                except RuntimeError:
                    pass
            stop.wait(min(0.2, max(0, end - time.monotonic())))
        else:
            raise InterruptedError("Factorio preparation cancelled or timed out")
        self.initial = rows[-1]
        evidence = self.folder / "evidence"
        evidence.mkdir()
        path = evidence / "initial.json"
        write_json(path, rows)
        frame.save(self.folder / "initial.png")
        self.persist_runtime()
        return {
            "verified": True,
            "initial": self.initial,
            "initial_evidence": str(path.relative_to(self.root)),
            "preparation": preparation,
            "runtime_settings": (self.profile / "config.ini").read_text(),
        }

    def poll(self, elapsed):
        """Preserve new native rows as evidence and return any terminal state."""
        rows = self.read_rows()
        if not rows:
            return None
        path = self.folder / "evidence" / f"{time.time_ns()}.json"
        write_json(path, rows)
        with (self.folder / "evidence.jsonl").open("a") as file:
            file.write(
                json.dumps(
                    {"kind": "save", "path": str(path.relative_to(self.root)), "elapsed": elapsed}
                )
                + "\n"
            )
            file.flush()
            os.fsync(file.fileno())
        self.persist_runtime()
        return facts("save", path.read_bytes(), self.initial)[1]

    def recover(self, folder, checkpoint):
        """Reattach to the episode process after a harness restart."""
        try:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation, self.profile = (
                Path(local[key]) for key in ("snapshot", "installation", "profile")
            )
            self.folder, self.process_id, self.offset = (
                Path(folder),
                local["process"],
                local["offset"],
            )
            self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
            self.adapter.release_all(recovery=True)
            self.adapter.find()
            return self.checkpoint()["process"] == checkpoint["process"]
        except (OSError, ValueError, RuntimeError, KeyError):
            return False

    def close(self, preserve=False):
        """Release input and pauses, and stop the game unless it is preserved."""
        try:
            if self.transport_pause is not None:
                self.transport_pause.close()
                self.transport_pause = None
            self.release_pause()
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
