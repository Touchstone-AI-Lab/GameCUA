"""Bounded X11 presentation settling after released input; not a native simulation clock."""

import select
import time

from Xlib import display
from Xlib.ext import damage

FULL_UPDATES = 6
TIMEOUT_SECONDS = 30.0


def settle(window_id, stop, deadline):
    """Wait for six distinct full-window X11 damage updates after input."""
    started = time.monotonic()
    end = min(deadline, started + TIMEOUT_SECONDS)
    stamps = set()
    connection = display.Display()
    try:
        if not connection.has_extension("DAMAGE"):
            raise RuntimeError("ONI frozen input requires the X11 DAMAGE extension")
        connection.damage_query_version()
        window = connection.create_resource_object("window", window_id)
        geometry = window.get_geometry()
        identifier = window.damage_create(damage.DamageReportNonEmpty)
        connection.sync()
        while connection.pending_events():
            connection.next_event()
        connection.damage_subtract(identifier)
        connection.sync()
        while len(stamps) < FULL_UPDATES:
            now = time.monotonic()
            if stop.is_set() or now >= deadline:
                raise InterruptedError("ONI render settling cancelled or deadline reached")
            if now >= end:
                raise RuntimeError("ONI did not present enough full-window updates after input")
            if not connection.pending_events():
                select.select([connection.fileno()], [], [], min(0.05, end - now))
            while len(stamps) < FULL_UPDATES and connection.pending_events():
                if stop.is_set() or time.monotonic() >= deadline:
                    raise InterruptedError("ONI render settling cancelled or deadline reached")
                if time.monotonic() >= end:
                    raise RuntimeError("ONI did not present enough full-window updates after input")
                event = connection.next_event()
                if getattr(event, "damage", None) != identifier:
                    continue
                area = event.area
                if (
                    area.x == 0
                    and area.y == 0
                    and area.width == geometry.width
                    and area.height == geometry.height
                ):
                    stamps.add(event.timestamp)
                connection.damage_subtract(identifier)
                connection.sync()
        if stop.is_set() or time.monotonic() >= deadline:
            raise InterruptedError("ONI render settling cancelled or deadline reached")
        return {
            "method": "x11_damage_full_window_updates",
            "full_updates": len(stamps),
            "host_seconds": time.monotonic() - started,
        }
    finally:
        connection.close()
