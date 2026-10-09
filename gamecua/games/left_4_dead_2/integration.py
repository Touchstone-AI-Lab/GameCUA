"""Isolated licensed campaign episodes with read-only native event evidence."""

import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

from ...actions import validate as validate_action
from ...desktop import X11Desktop
from ...pause import PausableProcess, ProcessPause
from ...storage import write_json
from ..steam.preparation import CLIENT, installed_app
from .progress import facts
from .vpk import resource

INSTALLATION_FILES = (
    "hl2.sh",
    "hl2_linux",
    "left4dead2/gameinfo.txt",
    "update/pak01_dir.vpk",
    "left4dead2/cfg/video_bench_low.txt",
)


def identity(pid):
    """Return the pid and kernel start time of a process."""
    stat = Path(f"/proc/{pid}/stat").read_text()
    return {"pid": pid, "start_ticks": stat.rsplit(")", 1)[1].split()[19]}


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


class Desktop(X11Desktop):
    def execute(self, action, *, stop=None, deadline=None):
        """Stretch key taps to 0.2 s so the engine sees them."""
        action = validate_action(action)
        if action["type"] == "control" and action["duration"] < 0.2:
            action = {**action, "duration": 0.2}
        return super().execute(action, stop=stop, deadline=deadline)


class Backend(PausableProcess):
    pause_name = "Left 4 Dead 2"
    SETTLE_SECONDS = 15

    def __init__(self, root, snapshot=None, installation=None):
        self.root = Path(root).resolve()
        self.snapshot = Path(snapshot).resolve() if snapshot else None
        self.installation = Path(installation).resolve() if installation else None
        self.adapter = Desktop(
            title="Left 4 Dead 2",
            size=(640, 360),
            title_prefix=True,
            input_backend="xtest",
            mouse_mode="captured",
        )
        self.process = self.identity = None

    def checkpoint(self):
        return identity(self.process.pid if self.process else self.identity["pid"])

    def engine(self):
        """Find the hl2_linux engine process launched by the hl2.sh wrapper."""
        for stat in Path("/proc").glob("[0-9]*/stat"):
            try:
                raw = stat.read_text()
                fields = raw.rsplit(")", 1)[1].split()
                if (
                    raw.split("(", 1)[1].rsplit(")", 1)[0] == "hl2_linux"
                    and int(fields[1]) == self.identity["pid"]
                ):
                    return {"pid": int(stat.parent.name), "start_ticks": fields[19]}
            except (OSError, ValueError, IndexError):
                continue
        raise RuntimeError("Left 4 Dead 2 engine process not found")

    def freeze(self):
        if self.pause_handle is None:
            engine = self.engine()
            self.pause_handle = ProcessPause(
                engine, lambda: identity(engine["pid"]), name=self.pause_name
            )
        self.pause_handle.freeze()

    def group_alive(self, group):
        for stat in Path("/proc").glob("[0-9]*/stat"):
            try:
                if int(stat.read_text().rsplit(")", 1)[1].split()[2]) == group:
                    return True
            except (OSError, ValueError, IndexError):
                continue
        return False

    def stop_process(self):
        self.release_pause()
        if not self.identity:
            return
        group = self.identity["pid"]
        signal_group(self.identity, signal.SIGTERM)
        end = time.monotonic() + 15
        while self.group_alive(group) and time.monotonic() < end:
            if self.process:
                self.process.poll()
            time.sleep(0.2)
        signal_group(self.identity, signal.SIGKILL)
        if self.process:
            self.process.wait(timeout=5)
        time.sleep(self.SETTLE_SECONDS)
        self.identity = None

    def read_rows(self):
        """Read the observer's new complete records in generation and sequence order."""
        generation_file = self.native_evidence / ("gs-" + self.nonce + "-generation.txt")
        if not generation_file.exists():
            return []
        raw_generation = generation_file.read_bytes().rstrip(b"\0")
        if not raw_generation:
            return []
        latest_generation = int(raw_generation)
        generation, sequence = self.last_native
        if generation == 0:
            generation, sequence = 1, -1
        rows = []
        while generation <= latest_generation:
            path = self.native_evidence / f"gs-{self.nonce}-{generation}-{sequence + 1}.json"
            if not path.exists():
                if generation < latest_generation:
                    generation, sequence = generation + 1, -1
                    continue
                break
            raw = path.read_bytes().rstrip(b"\0")
            if not raw.endswith(b"\n"):
                break
            rows.append(json.loads(raw))
            sequence += 1
            self.last_native = (generation, sequence)
        return rows

    @staticmethod
    def console_ready(image):
        """Detect the grey developer console panel shown at startup."""
        points = ((350, 25), (600, 25), (280, 100), (620, 100))
        return all(
            85 <= min(image.getpixel(point)) <= max(image.getpixel(point)) <= 165
            and max(image.getpixel(point)) - min(image.getpixel(point)) < 12
            for point in points
        )

    def start_campaign(self, stop, deadline):
        end = min(deadline, time.monotonic() + 120)
        while time.monotonic() < end and not stop.is_set():
            if self.process.poll() is not None:
                raise RuntimeError("Game exited before local campaign startup")
            self.dismiss_locale_warning()
            try:
                image = self.adapter.capture(focus=False)
                if self.console_ready(image):
                    image.save(self.folder / "preparation-console.png")
                    window = str(self.adapter.geometry["window_id"])
                    subprocess.run(["xdotool", "windowfocus", window], check=True, timeout=5)
                    stop.wait(1)
                    subprocess.run(
                        ["xdotool", "type", "--clearmodifiers", "--delay", "80", "exec gs_prepare"],
                        check=True,
                        timeout=10,
                    )
                    subprocess.run(
                        ["xdotool", "keydown", "Return", "sleep", "0.3", "keyup", "Return"],
                        check=True,
                        timeout=5,
                    )
                    return
            except RuntimeError:
                if self.process.poll() is not None:
                    raise
            stop.wait(1)
        raise InterruptedError("Verified startup console was unavailable")

    def dismiss_locale_warning(self):
        result = subprocess.run(
            ["xwininfo", "-root", "-tree"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if '"Warning"' not in line:
                continue
            window = line.split()[0]
            subprocess.run(
                [
                    "xdotool",
                    "windowactivate",
                    "--sync",
                    window,
                    "windowfocus",
                    window,
                    "keydown",
                    "Return",
                    "sleep",
                    "0.2",
                    "keyup",
                    "Return",
                ],
                check=True,
                timeout=5,
            )

    def build_profile(self, source, stop, deadline):
        """Clone the licensed installation and install the observer and preparation config."""

        def clone(source_file, target_file):
            if stop.is_set() or time.monotonic() >= deadline:
                raise InterruptedError("Native profile preparation cancelled")
            path = Path(source_file)
            if (
                path.suffix.lower() in (".cfg", ".vdf", ".txt", ".log", ".nut", ".nuc")
                or "config" in path.parts
            ):
                return shutil.copy2(source_file, target_file)
            try:
                os.link(source_file, target_file)
                return target_file
            except OSError:
                return shutil.copy2(source_file, target_file)

        shutil.copytree(
            source,
            self.profile,
            copy_function=clone,
            ignore=shutil.ignore_patterns("console.log", "*.dmp", "core.*"),
        )
        scripts = self.profile / "update/scripts/vscripts"
        scripts.mkdir(parents=True, exist_ok=True)
        native = resource(source / "update/pak01_dir.vpk", "scripts/vscripts/mapspawn.nuc")
        (scripts / "gs_native_mapspawn.nuc").write_bytes(native)
        (scripts / "mapspawn.nut").write_text(
            'IncludeScript("gs_native_mapspawn", this);\nIncludeScript("gamecua_observer", this);\n'
        )
        observer = Path(__file__).with_name("observer.nut")
        (scripts / "gamecua_observer.nut").write_text(
            'GSNonce <- "' + self.nonce + '";\n' + observer.read_text()
        )
        (self.profile / "update/cfg").mkdir(parents=True, exist_ok=True)
        preparation = (self.snapshot / "baseline.cfg").read_text()
        preparation += 'cl_showfps 0\nunbind F8\nunbind "\x60"\ncon_enable 0\nmap c1m1_hotel coop\n'
        for cfg in ("update/cfg", "left4dead2/cfg"):
            (self.profile / cfg / "gs_prepare.cfg").write_text(preparation)
            for name in ("video.txt", "videodefaults.txt"):
                shutil.copy2(self.snapshot / name, self.profile / cfg / name)
        compatibility = self.profile / "compat"
        compatibility.mkdir()
        (compatibility / "libpng12.so.0").symlink_to(
            CLIENT / "ubuntu12_32/steam-runtime/lib/i386-linux-gnu/libpng12.so.0"
        )
        return compatibility

    def prepare(self, folder, stop, deadline):
        self.stop_process()
        app = installed_app(550)
        if not app:
            raise RuntimeError("Licensed Steam installation is unavailable")
        self.folder = Path(folder)
        self.nonce = uuid.uuid4().hex
        self.profile = (
            Path.home()
            / ".local/share/GameCUA/left-4-dead-2"
            / (self.root.name + "-" + self.folder.name + "-" + self.nonce)
        )
        compatibility = self.build_profile(Path(app["directory"]), stop, deadline)
        self.native_evidence = self.profile / "left4dead2/ems"
        self.last_native = (0, -1)
        env = dict(
            os.environ,
            SteamAppId="550",
            SteamGameId="550",
            LANG="C",
            LC_ALL="C",
            SDL_AUDIODRIVER="dummy",
            LD_LIBRARY_PATH=str(compatibility),
            LP_NUM_THREADS="8",
            VK_DRIVER_FILES="/usr/share/vulkan/icd.d/lvp_icd.json",
            DXVK_NUM_COMPILER_THREADS="4",
        )
        with (self.profile / "launch.local.log").open("w") as log:
            self.process = subprocess.Popen(
                [
                    str(self.profile / "hl2.sh"),
                    "-game",
                    "left4dead2",
                    "-steam",
                    "-vulkan",
                    "-novid",
                    "-windowed",
                    "-w",
                    "640",
                    "-h",
                    "360",
                    "-nojoy",
                    "-condebug",
                    "-console",
                    "+con_enable",
                    "1",
                    "+fps_max",
                    "30",
                ],
                cwd=self.profile,
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        self.identity = self.checkpoint()
        self.start_campaign(stop, deadline)
        end = min(deadline, time.monotonic() + 600)
        ready_at = latest = None
        while time.monotonic() < end and not stop.is_set():
            if self.process.poll() is not None:
                raise RuntimeError("Game exited during preparation")
            self.dismiss_locale_warning()
            for row in self.read_rows():
                if row.get("human_alive") and row.get("bots") == 3:
                    latest = row
                    ready_at = ready_at or time.monotonic()
            if ready_at and time.monotonic() - ready_at >= 15 and latest["time"] >= 40:
                self.adapter.capture().save(self.folder / "initial.png")
                break
            stop.wait(1)
        else:
            raise InterruptedError("Campaign preparation timed out")
        self.initial = latest
        (self.folder / "evidence").mkdir()
        write_json(self.folder / "evidence/initial.json", self.initial)
        write_json(
            self.root / "runtime.local.json",
            {
                "profile": str(self.profile),
                "snapshot": str(self.snapshot),
                "process": self.identity,
            },
        )
        return {
            "verified": True,
            "initial": self.initial,
            "steam_build_id": app["build_id"],
            "death_policy": "Human death or mission failure ends the episode; fresh campaign restarts are charged.",
        }

    def poll(self, elapsed):
        if self.process is not None and self.process.poll() is not None:
            raise RuntimeError("Left 4 Dead 2 exited")
        rows = self.read_rows()
        if not rows:
            return None
        _, terminal = facts("history", json.dumps(rows).encode(), self.initial)
        path = self.folder / "evidence" / f"{time.time_ns()}.json"
        write_json(path, rows)
        with (self.folder / "evidence.jsonl").open("a") as file:
            row = {"kind": "history", "path": str(path.relative_to(self.root)), "elapsed": elapsed}
            file.write(json.dumps(row) + "\n")
        return terminal

    def recover(self, folder, checkpoint):
        return False

    def close(self, preserve=False):
        try:
            self.adapter.close()
        finally:
            if not preserve:
                self.stop_process()
