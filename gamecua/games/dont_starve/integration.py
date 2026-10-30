"""Native Steam client, menu-driven save loading and read-only observer evidence."""

import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image
from Xlib import X

from ...pause import PausableProcess
from ...storage import sha256, write_json
from .desktop import Desktop
from .progress import facts
from .setup import (
    ProfileLease,
    configure,
    environment,
    installation_identity,
    process_identity,
    validate_snapshot,
)

OBSERVER = re.compile(rb"GAMECUA_OBSERVER (\{.*\})")


def frame_matches(reference, image, region):
    a = np.asarray(reference.convert("RGB").crop(region), dtype=float)
    b = np.asarray(image.convert("RGB").crop(region), dtype=float)
    return float(np.abs(a - b).mean()) < 8


def following_menu_matches(snapshot, steps, index, frame):
    for following in steps[index + 1 :]:
        reference = Image.open(snapshot / "reference" / following["frame"])
        if frame_matches(reference, frame, following["region"]):
            return True
        if not following.get("optional"):
            break
    return False


class Backend(PausableProcess):
    pause_name = "Don't Starve"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = Desktop("Don't Starve", input_backend="xtest", mouse_mode="cursor")
        self.process = self.identity = self.lease = self.profile = self.initial = None
        self.offset = 0

    def checkpoint(self):
        return process_identity(self.identity["pid"])

    def persist(self):
        write_json(
            self.root / "runtime.local.json",
            {
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "profile": str(self.profile),
                "process": self.identity,
                "offset": self.offset,
            },
        )

    def stop_process(self):
        self.release_pause()
        if not self.identity:
            return
        pid = self.identity["pid"]
        try:
            if process_identity(pid) == self.identity:
                os.kill(pid, signal.SIGTERM)
                if self.process:
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=5)
                else:
                    end = time.monotonic() + 10
                    while time.monotonic() < end and Path(f"/proc/{pid}").exists():
                        time.sleep(0.1)
        except (OSError, RuntimeError):
            pass
        self.process = self.identity = None

    def read_rows(self):
        path = self.profile / "stdout.local.log"
        raw = path.read_bytes() if path.exists() else b""
        end = raw.rfind(b"\n") + 1
        rows = [
            json.loads(match[1])
            for line in raw[self.offset : end].splitlines()
            if (match := OBSERVER.search(line))
        ]
        self.offset = end
        return rows

    def launch(self, stop, deadline):
        with (self.profile / "stdout.local.log").open("w") as log:
            self.process = subprocess.Popen(
                [str(self.profile / "runtime/bin/dontstarve_steam")],
                cwd=self.profile / "runtime/bin",
                env=environment(self.installation),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = process_identity(self.process.pid)
        self.persist()
        end = min(deadline, time.monotonic() + 60)
        while time.monotonic() < end and not stop.is_set():
            if self.process.poll() is not None:
                raise RuntimeError("Native client exited; inspect private process logs")
            try:
                window = self.adapter.find()
                pid = window.get_full_property(
                    self.adapter.d.intern_atom("_NET_WM_PID"), X.AnyPropertyType
                )
                if pid and int(pid.value[0]) == self.identity["pid"]:
                    self.adapter.capture()
                    return
            except RuntimeError:
                pass
            stop.wait(0.1)
        raise InterruptedError("Native window preparation timed out or was cancelled")

    def click_menus(self, plan, stop, end):
        for index, step in enumerate(plan["steps"]):
            reference = Image.open(self.snapshot / "reference" / step["frame"])
            while time.monotonic() < end and not stop.is_set():
                frame = self.adapter.capture()
                if step.get("optional") and following_menu_matches(
                    self.snapshot, plan["steps"], index, frame
                ):
                    break
                if frame_matches(reference, frame, step["region"]):
                    if stop.wait(1.0):
                        raise InterruptedError("Native menu preparation was cancelled")
                    if not frame_matches(reference, self.adapter.capture(), step["region"]):
                        continue
                    x, y = step["click"]
                    self.adapter.execute({"type": "move", "x": x, "y": y}, stop=stop, deadline=end)
                    if stop.wait(0.3):
                        raise InterruptedError("Native menu preparation was cancelled")
                    self.adapter.execute({"type": "click", "x": x, "y": y}, stop=stop, deadline=end)
                    break
                stop.wait(0.1)
            else:
                self.adapter.capture(focus=False).save(
                    self.folder / f"setup-unmatched-{index:02d}.png"
                )
                raise InterruptedError("Prepared native menu did not match its reference")

    def prepare(self, folder, stop, deadline):
        self.stop_process()
        if self.lease:
            self.lease.release()
        if not self.snapshot:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = Path(local["snapshot"]), Path(local["installation"])
        snapshot_hash, plan = validate_snapshot(self.snapshot)
        write_json(
            self.root / "snapshot.provenance.json",
            {
                "snapshot_sha256": snapshot_hash,
                "installation": installation_identity(self.installation),
            },
        )
        self.folder = Path(folder).resolve()
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        self.profile.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.snapshot / "profile", self.profile)
        configure(self.profile, self.installation, self.folder.name, snapshot_hash)
        self.lease = ProfileLease(self.profile, self.root / "profile-binding.local.json")
        self.lease.acquire()
        self.offset = 0
        self.launch(stop, deadline)
        end = min(deadline, time.monotonic() + 60)
        self.click_menus(plan, stop, end)
        observed = []
        while not observed and time.monotonic() < end and not stop.is_set():
            observed.extend(self.read_rows())
            if self.process.poll() is not None:
                raise RuntimeError("Native client exited while loading the prepared world")
            stop.wait(0.05)
        if not observed:
            raise InterruptedError("Native observer did not report the prepared world")
        if plan.get("onboarding"):
            self.show_controls(plan["onboarding"], stop, deadline)
            observed.extend(self.read_rows())
        self.initial = observed[-1]
        self.persist()
        (self.folder / "evidence").mkdir()
        path = self.folder / "evidence/initial.json"
        write_json(path, observed)
        self.adapter.capture().save(self.folder / "initial.png")
        return {
            "verified": True,
            "initial": self.initial,
            "initial_evidence": str(path.relative_to(self.root)),
            "episode_profile_isolated": True,
            "evaluator_instrumentation": "Read-only native Lua callbacks; no state edits or privileged observations sent to the agent",
            "runtime_settings": (self.profile / "settings.ini").read_text(),
            "onboarding": plan.get("onboarding", {}).get("kind", "none"),
        }

    def show_controls(self, onboarding, stop, deadline):
        end = min(deadline, time.monotonic() + 10)
        self.adapter.execute({"type": "press", "key": "Escape"}, stop=stop, deadline=end)
        for name in ("pause", "controls"):
            reference = Image.open(self.snapshot / "reference" / onboarding[name + "_frame"])
            while time.monotonic() < end and not stop.is_set():
                frame = self.adapter.capture()
                if frame_matches(reference, frame, onboarding[name + "_region"]):
                    frame.save(self.folder / f"setup-{name}.png")
                    if name == "pause":
                        self.adapter.execute(
                            {"type": "click", "x": 555 / 1279, "y": 421 / 719},
                            stop=stop,
                            deadline=end,
                        )
                    break
                stop.wait(0.05)
            else:
                raise InterruptedError("Native controls onboarding did not match its reference")

    def poll(self, elapsed):
        rows = self.read_rows()
        if not rows:
            return None
        path = self.folder / "evidence" / f"{rows[-1]['sequence']:08d}.json"
        write_json(path, rows)
        row = {
            "kind": "save",
            "path": str(path.relative_to(self.root)),
            "sha256": sha256(path),
            "elapsed": elapsed,
        }
        with (self.folder / "evidence.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        self.persist()
        return facts("save", path.read_bytes(), self.initial)[1]

    def recover(self, folder, checkpoint):
        try:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.profile, self.snapshot, self.installation = (
                Path(local[name]) for name in ("profile", "snapshot", "installation")
            )
            self.folder, self.identity, self.offset = (
                Path(folder),
                local["process"],
                local["offset"],
            )
            self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
            if process_identity(self.identity["pid"]) != self.identity:
                return False
            self.lease = ProfileLease(self.profile, self.root / "profile-binding.local.json")
            self.lease.acquire()
            self.adapter.release_all(recovery=True)
            self.adapter.capture()
            return True
        except (OSError, ValueError, KeyError, RuntimeError):
            return False

    def close(self, preserve=False):
        try:
            self.release_pause()
            if not preserve:
                self.stop_process()
                if self.lease:
                    self.lease.release()
            elif self.lease and self.lease.lock:
                self.lease.lock.close()
                self.lease.lock = None
        finally:
            self.adapter.close()
