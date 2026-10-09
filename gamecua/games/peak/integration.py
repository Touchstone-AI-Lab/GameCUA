"""Official Proton episodes, isolated profiles and evaluator-only native evidence."""

import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import numpy as np
from Xlib import X

from ...pause import PausableProcess
from ...storage import write_json
from .desktop import Desktop
from .pause import NativePause
from .progress import facts, playable
from .setup import native_environment, stage_game

TITLE_RENDER_SETTLE_SECONDS = 5.0
TITLE_UNRENDERED_SECONDS = 15.0
PREPARATION_LAUNCHES = 3


class Backend(PausableProcess):
    """Launch, observe, pause and stop one PEAK process per episode."""

    pause_name = "PEAK"

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = Desktop(title="PEAK", input_backend="xtest", mouse_mode="captured")
        self.process = self.process_id = self.profile = self.folder = self.initial = None
        self.offset = 0
        self.run_start = self.binding = self.proton = None

    def freeze(self):
        """Suspend every native thread of the PEAK process."""
        if self.pause_handle is None:
            self.pause_handle = NativePause(
                self.process_id, self.process_identity, name=self.pause_name
            )
        self.pause_handle.freeze()

    def process_identity(self):
        """Return the pid and kernel start time of the native PEAK process."""
        stat = Path(f"/proc/{self.process_id['pid']}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": self.process_id["pid"], "start_ticks": stat[19]}

    def rows(self):
        """Return every complete sample the observer has written."""
        path = self.profile / "native.jsonl"
        if not path.exists():
            return []
        raw = path.read_bytes()
        return [json.loads(line) for line in raw[: raw.rfind(b"\n") + 1].splitlines()]

    def checkpoint(self):
        """Identify the running process and observer binding for recovery."""
        return {"process": self.process_identity(), "binding": self.binding}

    def persist_runtime(self):
        """Store what recovery needs to reattach to the running episode."""
        write_json(
            self.root / "runtime.local.json",
            {
                "snapshot": str(self.snapshot),
                "installation": str(self.installation),
                "profile": str(self.profile),
                "process": self.process_id,
                "binding": self.binding,
                "proton": str(self.proton),
                "offset": self.offset,
                "run_start": self.run_start,
            },
        )

    def stop_process(self):
        """Terminate PEAK and the Wine server of its prefix."""
        self.release_pause()
        if self.process_id:
            try:
                os.kill(self.process_id["pid"], signal.SIGTERM)
            except OSError:
                pass
        if self.proton and self.profile:
            subprocess.run(
                [str(self.proton.parent / "files/bin/wineserver"), "-k"],
                env=dict(
                    os.environ,
                    WINEPREFIX=str(self.profile / "compat/pfx"),
                    LD_LIBRARY_PATH="/usr/lib/wsl/lib",
                ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        if self.process:
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        self.process_id = None
        self.adapter.window = None

    def launch(self, number):
        """Start PEAK in a fresh copy of the snapshot prefix with a new observer binding."""
        from ..steam.preparation import CLIENT

        name = self.folder.name if number == 1 else f"{self.folder.name}-prepare-{number:02d}"
        root = Path(os.environ.get("GAMECUA_PEAK_PROFILE_ROOT", "/state/peak-profiles"))
        self.profile = root / self.root.name / name
        self.profile.mkdir(parents=True, exist_ok=False)
        shutil.copytree(self.snapshot / "compat", self.profile / "compat", symlinks=True)
        game = stage_game(self.installation, self.profile / "game")
        self.binding = uuid.uuid4().hex
        self.offset, self.run_start = 0, None
        options = [
            *(
                ["-disable-gpu-skinning"]
                if os.environ.get("GAMECUA_PEAK_CPU_SKINNING") == "1"
                else []
            ),
            *(
                ["-force-gfx-direct"]
                if os.environ.get("GAMECUA_PEAK_DIRECT_RENDERING") == "1"
                else []
            ),
        ]
        with (self.profile / "stdout.private.log").open("w") as log:
            self.process = subprocess.Popen(
                [
                    str(self.proton),
                    "run",
                    str(game / "PEAK.exe"),
                    "-force-d3d11",
                    *options,
                    "-screen-fullscreen",
                    "0",
                    "-screen-width",
                    "1280",
                    "-screen-height",
                    "720",
                ],
                env=native_environment(self.profile, CLIENT, self.binding),
                cwd=game,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        return options

    def prepare(self, folder, stop, deadline):
        """Launch PEAK until its title screen renders, relaunching a black title at most twice."""
        from ..steam.preparation import CLIENT

        self.stop_process()
        end = min(deadline, time.monotonic() + 180)
        if not self.snapshot or not self.installation:
            local = json.loads((self.root / "runtime.local.json").read_text())
            self.snapshot, self.installation = (
                Path(local[name]) for name in ("snapshot", "installation")
            )
        self.proton = CLIENT / "steamapps/common/Proton - Experimental/proton"
        self.folder = Path(folder)
        launches, verified_rows = [], []
        for number in range(1, PREPARATION_LAUNCHES + 1):
            if stop.is_set() or time.monotonic() >= end:
                break
            started = time.monotonic()
            options = self.launch(number)
            reason, title_ready_at = "preparation_timeout_or_cancelled", None
            while not stop.is_set() and time.monotonic() < end:
                if self.process.poll() is not None:
                    raise RuntimeError("Official Proton exited; inspect the private launch logs")
                rows = self.rows()
                latest = rows[-1] if rows else None
                ready = (
                    latest is not None
                    and latest["scene"] == "Title"
                    and not latest["character_present"]
                    and not latest["run_started"]
                    and not latest.get("error")
                )
                if not ready:
                    title_ready_at = None
                elif title_ready_at is None:
                    title_ready_at = time.monotonic()
                if ready and time.monotonic() - title_ready_at >= TITLE_RENDER_SETTLE_SECONDS:
                    window = self.adapter.find()
                    pid = window.get_full_property(
                        self.adapter.d.intern_atom("_NET_WM_PID"), X.AnyPropertyType
                    )
                    self.process_id = {"pid": int(pid.value[0])}
                    self.process_id = self.process_identity()
                    frame = self.adapter.capture(focus=False)
                    if stop.is_set() or time.monotonic() >= end:
                        break
                    if frame.size == (1280, 720) and np.asarray(frame).std() > 15:
                        verified_rows, reason = rows, "verified_title"
                        break
                    if time.monotonic() - title_ready_at >= TITLE_UNRENDERED_SECONDS:
                        reason = "title_unrendered"
                        break
                stop.wait(min(0.5, max(0, end - time.monotonic())))
            launches.append(
                {"launch": number, "reason": reason, "seconds": time.monotonic() - started}
            )
            if verified_rows or reason != "title_unrendered":
                break
            self.stop_process()
        if not verified_rows:
            raise InterruptedError("PEAK native title preparation timed out or was cancelled")
        (self.folder / "evidence").mkdir()
        baseline = self.folder / "evidence/initial.json"
        write_json(baseline, {"schema_version": 1, "binding": self.binding, "rows": verified_rows})
        self.initial = {
            "binding": self.binding,
            "baseline_sequence": verified_rows[-1]["sequence"],
            "initial_scene": "Title",
            "game_version": verified_rows[-1]["game_version"],
        }
        self.offset = len(verified_rows)
        frame.save(self.folder / "initial.png")
        self.persist_runtime()
        return {
            "verified": True,
            "initial": self.initial,
            "initial_evidence": str(baseline.relative_to(self.root)),
            "preparation_launches": launches,
            "launch_options": options,
            "experiment_kind": "fresh_title_screen",
            "native_evaluator_only": True,
        }

    def poll(self, elapsed):
        """Preserve new native samples with the run-start anchor and return any terminal state."""
        all_rows = self.rows()
        rows = all_rows[self.offset :]
        if not rows:
            return None
        for row in rows:
            if (
                self.run_start is None
                and row["run_started"]
                and playable(row)
                and not row["dead"]
                and not row["passed_out"]
            ):
                self.run_start = row
        path = self.folder / "evidence" / f"{time.time_ns()}.json"
        write_json(
            path,
            {
                "schema_version": 1,
                "binding": self.binding,
                "run_start": self.run_start,
                "rows": rows,
            },
        )
        with (self.folder / "evidence.jsonl").open("a") as index:
            index.write(
                json.dumps(
                    {"kind": "save", "path": str(path.relative_to(self.root)), "elapsed": elapsed}
                )
                + "\n"
            )
            index.flush()
            os.fsync(index.fileno())
        self.offset = len(all_rows)
        self.persist_runtime()
        return facts("save", path.read_bytes(), self.initial)[1]

    def recover(self, folder, checkpoint):
        """Reattach to the episode process after a harness restart."""
        local = json.loads((self.root / "runtime.local.json").read_text())
        self.profile, self.snapshot, self.installation, self.proton = (
            Path(local[name]) for name in ("profile", "snapshot", "installation", "proton")
        )
        self.folder = Path(folder)
        self.initial = json.loads((self.folder / "setup.json").read_text())["initial"]
        self.process_id, self.binding = local["process"], local["binding"]
        self.offset, self.run_start = local["offset"], local["run_start"]
        self.adapter.release_all(recovery=True)
        try:
            self.adapter.find()
            current = self.checkpoint()
            return (current["process"], current["binding"]) == (
                checkpoint["process"],
                checkpoint.get("binding"),
            )
        except (OSError, ValueError, RuntimeError):
            return False

    def close(self, preserve=False):
        """Release input and pauses, and stop the game unless it is preserved."""
        self.release_pause()
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
