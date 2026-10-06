"""Direct native launch with isolated profiles; evidence is each newly written native save."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from ...desktop import X11Desktop
from ...pause import PausableProcess, ProcessPause
from ...storage import sha256, write_json
from .saves import read_save
from .setup import BINARY, config_dir, environment, save_slot

SIZE = (1280, 720)
LOAD_BUTTON = (0.404, 0.84)
FIRST_SLOT = (0.469, 0.181)
ENERGY_BAR = (1236, 530, 1258, 690)
IDENTITY_FILES = ("Stardew Valley.dll", "StardewValley.GameData.dll", "Stardew Valley.deps.json")


def in_game(image):
    """Detect the in-game energy bar."""
    pixels = image.convert("RGB").crop(ENERGY_BAR).tobytes()
    green = sum(
        1
        for i in range(0, len(pixels), 3)
        if pixels[i + 1] > 180 and pixels[i] < 120 and pixels[i + 2] < 120
    )
    return green / (len(pixels) // 3) > 0.5


def load_menu(image):
    """Detect the load-game menu."""
    r, g, b = image.convert("RGB").getpixel((640, 420))
    return r > 220 and 170 < g < 235 and b < 170


class Backend(PausableProcess):
    """Load the prepared save in an isolated profile and preserve each new native save."""

    pause_name = "Stardew Valley"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = X11Desktop(title="Stardew Valley", input_backend="xtest")
        self.process = self.profile = self.folder = self.identity = None
        self.seen = self.initial = None

    def process_identity(self):
        """Identify the game process by PID and start time."""
        pid = self.identity["pid"] if self.process is None else self.process.pid
        stat = Path(f"/proc/{pid}/stat").read_text()
        return {"pid": pid, "start_ticks": stat.rsplit(")", 1)[1].split()[19]}

    def running(self):
        """Report whether the recorded game process is still alive."""
        if self.process is not None:
            return self.process.poll() is None
        try:
            stat = Path(f"/proc/{self.identity['pid']}/stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            return False
        return stat[0] != "Z" and stat[19] == self.identity["start_ticks"]

    def checkpoint(self):
        """Record the game process and the last preserved save for resumption."""
        return {"process": self.process_identity(), "seen": self.seen}

    def freeze(self):
        """Stop the verified game process."""
        if self.pause_handle is None:
            self.pause_handle = ProcessPause(
                self.identity, self.process_identity, name=self.pause_name
            )
        self.pause_handle.freeze()

    def stop_process(self):
        """Release any pause and terminate the game's process group."""
        self.release_pause()
        if self.identity is None or not self.running():
            return
        os.killpg(self.identity["pid"], signal.SIGTERM)
        for _ in range(100):
            if not self.running():
                return
            time.sleep(0.1)
        os.killpg(self.identity["pid"], signal.SIGKILL)

    def wait(self, seconds, stop, deadline):
        """Wait during preparation unless cancelled or past the deadline."""
        if (
            stop.wait(min(seconds, max(0, deadline - time.monotonic())))
            or time.monotonic() >= deadline
        ):
            raise InterruptedError("Stardew Valley preparation deadline or cancellation")

    def click(self, point, stop, deadline):
        """Click a normalized screen point."""
        self.adapter.execute(
            {"type": "click", "x": point[0], "y": point[1]}, stop=stop, deadline=deadline
        )

    def launch(self, stop, deadline):
        """Start the game in the isolated profile and place its window."""
        with (self.profile / "stdout.local.log").open("w") as log:
            self.process = subprocess.Popen(
                [str(self.installation / BINARY)],
                cwd=self.installation,
                env=environment(self.profile),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.process_identity()
        write_json(
            self.root / "runtime.local.json",
            {"snapshot": str(self.snapshot), "installation": str(self.installation)},
        )
        end = min(deadline, time.monotonic() + 90)
        while True:
            try:
                window = self.adapter.find()
                break
            except RuntimeError:
                if time.monotonic() >= end:
                    raise
                self.wait(0.5, stop, deadline)
        window.configure(x=0, y=0, width=SIZE[0], height=SIZE[1])
        self.adapter.d.sync()
        self.wait(2, stop, deadline)

    def enter_save(self, stop, deadline):
        """Open the first save slot from the title screen and report whether gameplay loaded."""
        end = min(deadline, time.monotonic() + 120)
        while time.monotonic() < end:
            frame = self.adapter.capture()
            if in_game(frame):
                return True
            if load_menu(frame):
                self.click(FIRST_SLOT, stop, deadline)
                self.wait(5, stop, deadline)
            else:
                self.click((0.5, 0.55), stop, deadline)
                self.wait(1.5, stop, deadline)
                self.click(LOAD_BUTTON, stop, deadline)
                self.wait(2.5, stop, deadline)
        return False

    def prepare(self, folder, stop, deadline):
        """Copy the snapshot save into a fresh isolated profile and load it."""
        self.stop_process()
        if self.snapshot is None:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        self.folder = Path(folder).resolve()
        self.profile = (
            self.root.parent / ".profiles" / self.root.name / self.folder.name
        ).resolve()
        target = config_dir(self.profile)
        shutil.copytree(self.snapshot / "Saves", target / "Saves")
        if (self.snapshot / "startup_preferences").exists():
            shutil.copyfile(self.snapshot / "startup_preferences", target / "startup_preferences")
        (self.profile / "home/.local/share").mkdir(parents=True, exist_ok=True)
        self.initial = read_save(self.save_path().read_bytes())
        self.launch(stop, deadline)
        entered = self.enter_save(stop, deadline)
        (self.folder / "evidence").mkdir()
        self.seen = sha256(self.save_path())
        return {"verified": entered, "initial": self.initial}

    def save_path(self):
        """Return the main save file of the episode profile."""
        return save_slot(config_dir(self.profile))[1]

    def poll(self, elapsed):
        """Preserve a changed, fully written native save."""
        if not self.running():
            raise RuntimeError("Stardew Valley process exited")
        raw = self.save_path().read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum == self.seen:
            return None
        try:
            ET.fromstring(raw)
        except ET.ParseError:
            return None
        self.seen = checksum
        path = self.folder / "evidence" / f"{time.time_ns()}.save"
        path.write_bytes(raw)
        row = {
            "kind": "save",
            "path": str(path.relative_to(self.root)),
            "sha256": checksum,
            "elapsed": elapsed,
        }
        with (self.folder / "evidence.jsonl").open("a") as file:
            file.write(json.dumps(row) + "\n")
        return None

    def recover(self, folder, checkpoint):
        """Reattach to the recorded game process if it still runs, resuming after its last save."""
        self.folder = Path(folder).resolve()
        self.profile = (
            self.root.parent / ".profiles" / self.root.name / self.folder.name
        ).resolve()
        self.process, self.identity = None, checkpoint["process"]
        index = self.folder / "evidence.jsonl"
        rows = index.read_text().splitlines() if index.exists() else []
        self.seen = json.loads(rows[-1])["sha256"] if rows else checkpoint["seen"]
        self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
        if not self.running():
            return False
        os.kill(self.identity["pid"], signal.SIGCONT)
        self.adapter.release_all(recovery=True)
        return True

    def close(self, preserve=False):
        """Close the desktop adapter and, unless preserved, the game."""
        self.release_pause()
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
