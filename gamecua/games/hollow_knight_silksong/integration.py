"""Native Linux episodes on WSL D3D12 with isolated XDG saves and the zero-health death save as the episode end."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import numpy as np

from ...desktop import X11Desktop
from ...pause import PausableProcess, ProcessPause
from ...storage import write_json
from .progress import facts, summary
from .setup import (
    APP_ID,
    ARGUMENTS,
    PREFS,
    SAVE,
    SAVES,
    SNAPSHOT_FILES,
    TITLE,
    save_directory,
    steam_account,
)

TITLE_SEQUENCE = ((40, "Return"), (5, "Return"), (25, None))
SPOOL = (56, 44, 108, 92)
HUD_SECONDS = 30
THAW_SETTLE_SECONDS = 0.03


def hud_visible(frame):
    """Detect the silk spool of the gameplay HUD."""
    pixels = np.asarray(frame.convert("RGB").crop(SPOOL)).astype(int)
    red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    disc = (red > 60) & (red < 130) & (green < 70) & (blue < 80) & (red - green > 25)
    bolt = (red > 200) & (green > 200) & (blue > 200)
    return bool(disc.mean() >= 0.2 and 0.005 <= bolt.mean() <= 0.05)


def official_installation():
    """Return the installed official game folder."""
    from ..steam.preparation import installed_app

    return Path(installed_app(APP_ID)["directory"])


def ensure_steam_client():
    """Start the cached official Steam client unless one is running."""
    from ..steam.preparation import client_identity, start_cached_client

    if not client_identity():
        start_cached_client()


def native_environment(profile):
    """Isolate the game's XDG folders and select the Mesa D3D12 driver."""
    return dict(
        os.environ,
        SteamAppId=str(APP_ID),
        SteamGameId=str(APP_ID),
        XDG_CONFIG_HOME=str(profile / "config"),
        XDG_DATA_HOME=str(profile / "data"),
        XDG_CACHE_HOME=str(profile / "cache"),
        LIBGL_ALWAYS_SOFTWARE="0",
        GALLIUM_DRIVER="d3d12",
    )


class Backend(PausableProcess):
    """Load the prepared save from the title screen and preserve each new native save."""

    pause_name = "Silksong"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = X11Desktop(title=TITLE, input_backend="xtest")
        self.profile = self.folder = self.process = self.identity = self.save = None
        self.initial = self.seen = None

    def process_identity(self):
        """Identify the game process by PID and start time."""
        pid = self.identity["pid"] if self.process is None else self.process.pid
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": stat[19]}

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

    def thaw(self):
        """Resume the game and let it render before input."""
        if self.pause_handle is not None:
            super().thaw()
            time.sleep(THAW_SETTLE_SECONDS)

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
            raise InterruptedError("Preparation deadline or cancellation")

    def install_profile(self, account):
        """Copy the snapshot save and preferences into the isolated profile."""
        saves = self.profile / "config" / SAVES / account
        saves.mkdir(parents=True)
        (self.profile / "config" / PREFS).parent.mkdir(parents=True)
        for name, relative in SNAPSHOT_FILES.items():
            target = self.profile / "config" / PREFS if relative is None else saves / relative
            shutil.copyfile(self.snapshot / name, target)
        (self.profile / "data").mkdir()
        (self.profile / "cache").mkdir()
        self.save = saves / SAVE

    def launch(self, stop, deadline):
        """Start the game and place its window."""
        with (self.profile / "stdout.local.log").open("w") as output:
            self.process = subprocess.Popen(
                [
                    str(self.installation / TITLE),
                    *ARGUMENTS,
                    "-logFile",
                    str(self.profile / "player.log"),
                ],
                cwd=self.installation,
                env=native_environment(self.profile),
                stdout=output,
                stderr=output,
                start_new_session=True,
            )
        self.identity = self.process_identity()
        write_json(
            self.root / "runtime.local.json",
            {"snapshot": str(self.snapshot), "installation": str(self.installation)},
        )
        end = min(deadline, time.monotonic() + 120)
        while True:
            try:
                window = self.adapter.find()
                break
            except RuntimeError:
                if time.monotonic() >= end:
                    raise
                self.wait(0.5, stop, deadline)
        window.configure(x=0, y=0, width=1280, height=720)
        self.adapter.d.sync()

    def prepare(self, folder, stop, deadline):
        """Load the prepared save in a fresh isolated profile and wait for the gameplay HUD."""
        self.stop_process()
        if self.snapshot is None:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        self.installation = self.installation or official_installation()
        self.initial = summary((self.snapshot / SAVE).read_bytes())
        ensure_steam_client()
        self.folder = Path(folder)
        self.profile = (
            self.root.parent / ".profiles" / self.root.name / self.folder.name
        ).resolve()
        self.profile.mkdir(parents=True)
        self.install_profile(steam_account(self.installation))
        self.launch(stop, deadline)
        for seconds, key in TITLE_SEQUENCE:
            self.wait(seconds, stop, deadline)
            if key:
                self.adapter.execute(
                    {"type": "control", "keys": [key]}, stop=stop, deadline=deadline
                )
        end = min(deadline, time.monotonic() + HUD_SECONDS)
        while not hud_visible(self.adapter.capture()) and time.monotonic() < end:
            self.wait(1, stop, deadline)
        (self.folder / "evidence").mkdir()
        self.seen = hashlib.sha256(self.save.read_bytes()).hexdigest()
        return {"verified": hud_visible(self.adapter.capture()), "initial": self.initial}

    def poll(self, elapsed):
        """Preserve a changed, fully written native save and return its terminal outcome."""
        if not self.running():
            raise RuntimeError("Dedicated native game process exited")
        raw = self.save.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum == self.seen:
            return None
        try:
            _, terminal = facts("save", raw, self.initial)
        except (ValueError, IndexError):
            return None
        self.seen = checksum
        path = self.folder / "evidence" / f"{time.time_ns()}.dat"
        path.write_bytes(raw)
        row = {
            "kind": "save",
            "path": str(path.relative_to(self.root)),
            "sha256": checksum,
            "elapsed": elapsed,
        }
        with (self.folder / "evidence.jsonl").open("a") as file:
            file.write(json.dumps(row) + "\n")
        return terminal

    def recover(self, folder, checkpoint):
        """Reattach to the recorded game process if it still runs, resuming after its last save."""
        self.folder = Path(folder)
        self.profile = (
            self.root.parent / ".profiles" / self.root.name / self.folder.name
        ).resolve()
        self.save = save_directory(self.profile / "config") / SAVE
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
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
