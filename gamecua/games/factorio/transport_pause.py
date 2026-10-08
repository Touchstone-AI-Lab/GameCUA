"""Private pause channel that freezes Factorio while a provider relay recovers from HTTP 413."""

import json
import os
import secrets
import socketserver
import threading
import time
import uuid
from pathlib import Path

from ...pause import ProcessPause


class PauseHandler(socketserver.StreamRequestHandler):
    """Serve one authenticated freeze or recover request."""

    def handle(self):
        try:
            value = json.loads(self.rfile.readline())
            owner = self.server.owner
            if not secrets.compare_digest(value.get("secret", ""), owner.secret):
                raise PermissionError("Invalid pause capability")
            reply = {"ok": True, **owner.request(value["operation"], value["request_sha256"])}
        except Exception as exc:
            reply = {"ok": False, "error_type": type(exc).__name__}
        self.wfile.write(json.dumps(reply).encode() + b"\n")


class PauseServer(socketserver.ThreadingUnixStreamServer):
    """Unix socket server with daemon request threads."""

    daemon_threads = True


class TransportPause:
    """Own at most one transport pause of the backend's game process."""

    def __init__(self, backend, directory=Path("/state")):
        self.backend = backend
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.registry = self.directory / "factorio-http413-channel.json"
        self.socket = self.directory / ("p" + uuid.uuid4().hex[:8] + ".sock")
        self.audit = self.directory / "factorio-http413-pause.local.jsonl"
        self.secret = secrets.token_hex(32)
        self.lock = threading.RLock()
        self.active = self.handle = self.since = None
        self.server = PauseServer(str(self.socket), PauseHandler)
        self.server.owner = self
        self.socket.chmod(0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.registry.unlink(missing_ok=True)
        fd = os.open(self.registry, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            json.dump({"socket": str(self.socket), "secret": self.secret}, file)

    def log(self, kind, **fields):
        """Append one pause interval event to the private audit log."""
        with self.audit.open("a") as file:
            file.write(json.dumps({"time": time.time(), "kind": kind, **fields}) + "\n")

    def request(self, operation, request_sha256):
        """Freeze the game for a failing request, or resume it once that request recovered."""
        with self.lock:
            if operation == "recover":
                if self.active is None:
                    return {"state": "no_pause"}
                owned = self.handle is not None
                self.reset("transport_recovered")
                return {"state": "resumed" if owned else "left_frozen"}
            if not self.backend.process_id:
                return {"state": "no_game"}
            if self.active is not None:
                return {"state": "paused" if self.handle else "already_frozen"}
            probe = ProcessPause(
                self.backend.process_id, self.backend.process_identity, name="Factorio transport"
            )
            already = probe.stopped()
            if not already:
                probe.freeze()
            self.active, self.since = request_sha256, time.monotonic()
            self.handle = None if already else probe
            self.log(
                "transport_pause_started", request_sha256=request_sha256, pause_owned=not already
            )
            return {"state": "already_frozen" if already else "paused"}

    def reset(self, reason):
        """Resume the game if this channel froze it, and record the pause interval."""
        with self.lock:
            if self.active is None:
                return
            handle, self.handle = self.handle, None
            if handle is not None:
                handle.thaw()
            self.log(
                "transport_pause_ended",
                request_sha256=self.active,
                pause_owned=handle is not None,
                seconds=time.monotonic() - self.since,
                reason=reason,
            )
            self.active = self.since = None

    def close(self):
        """Release any owned pause and remove the channel."""
        self.reset("backend_close")
        self.server.shutdown()
        self.server.server_close()
        self.socket.unlink(missing_ok=True)
        self.registry.unlink(missing_ok=True)
