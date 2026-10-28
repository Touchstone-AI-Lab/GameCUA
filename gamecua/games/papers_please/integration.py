"""Fresh official story runs with ordinary input and read-only native stashes."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from ...pause import PausableProcess, ProcessPause
from ...storage import write_json
from .desktop import Desktop
from .progress import day_state, facts
from .saves import members
from .setup import screen_matches

INSTALLATION_FILES = (
    "PapersPlease",
    "UnityPlayer.so",
    "GameAssembly.so",
    "PapersPlease_Data/il2cpp_data/Metadata/global-metadata.dat",
)
DECODE_ERRORS = (ValueError, IndexError, KeyError, TypeError, ET.ParseError)


class Backend(PausableProcess):
    """Launch a fresh story from the title screen and preserve each new native proof."""

    pause_name = "Papers, Please"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = Desktop()
        self.process = self.identity = self.seen = None

    def process_identity(self):
        """Identify the game process by PID and start time."""
        pid = self.identity["pid"] if self.process is None else self.process.pid
        text = Path(f"/proc/{pid}/stat").read_text()
        return {"pid": pid, "start_ticks": text.rsplit(")", 1)[1].split()[19]}

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
        """Record the game process and the last preserved proof for resumption."""
        return {"process": self.process_identity(), "seen": self.seen}

    def freeze(self):
        """Stop the verified game process."""
        if self.pause_handle is None:
            self.pause_handle = ProcessPause(
                self.identity, self.process_identity, name=self.pause_name
            )
        self.pause_handle.freeze()

    def configure_steps(self):
        """Cap frozen-step drags at the Trial's step duration."""
        specification = self.root / "trial.spec.json"
        spec = json.loads(specification.read_text()) if specification.exists() else {}
        self.adapter.step_seconds = (
            spec.get("step_seconds") if spec.get("action_execution") == "frozen_steps" else None
        )

    def prepare(self, folder, stop, deadline):
        """Start a new English story in an isolated profile and reach the first office."""
        self.close_process()
        self.configure_steps()
        if self.snapshot is None:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        preparation = json.loads((self.snapshot / "preparation.json").read_text())
        self.initial = {"decoder_key": preparation["decoder_key"], "processed": 0}
        self.folder = Path(folder)
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        self.profile.mkdir(parents=True)
        shutil.copy2(self.snapshot / "settings.sav", self.profile / "settings.sav")
        with (self.profile / "launch.local.log").open("w") as log:
            self.process = subprocess.Popen(
                [
                    str(self.installation / "PapersPlease"),
                    "savedir",
                    str(self.profile),
                    "-logFile",
                    str(self.profile / "player.local.log"),
                ],
                cwd=self.installation,
                env=dict(os.environ, SteamAppId="239030", SteamGameId="239030"),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.process_identity()
        write_json(
            self.root / "runtime.local.json",
            {"snapshot": str(self.snapshot), "installation": str(self.installation)},
        )

        def wait(seconds):
            if stop.wait(min(seconds, max(0, deadline - time.monotonic()))) or (
                time.monotonic() >= deadline
            ):
                raise InterruptedError("Preparation interrupted")

        def click(x, y):
            self.adapter.execute({"type": "click", "x": x, "y": y}, stop=stop, deadline=deadline)

        def matches(name, box):
            return screen_matches(self.adapter.capture(), self.snapshot / name, box)

        def advance(name, box, timeout, interval, action=None):
            end = min(deadline, time.monotonic() + timeout)
            while time.monotonic() < end:
                if matches(name, box):
                    return
                if action:
                    action()
                wait(interval)
            raise RuntimeError("Native setup screen did not become ready: " + name)

        end = min(deadline, time.monotonic() + 90)
        while True:
            try:
                self.adapter.find()
                break
            except RuntimeError:
                if time.monotonic() >= end:
                    raise
                wait(0.5)
        advance("title-menu.png", (440, 530, 700, 558), 60, 0.5)
        self.adapter.execute({"type": "move", "x": 0.1, "y": 0.1}, stop=stop, deadline=deadline)
        wait(1)

        def open_story():
            if matches("title-menu.png", (440, 530, 700, 558)):
                click(283 / 569, 245 / 319)

        advance("new-menu.png", (16, 151, 134, 211), 60, 1, open_story)
        click(0.065, 0.282)
        wait(3)
        advance("office-start.png", (596, 212, 894, 606), 90, 2, lambda: click(0.5, 0.935))
        (self.folder / "evidence").mkdir()
        self.seen = None
        return {"verified": True, "initial": self.initial}

    def proof(self):
        """Return the newest native stash or active daily save with its evidence kind."""
        key = bytes.fromhex(self.initial["decoder_key"])
        stash = self.profile / "stash.sav"
        if stash.exists():
            return "history", {"stash": stash.read_text()}
        day = members((self.profile / "stats.sav").read_bytes(), key).get("Day")
        saves = []
        for path in self.profile.glob("save_*.sav"):
            raw = path.read_bytes()
            value = day_state(raw, key)
            if str(value["day"]) == day:
                saves.append((value["processed"], path.name, raw))
        if not saves:
            return None, None
        return "save", {"save": max(saves)[2].decode("ascii")}

    def poll(self, elapsed):
        """Preserve a changed native proof and return its terminal outcome."""
        if not self.running():
            raise RuntimeError("Native Papers, Please process exited")
        try:
            kind, payload = self.proof()
        except DECODE_ERRORS:
            return None
        if kind is None:
            return None
        proof = json.dumps(payload).encode()
        checksum = hashlib.sha256(proof).hexdigest()
        if checksum == self.seen:
            return None
        try:
            terminal = facts(kind, proof, self.initial)[1]
        except DECODE_ERRORS:
            return None
        path = self.folder / "evidence" / f"{time.time_ns()}.native.json"
        path.write_bytes(proof)
        row = {
            "kind": kind,
            "path": str(path.relative_to(self.root)),
            "sha256": checksum,
            "elapsed": elapsed,
        }
        with (self.folder / "evidence.jsonl").open("a") as file:
            file.write(json.dumps(row) + "\n")
        self.seen = checksum
        return terminal

    def recover(self, folder, checkpoint):
        """Reattach to the recorded game process if it still runs, resuming after its last proof."""
        self.folder = Path(folder)
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        self.process, self.identity = None, checkpoint["process"]
        index = self.folder / "evidence.jsonl"
        rows = index.read_text().splitlines() if index.exists() else []
        self.seen = json.loads(rows[-1])["sha256"] if rows else checkpoint["seen"]
        self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
        if not self.running():
            return False
        os.kill(self.identity["pid"], signal.SIGCONT)
        self.configure_steps()
        self.adapter.release_all(recovery=True)
        return True

    def close_process(self):
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

    def close(self, preserve=False):
        """Close the desktop adapter and, unless preserved, the game."""
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.close_process()
