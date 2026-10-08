"""Repentance under Proton: fresh data directory per episode, fixed-seed start, native-log evidence."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from ...desktop import X11Desktop
from ...storage import write_json
from .progress import RUN_START, facts, project
from .setup import (
    DATA_DIRECTORY,
    command,
    data_directory,
    environment,
    installation_identity,
    normalize_seed,
)

MENU_TO_SEED = ("space", "space", "space", "space")


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


class Backend:
    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = X11Desktop(
            title="Binding of Isaac", title_prefix=True, input_backend="xtest"
        )
        self.prefix = Path(tempfile.gettempdir()) / "gamecua-isaac" / self.root.name
        self.process = self.profile = self.folder = self.identity = None
        self.initial = None
        self.seen = None

    def checkpoint(self):
        pid = self.process.pid if self.process else self.identity["pid"]
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start_ticks": stat[19]}

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
        subprocess.run(["pkill", "-9", "-f", "isaac-ng.exe"], capture_output=True)
        for _ in range(40):
            try:
                self.adapter.window = None
                self.adapter.find()
            except RuntimeError:
                return
            time.sleep(0.25)

    def game_processes(self):
        found = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid != os.getuid():
                    continue
                if b"isaac-ng.exe" in (entry / "cmdline").read_bytes():
                    found.append(int(entry.name))
            except OSError:
                continue
        return found

    def signal_game(self, signum):
        pids = self.game_processes()
        for pid in pids:
            try:
                os.kill(pid, signum)
            except OSError:
                continue
        return pids

    def freeze(self):
        if not self.signal_game(signal.SIGSTOP):
            raise RuntimeError("No Isaac game process to pause")

    def thaw(self):
        self.signal_game(signal.SIGCONT)

    def wait(self, seconds, stop, deadline):
        if (
            stop.wait(min(seconds, max(0, deadline - time.monotonic())))
            or time.monotonic() >= deadline
        ):
            raise InterruptedError("Preparation deadline or cancellation")

    def log_path(self):
        return data_directory(self.prefix) / "log.txt"

    def native_lines(self):
        path = self.log_path()
        if not path.exists():
            return []
        raw = path.read_bytes()
        return project(raw[: raw.rfind(b"\n") + 1].decode("utf-8", errors="replace"))

    def press(self, key, stop, deadline, settle=1.0):
        self.adapter.execute({"type": "press", "key": key}, stop=stop, deadline=deadline)
        self.wait(settle, stop, deadline)

    def dismiss_dialogs(self):
        dismissed = []
        for name, key in (("^Error$", "Return"), ("^Valve Hardware Survey$", "Escape")):
            found = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--name", name],
                capture_output=True,
                text=True,
            ).stdout.split()
            for window in found:
                subprocess.run(["xdotool", "windowactivate", "--sync", window], capture_output=True)
                subprocess.run(["xdotool", "key", key], capture_output=True)
                dismissed.append(name)
        return dismissed

    def launch(self, stop, deadline):
        data = data_directory(self.prefix)
        shutil.rmtree(data, ignore_errors=True)
        data.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.snapshot / "data" / DATA_DIRECTORY, data)
        with (self.profile / "launch.local.log").open("w") as log:
            self.process = subprocess.Popen(
                command(self.installation),
                cwd=self.installation,
                env=environment(self.installation, self.prefix),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.checkpoint()
        self.dialogs = []
        end = min(deadline, time.monotonic() + 240)
        while time.monotonic() < end:
            if self.process.poll() is not None:
                raise RuntimeError("Isaac exited during launch; inspect the private profile")
            self.dialogs += self.dismiss_dialogs()
            try:
                self.adapter.window = None
                self.adapter.find()
                break
            except RuntimeError:
                self.wait(1, stop, deadline)
        else:
            raise RuntimeError("Dedicated Isaac window unavailable")
        self.wait(3, stop, deadline)
        self.dialogs += self.dismiss_dialogs()
        self.place(stop, deadline)

    def place(self, stop, deadline):
        window = self.adapter.find()
        for _ in range(10):
            window.configure(x=0, y=0, width=1280, height=720)
            self.adapter.d.sync()
            self.wait(0.3, stop, deadline)
            origin = window.translate_coords(self.adapter.root, 0, 0)
            if (origin.x, origin.y) == (0, 0):
                return
        raise RuntimeError("Isaac window could not be placed at the display origin")

    def raw_log(self):
        path = self.log_path()
        return path.read_text(errors="replace") if path.exists() else ""

    def await_log(self, text, seconds, stop, deadline):
        end = min(deadline, time.monotonic() + seconds)
        while time.monotonic() < end:
            if self.process.poll() is not None:
                raise RuntimeError("Isaac exited during preparation")
            if text in self.raw_log():
                return True
            self.wait(0.5, stop, deadline)
        return False

    def start_seeded_run(self, seed, stop, deadline):
        if not self.await_log("playing cutscene 1 (Intro)", 180, stop, deadline):
            raise RuntimeError("Isaac intro did not start")
        self.wait(2, stop, deadline)
        self.place(stop, deadline)
        for key in MENU_TO_SEED:
            self.press(key, stop, deadline, settle=2.0)
        self.press("Tab", stop, deadline, settle=1.5)
        for char in seed.replace(" ", "").lower():
            self.press(char, stop, deadline, settle=0.4)
        self.press("Return", stop, deadline, settle=1.5)
        self.press("space", stop, deadline, settle=1.0)
        if not self.await_log("(Start Room)", 30, stop, deadline):
            return None
        self.wait(2, stop, deadline)
        self.place(stop, deadline)
        starts = [line for line in self.native_lines() if RUN_START.match(line)]
        return RUN_START.match(starts[0]).group(1) if starts else None

    def prepare(self, folder, stop, deadline):
        folder = Path(folder).resolve()
        self.stop_process()
        if not self.snapshot:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        setup = json.loads((self.snapshot / "GOLDEN.json").read_text())
        seed = normalize_seed(setup["seed"])
        self.folder = folder
        started = None
        for attempt in range(1, 3):
            self.stop_process()
            self.profile = (
                self.root.parent / ".profiles" / self.root.name / f"{folder.name}-{attempt}"
            ).resolve()
            self.profile.mkdir(parents=True)
            self.launch(stop, deadline)
            started = self.start_seeded_run(seed, stop, deadline)
            if started:
                break
            self.adapter.capture(focus=False).save(self.profile / "preparation-failure.png")
        shutil.copy2(self.log_path(), self.profile / "preparation-log.local.txt")
        self.initial = {"episode_id": folder.name, "seed": seed}
        write_json(
            self.root / "runtime.local.json",
            {
                "profile": str(self.profile),
                "prefix": str(self.prefix),
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "process": self.identity,
            },
        )
        (folder / "evidence").mkdir()
        path = folder / "evidence/initial.json"
        write_json(path, self.evidence(self.native_lines()))
        self.seen = None
        self.adapter.capture().save(folder / "initial.png")
        found, terminal = facts("save", path.read_bytes(), self.initial)
        return {
            "schema_version": 1,
            "verified": started == seed and not found and terminal is None,
            "experiment_kind": "fresh_seeded_run",
            "golden": setup,
            "installation": installation_identity(self.installation),
            "initial": self.initial,
            "seed_from_log": started,
            "dismissed_dialogs": self.dialogs,
            "preparation_attempts": attempt,
        }

    def evidence(self, lines):
        return {"schema_version": 1, **self.initial, "lines": lines}

    def poll(self, elapsed):
        if self.process is not None and self.process.poll() is not None:
            raise RuntimeError("Isaac exited")
        raw = json.dumps(self.evidence(self.native_lines()), sort_keys=True).encode()
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum == self.seen:
            return None
        self.seen = checksum
        path = self.folder / "evidence" / f"{time.time_ns()}.json"
        path.write_bytes(raw)
        with (self.folder / "evidence.jsonl").open("a") as file:
            row = {"kind": "save", "path": str(path.relative_to(self.root)), "elapsed": elapsed}
            file.write(json.dumps(row) + "\n")
        return facts("save", raw, self.initial)[1]

    def recover(self, folder, checkpoint):
        local = json.loads((self.root / "runtime.local.json").read_text())
        self.profile, self.snapshot, self.installation, self.prefix = (
            Path(local[name]) for name in ("profile", "snapshot", "installation", "prefix")
        )
        self.folder, self.identity = folder, local["process"]
        self.initial = json.loads((folder / "setup.json").read_text())["initial"]
        self.seen = None
        self.adapter.release_all(recovery=True)
        return running(self.identity)

    def close(self, preserve=False):
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
