"""Owned native art of rally process, custom-rally preparation and native evidence collection."""

import json
import subprocess
import time
import uuid
from pathlib import Path

from PIL import Image

from ...desktop import X11Desktop
from ...evidence import effective_deadline
from .pause import NativeStep, Pause, StepAdapter
from .progress import Writer
from .setup import BINARY, launch_environment, restore, snapshot_files
from .ui import menu_match, title_match


def native_rows(path):
    if not path.exists():
        return []
    raw = path.read_bytes()
    return [json.loads(line) for line in raw[: raw.rfind(b"\n") + 1].splitlines()]


class Backend:
    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.desktop = self.adapter = X11Desktop(title="art of rally", input_backend="xtest")
        self.process = self.pause = self.writer = None
        self.native_step = self.executing_native_step = None

    def prepare(self, folder, stop, deadline):
        self.stop_process()
        spec = json.loads((self.root / "trial.spec.json").read_bytes())
        self.wait_stop = stop
        self.step_seconds = spec.get("step_seconds")
        self.frozen = spec["action_execution"] == "frozen_steps"
        self.native_step = self.executing_native_step = None
        self.adapter = self.desktop
        self.folder = Path(folder)
        self.profile = self.root.parent / ".profiles" / self.root.name / self.folder.name
        try:
            return self.launch(stop, deadline)
        except BaseException:
            self.close()
            raise

    def launch(self, stop, deadline):
        preparation = restore(self.snapshot, self.installation, self.profile)
        self.binding = uuid.uuid4().hex
        self.pause_directory = self.profile / "native-pause"
        self.pause_directory.mkdir()
        self.native = self.profile / "native.local.jsonl"
        game = self.profile / "game"
        env = launch_environment(self.profile)
        env.update(
            LP_NUM_THREADS=str(preparation["renderer_threads"]),
            DOORSTOP_ENABLED="1",
            DOORSTOP_TARGET_ASSEMBLY=str(game / "BepInEx/core/BepInEx.Preloader.dll"),
            LD_PRELOAD=str(game / "libdoorstop.so"),
            GAMECUA_RALLY_OBSERVER=str(self.native),
            GAMECUA_RALLY_BINDING=self.binding,
            GAMECUA_RALLY_PAUSE=str(self.pause_directory),
            GAMECUA_RALLY_CONTROL_POLICY=preparation.get("control_policy", ""),
            GAMECUA_RALLY_LOADING_EVENTS="1",
        )
        with (self.profile / "stdout.local.log").open("w") as log:
            self.process = subprocess.Popen(
                [
                    str(game / BINARY),
                    "-job-worker-count",
                    str(preparation["unity_job_workers"]),
                    "-screen-width",
                    str(preparation["native_resolution"][0]),
                    "-screen-height",
                    str(preparation["native_resolution"][1]),
                    "-screen-fullscreen",
                    "0",
                    "-logFile",
                    str(self.profile / "Player.local.log"),
                ],
                cwd=game,
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        end = min(deadline, time.monotonic() + 300)
        actions = []

        def press(key):
            action = {"type": "hold", "key": key, "duration": 0.15}
            self.desktop.execute(action, stop=stop, deadline=end)
            actions.append(action)
            stop.wait(1)

        files = snapshot_files(self.snapshot)
        title = Image.open(files["title-screen.png"]).convert("RGB")
        menu = Image.open(files["main-menu.png"]).convert("RGB")
        confirmed = False
        while not stop.is_set() and time.monotonic() < end:
            if self.process.poll() is not None:
                raise RuntimeError("Art of Rally exited during preparation")
            try:
                frame = self.desktop.capture()
            except RuntimeError:
                stop.wait(0.5)
                continue
            if menu_match(frame, menu)[0]:
                break
            if not confirmed and title_match(frame, title):
                press("Return")
                confirmed = True
            stop.wait(0.5)
        else:
            raise TimeoutError("Art of Rally main menu did not become ready")
        for key in ("Down", "Down", "Return", "Return"):
            press(key)
        started = skipped_intro = False
        baseline = None
        while not stop.is_set() and time.monotonic() < end:
            rows = native_rows(self.native)
            for row in rows:
                if row["status"] == 2 and row["stage_time"] == "0" and not row["error"]:
                    baseline = row
            latest = rows[-1] if rows else None
            if latest and latest["status"] == 0 and not skipped_intro:
                press("Return")
                skipped_intro = True
            if latest and latest["status"] == 1 and not started:
                press("Return")
                started = True
            if latest and latest["status"] == 3 and baseline:
                break
            stop.wait(0.05)
        else:
            raise TimeoutError("Art of Rally stage did not reach a clean countdown")
        self.initial = {
            "protocol": preparation["protocol"],
            "binding": self.binding,
            "baseline": baseline,
        }
        (self.folder / "evidence").mkdir()
        action = {"type": "pointer", "x": 0.5, "y": 0.5}
        self.desktop.execute(action, stop=stop, deadline=deadline)
        actions.append(action)
        self.offset = 0
        self.writer = Writer(self.root, self.folder, self.initial)
        if self.frozen:
            self.freeze()
            self.adapter = StepAdapter(self)
        self.desktop.capture().save(self.folder / "initial.png")
        return {
            "schema_version": 1,
            "verified": True,
            "initial": self.initial,
            "preparation_actions": actions,
            "control_policy": json.loads(
                (self.pause_directory / "control-policy.json").read_bytes()
            ),
        }

    def checkpoint(self):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError("Art of Rally is not running")
        return {"process": {"pid": self.process.pid}, "binding": self.binding}

    def poll(self, elapsed):
        self.checkpoint()
        with self.native.open("rb") as stream:
            stream.seek(self.offset)
            raw = stream.read()
        end = raw.rfind(b"\n") + 1
        self.offset += end
        sequence = self.initial["baseline"]["sequence"]
        rows = [json.loads(line) for line in raw[:end].splitlines()]
        self.writer.append([r for r in rows if r["sequence"] > sequence], elapsed)
        return self.writer.state.terminal

    def wait_checkpoint(self):
        if self.wait_stop.is_set():
            raise InterruptedError("Native transition wait cancelled")
        record = json.loads((self.root / "trial.json").read_bytes())
        if record["deadline"] is not None and time.time() >= effective_deadline(record):
            raise InterruptedError("Trial deadline reached during native transition")

    def freeze(self):
        self.desktop.release_all()
        if self.pause is None:
            self.pause = Pause(
                self.pause_directory,
                self.binding,
                {"pid": self.process.pid},
                self.wait_checkpoint,
            )
        self.pause.freeze()

    def thaw(self):
        if self.pause is None:
            return
        if not self.frozen or self.wait_stop.is_set():
            self.native_step = None
            return self.pause.thaw()
        if (self.pause.last_ack or {}).get("disposition") == "transition_process_frozen":
            self.native_step = self.executing_native_step = None
            return self.pause.thaw()
        self.native_step = NativeStep(self.pause, self.step_seconds)
        self.executing_native_step = None

    def recover(self, folder, checkpoint):
        return False

    def close(self, preserve=False):
        self.native_step = None
        self.frozen = False
        step, self.executing_native_step = self.executing_native_step, None
        try:
            self.desktop.release_all()
            if step is not None:
                step.abort()
        finally:
            try:
                self.desktop.close()
            finally:
                pause, self.pause = self.pause, None
                try:
                    if pause is not None:
                        pause.thaw()
                finally:
                    if not preserve:
                        self.stop_process()

    def stop_process(self):
        pause, self.pause = self.pause, None
        if pause is not None:
            pause.thaw()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
        self.desktop.window = None
