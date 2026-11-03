"""Process pause with a longer stop confirmation for PEAK's Wine renderer."""

import os
import signal
import time

from ...pause import ProcessPause

STOP_CONFIRMATION_SECONDS = 10.0


class NativePause(ProcessPause):
    """Suspend PEAK and wait up to ten seconds for every native thread to stop."""

    def stopped(self):
        """Treat a thread that exits during the snapshot as not yet confirmed."""
        try:
            return super().stopped()
        except FileNotFoundError:
            return False

    def freeze(self):
        """Send SIGSTOP once and wait for confirmation."""
        if self.fd is not None:
            if not self.stopped():
                raise RuntimeError("PEAK was externally resumed")
            return
        self.fd = os.pidfd_open(self.identity["pid"])
        try:
            self.verify()
            signal.pidfd_send_signal(self.fd, signal.SIGSTOP)
            end = time.monotonic() + STOP_CONFIRMATION_SECONDS
            while time.monotonic() < end:
                if self.stopped():
                    return
                time.sleep(0.005)
            raise RuntimeError("PEAK did not confirm all threads stopped")
        except BaseException:
            self.release()
            raise
