"""Steam Proton launch, frame-guarded start-save loading and preserved native checkpoints."""

import fcntl
import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from ...desktop import X11Desktop
from ...storage import local_file, sha256, write_json
from ..steam import preparation as steam
from .base_game import NativeBaseGame
from .progress import outcome
from .runtime import (
    APP_ID,
    process_identity,
    proton_paths,
    steam_ipc_command,
)
from .setup import validate_snapshot


def frame_matches(reference, image, step):
    """Compare a guarded region of a live frame with its preserved reference frame."""
    left, top, right, bottom = step["region"]
    if step.get("metric") == "rgb":
        before = np.asarray(reference.convert("RGB"))[top:bottom, left:right].astype(float)
        actual = np.asarray(image.convert("RGB"))
        return any(
            np.abs(before - actual[top:bottom, left + offset : right + offset]).mean() <= 8
            for offset in step.get("horizontal_offsets", [0])
        )
    expected = np.asarray(reference.convert("L"))[top:bottom, left:right]
    actual = np.asarray(image.convert("L"))[top:bottom, left:right]
    expected = expected < 90 if step.get("ink") == "dark" else expected > 185
    actual = actual < 90 if step.get("ink") == "dark" else actual > 185
    union = np.count_nonzero(actual | expected)
    return bool(np.count_nonzero(actual != expected) / max(1, union) <= 0.12)


def matching_step(reference, image, step):
    """Return the step with clicks shifted to the first matching vertical offset, or None."""
    left, top, right, bottom = step["region"]
    for offset in step.get("vertical_offsets", [0]):
        aligned = image.copy()
        aligned.paste(image.crop((left, top + offset, right, bottom + offset)), (left, top))
        if frame_matches(reference, aligned, step):
            return {
                **step,
                "actions": [
                    {**action, "y": action["y"] + offset / (image.height - 1)}
                    if action["type"] == "click"
                    else action
                    for action in step.get("actions", [])
                ],
            }
    return None


class Backend:
    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = X11Desktop(
            title="Sid Meier's Civilization VI (DX11)", title_prefix=True, input_backend="xtest"
        )
        self.process = self.identity = self.profile = self.folder = self.binding = None
        self.lease = self.native = self.initial = None

    def process_identity(self):
        return process_identity(self.identity["pid"])

    def lock(self):
        self.lease = (proton_paths(steam.CLIENT)["prefix"] / "gamecua-civ6.lock").open("a")
        fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def bind_profile(self):
        """Point the Proton profile and save directories at this episode's private copy."""
        self.lock()
        paths = proton_paths(steam.CLIENT)
        self.binding = [
            {
                "target": str(path),
                "backup": str(path.with_name(path.name + ".gamecua-" + uuid.uuid4().hex)),
                "destination": str(destination),
            }
            for path, destination in (
                (paths["profile"], self.profile),
                (paths["saves"], self.profile / "Saves"),
            )
        ]
        self.persist_runtime()
        try:
            for entry in self.binding:
                target = Path(entry["target"])
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    target.rename(entry["backup"])
                target.symlink_to(entry["destination"], target_is_directory=True)
        except BaseException:
            self.restore_profile()
            raise

    def restore_profile(self):
        for entry in reversed(self.binding or []):
            target, backup = Path(entry["target"]), Path(entry["backup"])
            if target.is_symlink():
                target.unlink()
            if backup.exists() or backup.is_symlink():
                backup.rename(target)
        self.binding = None
        if self.lease:
            self.lease.close()
            self.lease = None

    def persist_runtime(self):
        write_json(
            self.root / "runtime.local.json",
            {
                "profile": str(self.profile),
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "process": self.identity,
                "binding": self.binding,
            },
        )

    def reference(self, step):
        return Image.open(local_file(self.snapshot, "reference/" + step["frame"])).convert("RGB")

    def wait_frame(self, step, stop, deadline, alternative=None, service=None, settle=0):
        """Wait for a guarded frame; None means an optional step was skipped."""
        reference = self.reference(step)
        following = self.reference(alternative) if alternative else None
        dialog = self.reference(service) if service and step["frame"] != service["frame"] else None
        image = matched_since = None
        while not stop.is_set() and time.monotonic() < deadline:
            if self.process_identity() != self.identity:
                raise RuntimeError("Native Civilization VI process changed")
            try:
                image = self.adapter.capture()
                matched = matching_step(reference, image, step)
                if matched is not None:
                    matched_since = matched_since or time.monotonic()
                    if time.monotonic() - matched_since >= settle:
                        return matched
                else:
                    matched_since = None
                    if following is not None and matching_step(following, image, alternative):
                        return None
                    if dialog is not None and frame_matches(dialog, image, service):
                        for action in service["actions"]:
                            self.menu_click(action, stop, deadline)
                        stop.wait(0.5)
            except RuntimeError:
                matched_since = None
            stop.wait(0.2)
        if image is not None:
            image.save(self.profile / "preparation-timeout.local.png")
        raise InterruptedError("Prepared-save loading timed out at a guarded native frame")

    def menu_click(self, action, stop, deadline):
        self.adapter.execute(
            {"type": "pointer", "x": action["x"], "y": action["y"]}, stop=stop, deadline=deadline
        )
        self.adapter.execute({"type": "wait", "seconds": 0.25}, stop=stop, deadline=deadline)
        self.adapter.execute(action, stop=stop, deadline=deadline)

    def prepare(self, folder, stop, deadline):
        """Launch the game on a private profile copy and load the prepared start save."""
        self.close()
        deadline = min(deadline, time.monotonic() + 360)
        preparation, start = validate_snapshot(self.snapshot)
        self.folder = Path(folder).resolve()
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        shutil.copytree(self.snapshot / "profile", self.profile)
        self.bind_profile()
        with (self.profile / "startup.local.log").open("w") as log:
            self.process = subprocess.Popen(
                steam_ipc_command(steam.CLIENT),
                cwd=self.installation,
                env=dict(os.environ, SteamAppId=str(APP_ID), SteamGameId=str(APP_ID)),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.wait_process(stop, deadline)
        self.persist_runtime()
        plan = json.loads(local_file(self.snapshot, "reference/plan.json").read_text())
        service = next((step for step in plan["steps"] if step.get("service_dialog")), None)
        for index, step in enumerate(plan["steps"]):
            alternative = plan["steps"][index + 1] if step.get("optional") else None
            matched = self.wait_frame(step, stop, deadline, alternative, service)
            for action in matched["actions"] if matched else []:
                self.menu_click(action, stop, deadline)
        self.wait_frame(plan["initial_frame"], stop, deadline, service=service, settle=3)
        self.warmup(stop, deadline)
        self.wait_frame(plan["evaluation_frame"], stop, deadline, service=service, settle=3)
        self.native = NativeBaseGame()
        state = self.native.read()
        self.initial = {
            "episode_id": uuid.uuid4().hex,
            "civilization": preparation["civilization"],
            "evaluation": "base_game_v1",
            "native_player_id": state["native_player_id"],
            "native_state": state,
        }
        baseline = self.folder / "evidence/initial.json"
        baseline.parent.mkdir()
        write_json(baseline, self.projection(state))
        self.adapter.capture().save(self.folder / "initial.png")
        return {
            "verified": True,
            "initial": self.initial,
            "initial_evidence": str(baseline.relative_to(self.root)),
            "start_save": start,
            "native_evidence": "Official game read-only native checkpoints, attributed by Game.GetLocalPlayer; evaluation state is never sent to the player.",
        }

    def wait_process(self, stop, deadline):
        """Identify the game process from its window once Steam has started it."""
        while not stop.is_set() and time.monotonic() < deadline:
            try:
                window = self.adapter.find()
            except RuntimeError:
                stop.wait(0.2)
                continue
            prop = window.get_full_property(self.adapter.d.intern_atom("_NET_WM_PID"), 0)
            return process_identity(int(prop.value[0]))
        raise InterruptedError("Official Steam launch did not produce a game window")

    def warmup(self, stop, deadline):
        """Send the single fixed Shift+Return preparation turn."""
        self.adapter.focus(force=True)
        if stop.is_set() or time.monotonic() >= deadline:
            raise InterruptedError("Preparation cancelled before its fixed warmup")
        try:
            subprocess.run(
                [
                    "xdotool",
                    "keydown",
                    "Shift_L",
                    "sleep",
                    "0.05",
                    "keydown",
                    "Return",
                    "sleep",
                    "0.1",
                    "keyup",
                    "Return",
                    "keyup",
                    "Shift_L",
                ],
                check=True,
                timeout=max(0.001, min(5, deadline - time.monotonic())),
            )
        finally:
            subprocess.run(["xdotool", "keyup", "Return", "Shift_L"], check=True, timeout=2)

    def projection(self, state):
        return {
            "schema_version": 2,
            "episode_id": self.initial["episode_id"],
            "evaluation": self.initial["evaluation"],
            "native_state": state,
        }

    def checkpoint(self):
        return {
            "process": self.process_identity(),
            "native_state": self.native.read(),
            "profile": self.profile.name,
        }

    def poll(self, elapsed):
        """Preserve one native checkpoint and return its terminal outcome, if any."""
        if self.process_identity() != self.identity:
            raise RuntimeError("Native Civilization VI process changed")
        state = self.native.read()
        started = json.loads((self.root / "trial.json").read_text()).get("started_at")
        if started is not None:
            elapsed = time.time() - started
        path = self.folder / "evidence" / f"science-{time.time_ns()}.json"
        write_json(path, self.projection(state))
        with (self.folder / "evidence.jsonl").open("a") as index:
            row = {
                "kind": "save",
                "path": str(path.relative_to(self.root)),
                "elapsed": elapsed,
                "sha256": sha256(path),
            }
            index.write(json.dumps(row) + "\n")
        return outcome(state)

    def recover(self, folder, checkpoint):
        """Reattach to the live game process when its native state still matches the checkpoint."""
        local = json.loads((self.root / "runtime.local.json").read_text())
        self.profile, self.snapshot, self.installation = (
            Path(local[name]) for name in ("profile", "snapshot", "installation")
        )
        self.folder, self.identity, self.binding = Path(folder), local["process"], local["binding"]
        self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
        self.native = NativeBaseGame()
        try:
            self.lock()
            self.adapter.release_all(recovery=True)
            expected = {key: value for key, value in checkpoint.items() if key != "frame"}
            return self.checkpoint() == expected
        except (OSError, ValueError, RuntimeError):
            return False

    def close(self, preserve=False):
        if self.native is not None:
            self.native.close()
            self.native = None
        if self.identity and not preserve:
            try:
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    if self.process_identity() != self.identity:
                        break
                    os.kill(self.identity["pid"], sig)
                    for _ in range(100):
                        if self.process_identity() != self.identity:
                            break
                        time.sleep(0.1)
            except (ProcessLookupError, RuntimeError):
                pass
            self.identity = self.process = None
        if not preserve:
            self.restore_profile()
        self.adapter.release_all()
