"""Runs one CLI command under an exclusive lock; Steam environments first start or verify the cached client."""

import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from ..storage import write_json


def main():
    state = Path("/state")
    lock = (state / "execution.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    status = state / "execution.json"
    provenance = Path("/work/environment.json")
    if provenance.exists() and json.loads(provenance.read_text()).get("steam"):
        from ..games.steam.preparation import start_cached_client, verify_cached_session

        write_json(status, {"pid": os.getpid(), "running": True, "phase": "steam_startup"})
        try:
            if "resume-trial" in sys.argv[1:]:
                verify_cached_session()
            else:
                start_cached_client()
        except Exception:
            write_json(
                status,
                {
                    "running": False,
                    "exit": 1,
                    "reason": "steam_authorization_unverified",
                    "finished_at": time.time(),
                },
            )
            raise
    with (state / "execution.log").open("a") as log:
        process = subprocess.Popen(sys.argv[1:], stdout=log, stderr=log)
        write_json(status, {"pid": process.pid, "running": True, "started_at": time.time()})
        signal.signal(signal.SIGTERM, lambda *_: process.send_signal(signal.SIGTERM))
        signal.signal(signal.SIGINT, lambda *_: process.send_signal(signal.SIGINT))
        code = process.wait()
        write_json(
            status, {"pid": process.pid, "running": False, "exit": code, "finished_at": time.time()}
        )


if __name__ == "__main__":
    main()
