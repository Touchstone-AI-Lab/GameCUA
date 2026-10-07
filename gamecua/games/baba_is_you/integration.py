"""Direct native launch with isolated profiles; evidence is each newly written slot save."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from ...desktop import X11Desktop
from ...storage import sha256, write_json
from .saves import read_save
from .setup import SETTINGS, command, data_dir, environment, slot_paths

IDENTITY_FILES = ("bin64/Chowdren", "Assets.dat", "Data/values.lua", "Data/rules.lua")
SPLASH_LOGO = (516, 510, 580, 570)
OPENING_YOU = (514, 253, 549, 287)
OPENING_WIN = (802, 253, 837, 287)


def running(identity):
    """Return whether the recorded pid still has the recorded kernel start time."""
    try:
        stat = Path(f"/proc/{identity['pid']}/stat").read_text()
    except OSError:
        return False
    return stat.rsplit(")", 1)[1].split()[19] == identity["start_ticks"]


def signal_group(identity, sig):
    """Signal the recorded process group unless its leader pid now names another process."""
    pid = identity["pid"]
    if running(identity) or not Path(f"/proc/{pid}").exists():
        try:
            os.killpg(pid, sig)
        except OSError:
            pass


def fraction(image, box, test):
    pixels = image.convert("RGB").crop(box).tobytes()
    count = len(pixels) // 3
    return (
        sum(1 for i in range(0, len(pixels), 3) if test(pixels[i], pixels[i + 1], pixels[i + 2]))
        / count
    )


def pink(r, g, b):
    return r > 170 and g < 110 and 70 < b < 160


def yellow(r, g, b):
    return r > 200 and g > 190 and b < 160


def splash(image):
    return fraction(image, SPLASH_LOGO, pink) > 0.4


def opening_level(image):
    return fraction(image, OPENING_YOU, pink) > 0.5 and fraction(image, OPENING_WIN, yellow) > 0.5


class Backend:
    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = X11Desktop(title="Baba Is You", input_backend="xtest")
        self.process = self.profile = self.folder = self.identity = None
        self.seen = {}
        self.initial = None

    def process_identity(self):
        pid = self.process.pid if self.process else self.identity["pid"]
        stat = Path(f"/proc/{pid}/stat").read_text()
        return {"pid": pid, "start_ticks": stat.rsplit(")", 1)[1].split()[19]}

    def stop_process(self):
        if not self.identity:
            return
        signal_group(self.identity, signal.SIGTERM)
        if self.process:
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                signal_group(self.identity, signal.SIGKILL)
                self.process.wait(timeout=5)

    def wait(self, seconds, stop, deadline):
        if (
            stop.wait(min(seconds, max(0, deadline - time.monotonic())))
            or time.monotonic() >= deadline
        ):
            raise InterruptedError("Baba Is You preparation deadline or cancellation")

    def launch(self, stop, deadline):
        with (self.profile / "stdout.local.log").open("w") as log:
            self.process = subprocess.Popen(
                command(self.installation),
                cwd=self.installation,
                env=environment(self.profile),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.process_identity()
        end = min(deadline, time.monotonic() + 90)
        while time.monotonic() < end:
            if self.process.poll() is not None:
                raise RuntimeError("Baba Is You exited during launch; inspect private profile")
            try:
                self.adapter.find()
                return
            except RuntimeError:
                self.wait(0.5, stop, deadline)
        raise RuntimeError("Baba Is You window unavailable")

    def enter_opening(self, stop, deadline):
        end = min(deadline, time.monotonic() + 120)
        matched = 0
        while time.monotonic() < end:
            frame = self.adapter.capture()
            if opening_level(frame):
                matched += 1
                if matched >= 3:
                    return True
            else:
                matched = 0
                if splash(frame):
                    self.adapter.execute(
                        {"type": "press", "key": "Return"}, stop=stop, deadline=deadline
                    )
            self.wait(1, stop, deadline)
        return False

    def prepare(self, folder, stop, deadline):
        folder = Path(folder).resolve()
        self.stop_process()
        if not self.snapshot:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        self.folder = folder
        self.profile = (self.root.parent / ".profiles" / self.root.name / folder.name).resolve()
        target = data_dir(self.profile)
        target.mkdir(parents=True)
        shutil.copyfile(self.snapshot / "Baba_Is_You" / SETTINGS, target / SETTINGS)
        self.launch(stop, deadline)
        entered = self.enter_opening(stop, deadline)
        slots = [path for path in slot_paths(self.profile) if path.exists()]
        baseline_raw = slots[0].read_bytes() if len(slots) == 1 else b""
        self.initial = read_save(baseline_raw)
        write_json(
            self.root / "runtime.local.json",
            {
                "profile": str(self.profile),
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "process": self.identity,
            },
        )
        (folder / "evidence").mkdir()
        (folder / "evidence/initial.save").write_bytes(baseline_raw)
        self.seen = {path.name: sha256(path) for path in slots}
        self.adapter.capture().save(folder / "initial.png")
        return {
            "schema_version": 1,
            "verified": entered and len(slots) == 1 and not self.initial["cleared"],
            "experiment_kind": "prepared_state",
            "initial": self.initial,
        }

    def checkpoint(self):
        return self.process_identity()

    def poll(self, elapsed):
        if self.process is not None and self.process.poll() is not None:
            raise RuntimeError("Baba Is You process exited")
        for path in slot_paths(self.profile):
            if not path.exists():
                continue
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            if checksum == self.seen.get(path.name):
                continue
            self.seen[path.name] = checksum
            evidence = self.folder / "evidence" / f"{time.time_ns()}.save"
            evidence.write_bytes(raw)
            with (self.folder / "evidence.jsonl").open("a") as file:
                row = {
                    "kind": "save",
                    "path": str(evidence.relative_to(self.root)),
                    "elapsed": elapsed,
                }
                file.write(json.dumps(row) + "\n")
        return None

    def recover(self, folder, checkpoint):
        local = json.loads((self.root / "runtime.local.json").read_text())
        self.profile, self.snapshot, self.installation = (
            Path(local[name]) for name in ("profile", "snapshot", "installation")
        )
        self.folder, self.identity = folder, local["process"]
        self.initial = json.loads((folder / "setup.json").read_text())["initial"]
        self.seen = {}
        self.adapter.release_all(recovery=True)
        return running(self.identity)

    def close(self, preserve=False):
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
