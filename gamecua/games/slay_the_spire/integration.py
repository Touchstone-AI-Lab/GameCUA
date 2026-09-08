"""Dedicated Java profiles protect personal saves and isolate episode evidence."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from ...desktop import X11Desktop
from ...pause import PausableProcess
from ...storage import sha256, write_json
from .progress import facts
from .saves import decode_autosave
from .setup import ENCOUNTER, default_game_dir, public_log

CONTINUE = (0.096, 0.701)
STATE_DIRS = ("saves", "preferences")
SETUP_KEYS = (
    "seed",
    "act_num",
    "floor_num",
    "current_room",
    "post_combat",
    "cards",
    "relics",
    "current_health",
    "max_health",
    "ascension_level",
    "monsters_killed",
    "metric_damage_taken",
)


def running(identity):
    """Return whether the recorded pid still has the recorded kernel start time."""
    try:
        stat = Path(f"/proc/{identity['pid']}/stat").read_text()
    except OSError:
        return False
    return stat.rsplit(")", 1)[1].split()[19] == identity["start_ticks"]


class Backend(PausableProcess):
    pause_name = "Slay the Spire"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else default_game_dir()
        self.adapter = X11Desktop(input_backend="xsend")
        self.profile = self.folder = self.process = self.identity = self.terminal = None
        self.seen = {}

    def wait(self, seconds, stop, deadline):
        if (
            stop.wait(min(seconds, max(0, deadline - time.monotonic())))
            or time.monotonic() >= deadline
        ):
            raise InterruptedError("Preparation deadline or cancellation")

    def freeze(self):
        """Retry the pause because the JVM sometimes stops its threads slowly."""
        for attempt in range(3):
            try:
                return super().freeze()
            except RuntimeError as error:
                if "did not confirm" not in str(error) or attempt == 2:
                    raise
                self.release_pause()
                time.sleep(0.2)

    def stop_process(self):
        self.release_pause()
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=10)
        elif self.identity and running(self.identity):
            try:
                os.kill(self.identity["pid"], signal.SIGTERM)
            except OSError:
                pass

    def log_text(self):
        path = self.profile / "sendToDevs/logs/SlayTheSpire.log"
        return path.read_text(errors="replace") if path.exists() else ""

    def prepare(self, folder, stop, deadline):
        self.stop_process()
        if self.snapshot is None:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        initial = decode_autosave((self.snapshot / "saves/IRONCLAD.autosave").read_bytes())
        provenance = json.loads((self.snapshot / "GOLDEN.json").read_text())
        self.folder = folder
        self.profile = (self.root.parent / ".profiles" / self.root.name / folder.name).resolve()
        self.profile.mkdir(parents=True)
        for name in STATE_DIRS:
            shutil.copytree(self.snapshot / name, self.profile / name)
        (folder / "evidence").mkdir()
        with (self.profile / "launch.log").open("w") as log:
            self.process = subprocess.Popen(
                [
                    str(self.installation / "jre/bin/java"),
                    "-Xmx1G",
                    "-Dsun.java2d.dpiaware=true",
                    "-jar",
                    str(self.installation / "desktop-1.0.jar"),
                ],
                cwd=self.profile,
                env=dict(os.environ, SteamAppId="646570", SteamGameId="646570"),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.checkpoint()
        write_json(
            self.root / "runtime.local.json",
            {
                "profile": str(self.profile),
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "process": self.identity,
            },
        )
        end = min(deadline, time.monotonic() + 90)
        while time.monotonic() < end:
            try:
                self.adapter.find()
                break
            except RuntimeError:
                self.wait(0.5, stop, deadline)
        else:
            raise RuntimeError("Dedicated game window unavailable")
        while "IRONCLAD save exists and is valid." not in self.log_text():
            if time.monotonic() >= end:
                raise RuntimeError("Dedicated game menu did not finish loading")
            self.wait(0.5, stop, deadline)
        self.wait(1, stop, deadline)
        offset = len(self.log_text())
        encounter = None
        for _ in range(3):
            self.adapter.execute(
                {"type": "move", "x": CONTINUE[0], "y": CONTINUE[1]}, stop=stop, deadline=deadline
            )
            self.wait(0.5, stop, deadline)
            self.adapter.execute(
                {"type": "mouse_hold", "button": "left", "duration": 0.4},
                stop=stop,
                deadline=deadline,
            )
            for _ in range(20):
                self.wait(0.5, stop, deadline)
                encounters = ENCOUNTER.findall(self.log_text()[offset:])
                if encounters:
                    encounter = encounters[-1]
                    break
            if encounter:
                break
        self.wait(3, stop, deadline)
        save = self.profile / "saves/IRONCLAD.autosave"
        data = decode_autosave(save.read_bytes())
        expected = provenance.get("initial_state", {}).get("encounter", "Cultist")
        verified = all(data.get(k) == initial.get(k) for k in SETUP_KEYS) and encounter == expected
        self.adapter.capture().save(folder / "initial.png")
        (folder / "evidence/initial.autosave").write_bytes(save.read_bytes())
        self.seen = {"save": sha256(save)}
        self.terminal = None
        self.log_offset = 0
        self.initial = data
        return {
            "schema_version": 1,
            "verified": verified,
            "experiment_kind": "prepared_state",
            "provenance": provenance,
            "initial": data,
            "encounter_from_log": encounter,
        }

    def checkpoint(self):
        pid = self.process.pid if self.process else self.identity["pid"]
        stat = Path(f"/proc/{pid}/stat").read_text()
        return {"pid": pid, "start_ticks": stat.rsplit(")", 1)[1].split()[19]}

    def recover(self, folder, checkpoint):
        local = json.loads((self.root / "runtime.local.json").read_text())
        self.profile, self.snapshot, self.installation = (
            Path(local[name]) for name in ("profile", "snapshot", "installation")
        )
        self.identity, self.folder = local["process"], folder
        self.initial = json.loads((folder / "setup.json").read_text())["initial"]
        self.adapter.release_all(recovery=True)
        self.seen = {}
        self.log_offset = 0
        self.terminal = None
        return running(self.identity)

    def preserve(self, kind, raw, elapsed, suffix):
        checksum = hashlib.sha256(raw).hexdigest()
        if self.seen.get(kind) == checksum:
            return
        self.seen[kind] = checksum
        path = self.folder / "evidence" / f"{time.time_ns()}{suffix}"
        path.write_bytes(raw)
        row = {
            "kind": kind.split(":", 1)[0],
            "path": str(path.relative_to(self.root)),
            "elapsed": elapsed,
        }
        with (self.folder / "evidence.jsonl").open("a") as file:
            file.write(json.dumps(row) + "\n")

    def poll(self, elapsed):
        if self.process is not None and self.process.poll() is not None:
            raise RuntimeError("Dedicated game process exited")
        save = self.profile / "saves/IRONCLAD.autosave"
        if save.exists():
            raw = save.read_bytes()
            try:
                decode_autosave(raw)
                self.preserve("save", raw, elapsed, ".autosave")
            except ValueError:
                pass
        for path in sorted(self.profile.glob("runs/**/*.run")):
            raw = path.read_bytes()
            try:
                if str(json.loads(raw).get("seed_played")) != str(self.initial["seed"]):
                    continue
            except ValueError:
                continue
            self.preserve("history:" + path.name, raw, elapsed, ".run")
            self.terminal = facts("history", raw, self.initial)[1] or self.terminal
        log = self.profile / "sendToDevs/logs/SlayTheSpire.log"
        if log.exists():
            raw = log.read_bytes()
            end = raw.rfind(b"\n") + 1
            if end > self.log_offset:
                projected = public_log(raw[self.log_offset : end])
                if projected:
                    self.preserve("log", projected, elapsed, ".log")
                self.log_offset = end
        return self.terminal

    def close(self, preserve=False):
        self.adapter.close()
        if not preserve:
            self.stop_process()


def capture_snapshot(installation, target, encounter):
    """Copy the game's save and preference folders into a new snapshot."""
    installation, target = Path(installation).resolve(), Path(target).resolve()
    initial = decode_autosave((installation / "saves/IRONCLAD.autosave").read_bytes())
    target.mkdir(parents=True)
    for name in STATE_DIRS:
        shutil.copytree(installation / name, target / name)
    write_json(
        target / "GOLDEN.json",
        {
            "id": target.name,
            "derivation": "Read-only capture of an existing save/profile; prepared-state experiment, not a claim of an unmodified fresh seeded run",
            "initial_state": {"encounter": encounter, "seed": initial["seed"]},
        },
    )
    write_json(
        target / "snapshot.manifest.json",
        {str(p.relative_to(target)): sha256(p) for p in sorted(target.rglob("*")) if p.is_file()},
    )
    return target
