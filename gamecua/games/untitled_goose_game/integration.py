"""Official Proton episodes with isolated profiles and native save evidence."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image
from Xlib import X
from Xlib.error import BadMatch

from ...desktop import X11Desktop
from ...pause import PausableProcess, ProcessPause
from ...storage import sha256, write_json
from ..steam.preparation import CLIENT
from .saves import SaveFormatError, read_save
from .setup import BINARY, PROTON_METADATA, SAVE_DIRECTORY, environment

RESOLUTION = (1280, 720)


class GooseDesktop(X11Desktop):
    """X11 desktop that falls back to a root-window capture when Proton's window cannot be read."""

    def capture(self, focus=True):
        try:
            return super().capture(focus)
        except BadMatch:
            self.focus() if focus else self.find()
        geometry = self.root.get_geometry()
        raw = self.root.get_image(0, 0, geometry.width, geometry.height, X.ZPixmap, 0xFFFFFFFF)
        self.geometry = {
            "width": geometry.width,
            "height": geometry.height,
            "window_id": self.root.id,
        }
        return Image.frombytes(
            "RGB", (geometry.width, geometry.height), raw.data, "raw", "BGRX"
        ).resize(self.size, Image.Resampling.LANCZOS)


class Backend(PausableProcess):
    """Launch, observe, pause and stop one Proton game process per episode."""

    pause_name = "Untitled Goose Game"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = GooseDesktop(
            title="Untitled Goose Game", input_backend="xtest", mouse_mode="cursor"
        )
        self.process = self.identity = self.profile = self.folder = None
        self.initial = {"completed": []}
        self.seen = {}

    def save_paths(self):
        """Return the native slot saves in the episode profile."""
        return sorted((self.profile / SAVE_DIRECTORY).glob("savegame*.save"))

    def process_identity(self):
        """Return the pid and kernel start time of the Proton launcher."""
        pid = self.process.pid if self.process else self.identity["pid"]
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": stat[19]}

    def freeze(self):
        """Suspend every thread of the launcher process."""
        if self.pause_handle is None:
            self.pause_handle = ProcessPause(
                self.identity, self.process_identity, name=self.pause_name
            )
        self.pause_handle.freeze()

    def persist_runtime(self):
        """Store what recovery needs to reattach to the running episode."""
        write_json(
            self.root / "runtime.local.json",
            {
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "profile": str(self.profile),
                "process": self.identity,
            },
        )

    def stop_process(self):
        """Terminate the Proton process group."""
        self.release_pause()
        if self.identity:
            try:
                os.killpg(self.identity["pid"], signal.SIGTERM)
            except OSError:
                pass
        if self.process:
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(self.identity["pid"], signal.SIGKILL)
                self.process.wait(timeout=5)
        self.process = self.identity = None

    def prepare(self, folder, stop, deadline):
        """Restore the snapshot into a fresh profile and wait for the title screen."""
        self.stop_process()
        proton = CLIENT / "steamapps/common/Proton - Experimental/proton"
        self.folder = Path(folder).resolve()
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        self.profile.mkdir(parents=True, exist_ok=False)
        shutil.copytree(self.snapshot / "pfx", self.profile / "pfx", symlinks=True)
        for name in PROTON_METADATA:
            shutil.copy2(self.snapshot / name, self.profile / name)
        (self.profile / SAVE_DIRECTORY).mkdir(parents=True, exist_ok=True)
        with (self.profile / "launch.private.log").open("w") as log:
            self.process = subprocess.Popen(
                [
                    str(proton),
                    "run",
                    str(self.installation / BINARY),
                    "-screen-fullscreen",
                    "0",
                    "-screen-width",
                    str(RESOLUTION[0]),
                    "-screen-height",
                    str(RESOLUTION[1]),
                ],
                cwd=self.installation,
                env=environment(self.profile, CLIENT),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.process_identity()
        end = min(deadline, time.monotonic() + 180)
        frame = None
        while not stop.is_set() and time.monotonic() < end:
            if self.process.poll() is not None:
                raise RuntimeError("Official Proton launch exited; inspect private launch log")
            try:
                image = self.adapter.capture()
                if image.size == RESOLUTION and float(np.asarray(image).std()) > 10:
                    frame = image
                    break
            except RuntimeError:
                pass
            stop.wait(0.5)
        if frame is None:
            raise InterruptedError("Untitled Goose Game title screen did not become ready")
        (self.folder / "evidence").mkdir()
        baseline = self.folder / "evidence/initial.json"
        write_json(baseline, self.initial)
        frame.save(self.folder / "initial.png")
        self.persist_runtime()
        return {
            "verified": True,
            "initial": self.initial,
            "initial_evidence": str(baseline.relative_to(self.root)),
            "experiment_kind": "fresh_title_screen",
            "proton_version": (proton.parent / "version").read_text().strip(),
            "native_evidence": "Game-written BinaryFormatter slot saves from the isolated profile",
        }

    def checkpoint(self):
        """Identify the running process and profile for recovery."""
        return {"process": self.process_identity(), "profile": self.profile.name}

    def poll(self, elapsed):
        """Preserve every new complete slot save as native evidence."""
        for path in self.save_paths():
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            if checksum == self.seen.get(path.name):
                continue
            try:
                read_save(raw)
            except SaveFormatError:
                continue
            self.seen[path.name] = checksum
            evidence = self.folder / "evidence" / f"{time.time_ns()}.save"
            evidence.write_bytes(raw)
            with (self.folder / "evidence.jsonl").open("a") as index:
                index.write(
                    json.dumps(
                        {
                            "kind": "save",
                            "path": str(evidence.relative_to(self.root)),
                            "elapsed": elapsed,
                        }
                    )
                    + "\n"
                )
                index.flush()
                os.fsync(index.fileno())
        return None

    def recover(self, folder, checkpoint):
        """Reattach to the episode process after a harness restart."""
        local = json.loads((self.root / "runtime.local.json").read_text())
        self.snapshot, self.installation, self.profile = (
            Path(local[name]) for name in ("snapshot", "installation", "profile")
        )
        self.folder, self.identity = Path(folder), local["process"]
        self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
        self.seen = {path.name: sha256(path) for path in self.save_paths()}
        self.adapter.release_all(recovery=True)
        try:
            self.adapter.find()
            return self.checkpoint()["process"] == checkpoint["process"]
        except (OSError, RuntimeError, ValueError):
            return False

    def close(self, preserve=False):
        """Release input and stop the game unless it is preserved."""
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
