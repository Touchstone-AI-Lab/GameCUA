"""Records only the game window to an MP4 with per-frame elapsed timestamps and recording gaps."""

import json
import shutil
import subprocess
import threading
import time

from .desktop import X11Desktop
from .storage import write_json


class Recording:
    def __init__(self, directory, game, fps, elapsed, stop, capture_factory=None):
        self.directory, self.game, self.fps, self.elapsed, self.stop = (
            directory,
            game,
            fps,
            elapsed,
            stop,
        )
        self.capture_factory = capture_factory
        self.done = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.result = {"fps": fps, "frames": 0, "gaps": [], "window_only": True}
        self.thread.start()

    def desktop(self):
        if self.capture_factory is not None:
            return self.capture_factory()
        return X11Desktop(
            self.game.window_title,
            self.game.resolution,
            self.game.input_backend,
            title_prefix=self.game.window_title_prefix,
        )

    def encoder(self, stderr):
        executable = shutil.which("ffmpeg")
        if not executable:
            import imageio_ffmpeg

            executable = imageio_ffmpeg.get_ffmpeg_exe()
        width, height = self.game.resolution
        return subprocess.Popen(
            [
                executable,
                *("-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24"),
                *("-s", f"{width}x{height}", "-r", str(self.fps), "-i", "pipe:0", "-an"),
                *("-c:v", "libx264", "-preset", "ultrafast", "-crf", "26"),
                *("-movflags", "frag_keyframe+empty_moov", str(self.directory / "window.mp4")),
            ],
            stdin=subprocess.PIPE,
            stderr=stderr,
        )

    def run(self):
        desktop = process = None
        try:
            desktop = self.desktop()
            with (self.directory / "recording.stderr.txt").open("w") as stderr:
                process = self.encoder(stderr)
                previous = None
                while not self.done.is_set() and not self.stop.is_set():
                    started = time.monotonic()
                    stamp = self.elapsed()
                    if previous is not None and stamp - previous > 1.8 / self.fps:
                        self.result["gaps"].append({"from": previous, "to": stamp})
                    process.stdin.write(desktop.capture(focus=False).tobytes())
                    with (self.directory / "frames.jsonl").open("a") as index:
                        index.write(
                            json.dumps({"frame": self.result["frames"], "elapsed": stamp}) + "\n"
                        )
                    self.result["frames"] += 1
                    previous = stamp
                    self.done.wait(max(0, 1 / self.fps - (time.monotonic() - started)))
        except Exception as exc:
            self.result["error_type"] = type(exc).__name__
            self.result["gaps"].append({"from": self.elapsed(), "reason": "recording_failed"})
        finally:
            if process:
                self.stop_encoder(process)
            if desktop:
                desktop.close()
            write_json(self.directory / "recording.json", self.result)

    def stop_encoder(self, process):
        """Close the encoder input and wait for it, killing it if it does not exit."""
        try:
            process.stdin.close()
        except OSError:
            pass
        try:
            self.result["encoder_exit"] = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            self.result["encoder_exit"] = process.wait()
            self.result["gaps"].append({"from": self.elapsed(), "reason": "encoder_killed"})

    def close(self):
        self.done.set()
        self.thread.join()
