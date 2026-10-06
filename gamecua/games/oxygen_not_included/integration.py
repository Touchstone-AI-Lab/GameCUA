"""Native ONI preparation and passive save collection for canonical Trials."""

import hashlib
import json
import os
import signal
import struct
import subprocess
import time
import zlib
from pathlib import Path

from ...desktop import X11Desktop
from ...pause import ProcessPause
from ...storage import write_json
from ..steam.preparation import verify_cached_session
from .loss import receipt
from .native import read_save
from .progress import facts
from .render import settle
from .setup import (
    command,
    config_dir,
    environment,
    install_profile,
    link_steam_runtime,
    stage_launcher,
)
from .startup import simulation_state
from .ui import preparation_action

START_POLICY = "running_before_first_decision_v1"


class Backend:
    """Game backend that runs ONI in a private profile and preserves its saves."""

    pause_handle = None
    startup_pending = False

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = X11Desktop(title="Oxygen Not Included", input_backend="xtest")
        self.process = self.identity = self.profile = self.folder = self.initial = None
        self.seen = set()
        self.terminal = None

    def process_identity(self):
        """Return the game's pid and kernel start time, failing once it has exited."""
        pid = self.identity["pid"]
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            raise RuntimeError("ONI process has exited")
        return {"pid": pid, "start_ticks": stat[19]}

    def stop_process(self):
        """Terminate the game process group, killing it after ten seconds."""
        self.release_pause()
        try:
            if not self.identity or self.process_identity() != self.identity:
                return
            os.killpg(self.identity["pid"], signal.SIGTERM)
            end = time.monotonic() + 10
            while time.monotonic() < end and self.process_identity():
                time.sleep(0.1)
            os.killpg(self.identity["pid"], signal.SIGKILL)
        except (OSError, RuntimeError):
            pass
        if self.process:
            self.process.wait(timeout=5)

    def freeze(self):
        """Stop every game thread with SIGSTOP."""
        self.assert_runtime()
        if self.pause_handle is None:
            self.pause_handle = ProcessPause(self.identity, self.process_identity, name="ONI")
        self.pause_handle.freeze()

    def thaw(self):
        """Resume a frozen game."""
        if self.pause_handle is not None:
            self.pause_handle.thaw()

    def settle_action(self, stop, deadline):
        """Wait until the window has presented the result of the last input."""
        self.assert_runtime()
        return settle(self.adapter.find().id, stop, deadline)

    def release_pause(self):
        """Resume the game and drop the pause handle."""
        handle, self.pause_handle = self.pause_handle, None
        if handle is not None:
            handle.release()

    def wait(self, seconds, stop, deadline):
        """Sleep, raising on cancellation or when the deadline passes."""
        if (
            stop.wait(min(seconds, max(0, deadline - time.monotonic())))
            or time.monotonic() >= deadline
        ):
            raise InterruptedError("ONI preparation deadline or cancellation")

    def save_paths(self):
        """Return every save file in the profile."""
        root = config_dir(self.profile)
        return sorted(
            path
            for name in ("save_files", "cloud_save_files")
            for path in (root / name).rglob("*.sav")
            if path.is_file()
        )

    def assert_runtime(self):
        """Raise when the game process has exited."""
        if self.process and self.process.poll() is not None:
            raise RuntimeError("ONI exited during execution")
        self.process_identity()

    def enter_save(self, stop, deadline):
        """Click through the startup menus until the prepared save is loaded."""
        end = min(deadline, time.monotonic() + 480)
        acted = {}
        while time.monotonic() < end:
            self.assert_runtime()
            try:
                frame = self.adapter.capture()
            except RuntimeError:
                self.wait(1, stop, end)
                continue
            cue = preparation_action(frame)
            if cue and cue[0] == "loaded":
                log = (self.profile / "Player.local.log").read_text(errors="replace")
                if "Active Mods (0):" not in log:
                    raise RuntimeError("ONI mods must remain disabled")
                return frame
            if cue and acted.get(cue[0], 0) < (3 if cue[0] == "base_resume" else 1):
                acted[cue[0]] = acted.get(cue[0], 0) + 1
                if cue[0] == "base_resume":
                    self.wait(3, stop, end)
                self.adapter.execute(cue[1], stop=stop, deadline=end)
                self.wait(2, stop, end)
            else:
                self.wait(1, stop, end)
        raise RuntimeError("ONI save did not reach the gameplay screen")

    def prepare(self, folder, stop, deadline):
        """Launch ONI on a fresh copy of the snapshot and return the episode setup."""
        self.stop_process()
        self.terminal = None
        verify_cached_session()
        if not self.snapshot:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        self.folder = Path(folder).resolve()
        self.profile = (
            self.root.parent / ".profiles" / self.root.name / self.folder.name
        ).resolve()
        raw = install_profile(self.snapshot, self.profile)
        stage_launcher(self.installation, self.profile)
        link_steam_runtime(self.profile)
        with (self.profile / "stdout.local.log").open("w") as log:
            self.process = subprocess.Popen(
                command(self.profile),
                cwd=self.profile,
                env=environment(self.profile),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = {"pid": self.process.pid}
        self.identity = self.process_identity()
        write_json(
            self.root / "runtime.local.json",
            {
                "profile": str(self.profile),
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "process": self.identity,
            },
        )
        frame = self.enter_save(stop, deadline)
        self.initial = read_save(raw)
        (self.folder / "evidence").mkdir()
        baseline = self.folder / "evidence/initial.sav"
        baseline.write_bytes(raw)
        frame.save(self.folder / "initial.png")
        self.seen = {self.initial["sha256"]}
        self.startup_pending = True
        self.startup_stop = stop
        self.startup_deadline = deadline
        return {
            "schema_version": 1,
            "verified": True,
            "simulation_start": START_POLICY,
            "experiment_kind": "prepared_state",
            "initial": self.initial,
            "initial_evidence": str(baseline.relative_to(self.root)),
            "setup_frame": str((self.folder / "initial.png").relative_to(self.root)),
        }

    def checkpoint(self):
        """Return the process state that a recovery must find again."""
        self.assert_runtime()
        return {"process": self.process_identity(), "profile": self.profile.name}

    def preserve(self, kind, raw, elapsed):
        """Copy new evidence into the episode and index it."""
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum in self.seen:
            return
        extension = "sav" if kind == "save" else "loss.json"
        target = self.folder / "evidence" / f"{time.time_ns()}.{extension}"
        target.write_bytes(raw)
        row = {
            "kind": kind,
            "path": str(target.relative_to(self.root)),
            "sha256": checksum,
            "elapsed": elapsed,
        }
        with (self.folder / "evidence.jsonl").open("a") as index:
            index.write(json.dumps(row) + "\n")
        self.seen.add(checksum)

    def start_simulation(self, elapsed):
        """Unpause the loaded colony once before the first decision."""
        self.startup_pending = False
        state = simulation_state(self.adapter.capture())
        if state not in {"paused", "running"}:
            raise RuntimeError("ONI startup pause state is unrecognized")
        frozen = self.pause_handle is not None and self.pause_handle.stopped()
        end = min(self.startup_deadline, time.monotonic() + 5)
        try:
            if state == "paused":
                if frozen:
                    self.thaw()
                self.adapter.execute(
                    {"type": "control", "keys": ["space"], "duration": 0.1},
                    stop=self.startup_stop,
                    deadline=end,
                )
                while True:
                    self.wait(0.1, self.startup_stop, end)
                    if simulation_state(self.adapter.capture()) == "running":
                        break
            write_json(
                self.folder / "simulation-start.json",
                {
                    "policy": START_POLICY,
                    "elapsed": elapsed,
                    "before": state,
                    "status": "completed",
                },
            )
        finally:
            self.adapter.release_all()
            if frozen:
                self.freeze()

    def poll(self, elapsed):
        """Preserve new saves and the Colony Lost screen, returning death once seen."""
        self.assert_runtime()
        if self.startup_pending:
            self.start_simulation(elapsed)
        log = (self.profile / "Player.local.log").read_text(errors="replace")
        if log.count("Loading save file:") > 1:
            raise RuntimeError("ONI must not load another save inside an episode")
        for path in self.save_paths():
            before = path.stat().st_mtime_ns
            raw = path.read_bytes()
            if before != path.stat().st_mtime_ns or hashlib.sha256(raw).hexdigest() in self.seen:
                continue
            try:
                _, terminal = facts("save", raw, self.initial)
            except (ValueError, struct.error, zlib.error):
                continue
            self.preserve("save", raw, elapsed)
            self.terminal = self.terminal or terminal
        if not self.terminal:
            raw = receipt(self.adapter.capture(focus=False))
            if raw is not None:
                self.preserve("history", raw, elapsed)
                self.terminal = "death"
        return self.terminal

    def recover(self, folder, checkpoint):
        """Reattach to the still-running game after a harness restart."""
        local = json.loads((self.root / "runtime.local.json").read_text())
        self.profile, self.snapshot, self.installation = (
            Path(local[key]) for key in ("profile", "snapshot", "installation")
        )
        self.folder, self.identity = Path(folder), local["process"]
        setup = json.loads((self.folder / "setup.json").read_text())
        self.startup_pending = False
        startup = self.folder / "simulation-start.json"
        if not startup.exists() or json.loads(startup.read_text()).get("status") != "completed":
            return False
        self.initial = setup["initial"]
        self.seen = {self.initial["sha256"]}
        self.terminal = None
        index = self.folder / "evidence.jsonl"
        rows = (
            [json.loads(line) for line in index.read_text().splitlines()] if index.exists() else []
        )
        self.adapter.release_all(recovery=True)
        try:
            for row in rows:
                self.seen.add(row["sha256"])
                _, terminal = facts(row["kind"], (self.root / row["path"]).read_bytes(), None)
                self.terminal = self.terminal or terminal
            self.adapter.find()
            return self.process_identity() == checkpoint["process"]
        except (KeyError, OSError, RuntimeError, ValueError):
            return False

    def close(self, preserve=False):
        """Release the window and stop the game unless it is preserved for recovery."""
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
