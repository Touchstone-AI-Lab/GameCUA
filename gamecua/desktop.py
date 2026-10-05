"""Captures only the titled game window and sends input through XTest, or XSendEvent under Wayland where XTest does not reach XWayland windows."""

import os
import time

from PIL import Image
from Xlib import XK, X, Xatom, display, protocol
from Xlib.ext import xtest

from .actions import KEYS, pixel, validate

EVENTS = {
    X.KeyPress: protocol.event.KeyPress,
    X.KeyRelease: protocol.event.KeyRelease,
    X.ButtonPress: protocol.event.ButtonPress,
    X.ButtonRelease: protocol.event.ButtonRelease,
}
MASKS = {
    X.KeyPress: X.KeyPressMask,
    X.KeyRelease: X.KeyReleaseMask,
    X.ButtonPress: X.ButtonPressMask,
    X.ButtonRelease: X.ButtonReleaseMask,
}
BUTTON_MASKS = {
    1: X.Button1Mask,
    2: X.Button2Mask,
    3: X.Button3Mask,
    4: X.Button4Mask,
    5: X.Button5Mask,
}


class X11Desktop:
    def __init__(
        self,
        title="Slay the Spire",
        size=(1280, 720),
        input_backend=None,
        mouse_mode="cursor",
        title_prefix=False,
    ):
        self.d = display.Display()
        self.root = self.d.screen().root
        self.title = title
        self.title_prefix = title_prefix
        self.size = size
        self.window = None
        if input_backend in (None, "auto"):
            input_backend = "xsend" if os.getenv("XDG_SESSION_TYPE") == "wayland" else "xtest"
        self.input_backend = input_backend
        self.mouse_mode = mouse_mode
        self.button_state = 0
        self.held_keys = set()
        self.held_buttons = set()

    def matches_title(self, name):
        return bool(name) and (
            name.startswith(self.title) if self.title_prefix else name == self.title
        )

    def window_title(self, window):
        for name in (self.d.intern_atom("_NET_WM_NAME"), Xatom.WM_NAME):
            value = window.get_full_text_property(name)
            if isinstance(value, bytes):
                value = value.decode("utf-8", "replace")
            if value:
                return value
        return None

    def find(self):
        if self.window is not None:
            try:
                if (
                    self.matches_title(self.window_title(self.window))
                    and self.window.get_attributes().map_state == X.IsViewable
                ):
                    return self.window
            except Exception:
                self.window = None
        matches = []

        def walk(w, depth=0):
            if depth > 5:
                return
            try:
                if (
                    self.matches_title(self.window_title(w))
                    and "mutter-x11-frames" not in (w.get_wm_class() or ())
                    and w.get_attributes().map_state == X.IsViewable
                ):
                    matches.append(w)
                for child in w.query_tree().children:
                    walk(child, depth + 1)
            except Exception:
                return

        walk(self.root)
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one visible game window titled {self.title!r}; found {len(matches)}"
            )
        self.window = matches[0]
        return self.window

    def focus(self, force=False):
        w = self.find()
        if not force and getattr(self.d.get_input_focus().focus, "id", None) == w.id:
            return w
        self.root.send_event(
            protocol.event.ClientMessage(
                window=w,
                client_type=self.d.intern_atom("_NET_ACTIVE_WINDOW"),
                data=(32, [2, X.CurrentTime, 0, 0, 0]),
            ),
            event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
        )
        self.d.sync()
        time.sleep(0.2)
        w.configure(stack_mode=X.Above)
        w.set_input_focus(X.RevertToParent, X.CurrentTime)
        self.d.sync()
        time.sleep(0.1)
        if self.d.get_input_focus().focus.id != w.id:
            raise RuntimeError("Game focus could not be acquired")
        return w

    def capture(self, focus=True):
        w = self.focus() if focus else self.find()
        g = w.get_geometry()
        raw = w.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xFFFFFFFF)
        image = Image.frombytes("RGB", (g.width, g.height), raw.data, "raw", "BGRX")
        self.geometry = {"width": g.width, "height": g.height, "window_id": w.id}
        return image.resize(self.size, Image.Resampling.LANCZOS)

    def _input(self, kind, detail, down):
        key = kind == "key"
        event_type = (
            (X.KeyPress if down else X.KeyRelease)
            if key
            else (X.ButtonPress if down else X.ButtonRelease)
        )
        if self.input_backend == "xtest":
            xtest.fake_input(self.d, event_type, detail)
        else:
            window = self.window or self.find()
            pointer = window.query_pointer()
            shift = self.d.keysym_to_keycode(XK.string_to_keysym("Shift_L")) in self.held_keys
            window.send_event(
                EVENTS[event_type](
                    time=X.CurrentTime,
                    root=self.root,
                    window=window,
                    child=X.NONE,
                    root_x=pointer.root_x,
                    root_y=pointer.root_y,
                    event_x=pointer.win_x,
                    event_y=pointer.win_y,
                    state=self.button_state | (X.ShiftMask if shift else 0),
                    detail=detail,
                    same_screen=1,
                ),
                event_mask=MASKS[event_type],
            )
        self.d.sync()
        held = self.held_keys if key else self.held_buttons
        held.add(detail) if down else held.discard(detail)
        if not key:
            mask = BUTTON_MASKS.get(detail, 0)
            self.button_state = self.button_state | mask if down else self.button_state & ~mask

    def release_all(self, recovery=False):
        keys = set(self.held_keys)
        buttons = set(self.held_buttons)
        if recovery:
            keys.update(self.d.keysym_to_keycode(XK.string_to_keysym(key)) for key in KEYS)
            buttons.update((1, 3, 4, 5))
        for kind, held in (("key", keys), ("button", buttons)):
            for detail in held:
                try:
                    self._input(kind, detail, False)
                except Exception:
                    if self.input_backend == "xtest":
                        xtest.fake_input(
                            self.d, X.KeyRelease if kind == "key" else X.ButtonRelease, detail
                        )
                        self.d.sync()
        if self.input_backend == "xtest" and buttons:
            for _ in range(5):
                active = self.root.query_pointer().mask
                remaining = [button for button in buttons if active & BUTTON_MASKS.get(button, 0)]
                if not remaining:
                    break
                for button in remaining:
                    xtest.fake_input(self.d, X.ButtonRelease, button)
                self.d.sync()
                time.sleep(0.02)
            else:
                raise RuntimeError("X server did not confirm mouse button release")
        self.held_keys.clear()
        self.held_buttons.clear()
        self.button_state = 0

    def execute(self, action, *, stop=None, deadline=None):
        try:
            return self._execute(action, stop=stop, deadline=deadline)
        finally:
            self.release_all()

    def _execute(self, action, *, stop=None, deadline=None):
        import threading

        a = validate(action)
        stop = stop or threading.Event()
        deadline = deadline if deadline is not None else float("inf")

        def guard():
            if stop.is_set() or time.monotonic() >= deadline:
                raise InterruptedError("Input cancelled or deadline reached")

        def wait(seconds):
            guard()
            stop.wait(min(seconds, max(0, deadline - time.monotonic())))
            guard()

        guard()
        if a["type"] == "wait":
            wait(a["seconds"])
            return
        window = self.focus(force=self.input_backend == "xsend")
        geometry = window.get_geometry()
        origin = self.root.translate_coords(window, 0, 0)

        def move(px, py):
            guard()
            if not 0 <= px < geometry.width or not 0 <= py < geometry.height:
                raise ValueError("Cursor movement must stay inside the game window")
            root_geometry = self.root.get_geometry()
            px = min(max(px, -origin.x), root_geometry.width - origin.x - 1)
            py = min(max(py, -origin.y), root_geometry.height - origin.y - 1)
            window.warp_pointer(round(px), round(py))
            self.d.sync()
            if self.mouse_mode != "captured":
                for _ in range(10):
                    actual = self.root.query_pointer()
                    if (
                        abs(actual.root_x - origin.x - px) <= 3
                        and abs(actual.root_y - origin.y - py) <= 3
                    ):
                        break
                    wait(0.05)
                else:
                    raise RuntimeError("Pointer did not reach game coordinates")
            if self.input_backend == "xsend":
                guard()
                pointer = window.query_pointer()
                window.send_event(
                    protocol.event.MotionNotify(
                        time=X.CurrentTime,
                        root=self.root,
                        window=window,
                        child=X.NONE,
                        root_x=pointer.root_x,
                        root_y=pointer.root_y,
                        event_x=pointer.win_x,
                        event_y=pointer.win_y,
                        state=self.button_state,
                        detail=0,
                        same_screen=1,
                    ),
                    event_mask=X.PointerMotionMask,
                )
                self.d.sync()

        def relative(dx, dy):
            guard()
            if self.mouse_mode == "captured":
                xtest.fake_input(self.d, X.MotionNotify, detail=1, x=round(dx), y=round(dy))
                self.d.sync()
            else:
                pointer = window.query_pointer()
                move(
                    min(max(pointer.win_x + dx, 0), geometry.width - 1),
                    min(max(pointer.win_y + dy, 0), geometry.height - 1),
                )

        def keys(items):
            for key in items:
                code = self.d.keysym_to_keycode(XK.string_to_keysym(key))
                if not code:
                    raise ValueError("Key unavailable on this keyboard")
                guard()
                self._input("key", code, True)

        kind = a["type"]
        if kind in ("pointer", "drag"):
            move(*pixel(a["x"], a["y"], geometry.width, geometry.height))
        if kind == "scroll":
            for _ in range(abs(a["steps"])):
                guard()
                detail = 4 if a["steps"] > 0 else 5
                self._input("button", detail, True)
                self._input("button", detail, False)
                wait(0.04)
        elif kind == "pointer" and "button" in a:
            guard()
            self._input("button", 3 if a["button"] == "right" else 1, True)
            wait(0.2)
        elif kind == "drag":
            guard()
            self._input("button", 1, True)
            for i in range(1, 21):
                fraction = i / 20
                move(
                    *pixel(
                        a["x"] + (a["to_x"] - a["x"]) * fraction,
                        a["y"] + (a["to_y"] - a["y"]) * fraction,
                        geometry.width,
                        geometry.height,
                    )
                )
                wait(a["duration"] / 20)
        elif kind == "control":
            keys(a["keys"])
            for button in a["buttons"]:
                guard()
                self._input("button", 1 if button == "left" else 3, True)
            steps = max(1, round(a["duration"] * 20)) if a["dx"] or a["dy"] else 0
            for i in range(steps):
                relative(
                    round(a["dx"] * (i + 1) / steps) - round(a["dx"] * i / steps),
                    round(a["dy"] * (i + 1) / steps) - round(a["dy"] * i / steps),
                )
                wait(a["duration"] / steps)
            if not steps:
                wait(a["duration"])

    def close(self):
        try:
            self.release_all()
        finally:
            self.d.close()
