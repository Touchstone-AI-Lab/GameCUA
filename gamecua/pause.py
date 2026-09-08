"""Freezes a game process with SIGSTOP through a pidfd, re-verifying its identity around every pause."""

import os
import signal
import time
from pathlib import Path


class ProcessPause:
    def __init__(self, identity, read_identity, name="Game"):
        self.name = name
        self.identity = dict(identity)
        self.read_identity = read_identity
        self.fd = None

    def verify(self):
        if self.read_identity() != self.identity:
            raise RuntimeError(f"{self.name} pause process identity changed")

    def stopped(self):
        tasks = list(Path(f"/proc/{self.identity['pid']}/task").glob("*/stat"))
        return bool(tasks) and all(
            path.read_text().rsplit(")", 1)[1].split()[0] == "T" for path in tasks
        )

    def freeze(self):
        self.verify()
        if self.fd is not None:
            if not self.stopped():
                raise RuntimeError(f"{self.name} was externally resumed")
            return
        if self.stopped():
            raise RuntimeError(f"{self.name} was externally stopped")
        self.fd = os.pidfd_open(self.identity["pid"])
        try:
            self.verify()
            signal.pidfd_send_signal(self.fd, signal.SIGSTOP)
            end = time.monotonic() + 1
            while time.monotonic() < end:
                self.verify()
                if self.stopped():
                    return
                time.sleep(0.005)
            raise RuntimeError(f"{self.name} did not confirm all threads stopped")
        except BaseException:
            self.release()
            raise

    def release(self):
        if self.fd is None:
            return
        fd, self.fd = self.fd, None
        try:
            signal.pidfd_send_signal(fd, signal.SIGCONT)
        except ProcessLookupError:
            pass
        finally:
            os.close(fd)

    def thaw(self):
        if self.fd is None:
            return
        try:
            self.verify()
        finally:
            self.release()


class PausableProcess:
    pause_name = "Game"
    pause_handle = None

    def freeze(self):
        if self.pause_handle is None:
            self.pause_handle = ProcessPause(self.identity, self.checkpoint, name=self.pause_name)
        self.pause_handle.freeze()

    def thaw(self):
        if self.pause_handle is not None:
            self.pause_handle.thaw()

    def release_pause(self):
        handle, self.pause_handle = self.pause_handle, None
        if handle is not None:
            handle.release()
