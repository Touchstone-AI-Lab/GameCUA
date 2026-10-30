"""Allow the native frame update to select the hovered target before pressing a button."""

import threading
import time

from ...actions import validate
from ...desktop import X11Desktop

HOVER_SECONDS = 0.2


class Desktop(X11Desktop):
    def _execute(self, action, *, stop=None, deadline=None):
        action = validate(action)
        if action["type"] == "drag" or (action["type"] == "pointer" and "button" in action):
            stop = stop or threading.Event()
            super()._execute(
                {"type": "pointer", "x": action["x"], "y": action["y"]},
                stop=stop,
                deadline=deadline,
            )
            remaining = (
                HOVER_SECONDS
                if deadline is None
                else min(HOVER_SECONDS, max(0, deadline - time.monotonic()))
            )
            if stop.wait(remaining) or (deadline is not None and time.monotonic() >= deadline):
                raise InterruptedError("Native pointer settling cancelled or deadline reached")
        return super()._execute(action, stop=stop, deadline=deadline)
