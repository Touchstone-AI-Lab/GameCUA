"""Isolated Understand episodes launched from a frozen native save under official Proton."""

import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from ...catalog import digest
from ...storage import write_json
from .lifecycle import QuitRestarts, RestartDesktop
from .progress import facts
from .setup import SAVE, command, environment, stage_game

SIZE = (1280, 720)


def fraction(image, box, predicate):
    values = image.convert("RGB").crop(box).tobytes()
    return sum(predicate(*values[index : index + 3]) for index in range(0, len(values), 3)) / (
        len(values) // 3
    )


def initial_menu(image):
    return (
        image.size == SIZE
        and fraction(image, (25, 25, 85, 85), lambda r, g, b: max(r, g, b) < 100) > 0.8
        and fraction(image, (532, 270, 539, 450), lambda r, g, b: max(r, g, b) < 60) > 0.8
        and fraction(
            image,
            (1000, 500, 1020, 520),
            lambda r, g, b: max(r, g, b) - min(r, g, b) < 5 and 200 < r < 240,
        )
        > 0.95
    )


class Backend:
    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.quit_restarts = QuitRestarts(self)
        self.adapter = RestartDesktop(
            self.quit_restarts, title="Understand", size=SIZE, input_backend="xtest"
        )
        self.process = self.identity = self.profile = self.folder = None
        self.initial = self.seen = None

    @property
    def game(self):
        return self.profile / "game"

    def process_identity(self, pid=None):
        pid = pid or self.identity["pid"]
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            raise RuntimeError("Understand process exited")
        return {"pid": pid, "start_ticks": stat[19]}

    def stop_process(self):
        if not self.identity:
            return
        try:
            if self.process_identity() != self.identity:
                return
            os.killpg(self.identity["pid"], signal.SIGTERM)
            if self.process:
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(self.identity["pid"], signal.SIGKILL)
                    self.process.wait(timeout=5)
        except (OSError, RuntimeError):
            pass

    def window_identity(self):
        window = self.adapter.find()
        geometry = window.get_geometry()
        return {"window_id": window.id, "width": geometry.width, "height": geometry.height}

    def persist(self):
        write_json(
            self.root / "runtime.local.json",
            {
                "profile": str(self.profile),
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "process": self.identity,
            },
        )

    def launch(self, stop, deadline):
        with (self.profile / "launch.local.log").open("w") as log:
            self.process = subprocess.Popen(
                command(self.game),
                cwd=self.game,
                env=environment(self.game, self.profile / "prefix"),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.process_identity(self.process.pid)
        end = min(deadline, time.monotonic() + 240)
        stable = 0
        while time.monotonic() < end:
            if self.process.poll() is not None:
                raise RuntimeError(
                    "Understand exited during startup; inspect private launch output"
                )
            try:
                geometry = self.window_identity()
                ready = (geometry["width"], geometry["height"]) == SIZE and initial_menu(
                    self.adapter.capture()
                )
                stable = stable + 1 if ready else 0
                if stable >= 2:
                    return
            except RuntimeError:
                stable = 0
            if stop.wait(0.5):
                raise InterruptedError("Understand preparation cancelled")
        raise RuntimeError("Understand zero-progress opening menu did not appear")

    def native_save(self):
        raw = (self.game / SAVE).read_bytes()
        return raw, json.loads(raw)

    def prepare(self, folder, stop, deadline):
        self.quit_restarts.stop = stop
        self.stop_process()
        if self.snapshot is None:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        manifest = json.loads((self.snapshot / "snapshot.manifest.json").read_text())
        write_json(self.root / "snapshot.provenance.json", {"snapshot_hash": digest(manifest)})
        self.folder = Path(folder).resolve()
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        stage_game(self.installation, self.snapshot, self.profile)
        self.launch(stop, deadline)
        raw, data = self.native_save()
        self.initial = {"active_slot": data[0]}
        (self.folder / "evidence").mkdir()
        baseline = self.folder / "evidence/initial.save"
        baseline.write_bytes(raw)
        self.seen = hashlib.sha256(raw).hexdigest()
        self.adapter.capture().save(self.folder / "initial.png")
        self.persist()
        return {
            "schema_version": 1,
            "verified": True,
            "initial": self.initial,
            "initial_evidence": str(baseline.relative_to(self.root)),
            "setup_frame": str((self.folder / "initial.png").relative_to(self.root)),
            "episode_profile_isolated": True,
        }

    def checkpoint(self):
        return {"process": self.identity, "save_sha256": self.seen}

    def poll(self, elapsed):
        self.quit_restarts.before_poll()
        try:
            raw, _ = self.native_save()
        except (OSError, ValueError):
            return None
        return self.preserve_save(raw, elapsed)

    def preserve_save(self, raw, elapsed):
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum != self.seen:
            evidence = self.folder / "evidence" / f"{time.time_ns()}.save"
            evidence.write_bytes(raw)
            row = {
                "kind": "save",
                "path": str(evidence.relative_to(self.root)),
                "sha256": checksum,
                "elapsed": elapsed,
            }
            with (self.folder / "evidence.jsonl").open("a") as file:
                file.write(json.dumps(row) + "\n")
            self.seen = checksum
        return facts("save", raw, self.initial)[1]

    def recover(self, folder, checkpoint):
        try:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.profile, self.snapshot, self.installation = (
                Path(local[name]) for name in ("profile", "snapshot", "installation")
            )
            self.folder, self.identity = Path(folder), local["process"]
            self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
            self.seen = checkpoint["save_sha256"]
            if self.process_identity() != self.identity:
                return False
            self.adapter.release_all(recovery=True)
            return True
        except (OSError, ValueError, KeyError, RuntimeError):
            return False

    def close(self, preserve=False):
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
