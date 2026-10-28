"""Allow one native hover update before a click or document drag."""

from ...actions import validate
from ...desktop import X11Desktop


class Desktop(X11Desktop):
    def __init__(self):
        super().__init__(title="PapersPlease", size=(1140, 640), input_backend="xtest")
        self.step_seconds = None

    def _execute(self, action, *, stop=None, deadline=None):
        action = validate(action)
        if action["type"] == "drag" and self.step_seconds is not None:
            action = {
                **action,
                "duration": min(action["duration"], max(0.1, self.step_seconds - 0.2)),
            }
        if action["type"] == "drag" or "button" in action:
            super()._execute(
                {"type": "pointer", "x": action["x"], "y": action["y"]},
                stop=stop,
                deadline=deadline,
            )
            super()._execute({"type": "wait", "seconds": 0.2}, stop=stop, deadline=deadline)
        if action["type"] == "pointer" and "button" in action:
            action = {"type": "control", "buttons": [action["button"]], "duration": 0.3}
        return super()._execute(action, stop=stop, deadline=deadline)
