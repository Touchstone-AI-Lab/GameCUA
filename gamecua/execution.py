"""One run per X display, and what a new segment inherits: recovery continues its own episode; after a death only the previous episode's notes and context carry over."""

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

MEMORY_LIMIT = 1800
NEW_ATTEMPT = "A new attempt has started. Your previous immediate scene, position, resources and pending intentions are no longer current. Retain only your own learned observations and hypotheses as unverified experience; inspect the current screenshot before acting."


@contextmanager
def desktop_lease(enabled=True):
    if not enabled:
        yield
        return
    identity = hashlib.sha256(f"{os.getuid()}:{os.getenv('DISPLAY', 'default')}".encode())
    path = Path(tempfile.gettempdir()) / f"gamecua-desktop-{identity.hexdigest()[:16]}.lock"
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another GameCUA run owns this desktop") from None
        yield


def last_segment(root, episode):
    return root / "episodes" / episode["id"] / "segments" / episode["segments"][-1]["id"]


def inherited_context(root, episode, episodes, policy):
    recovering = bool(episode["segments"])
    previous = episodes[-2] if len(episodes) > 1 else None
    if recovering:
        source = last_segment(root, episode)
    elif (
        policy == "trial_memory"
        and previous
        and previous["reason"] == "death"
        and previous["segments"]
    ):
        source = last_segment(root, previous)
    else:
        return {
            "memory": "",
            "history": [],
            "attempt_notice": "",
            "session_source": None,
            "policy": policy,
            "provenance": {"kind": "fresh_trial", "source": None},
        }
    records = [json.loads(p.read_text()) for p in sorted(source.glob("[0-9]*.json"))]
    completed = [r for r in records if r.get("execution_status") == "completed"]
    notes = [
        r
        for r in records
        if r.get("execution_status") == "completed"
        or (
            not recovering
            and r.get("execution_status") == "rejected"
            and r.get("reason") == "native_terminal"
            and r.get("native_terminal") == "death"
        )
    ]
    initial_path = source / "initial_agent_context.json"
    initial = json.loads(initial_path.read_text()) if initial_path.exists() else {}
    memory = notes[-1]["decision"]["memory"] if notes else initial.get("memory", "")
    history = [
        {"segment": source.name, "step": r["step"], "action": r["decision"]["action"]}
        for r in completed[-8:]
    ] or initial.get("history", [])
    session = source / "context" / "latest.json"
    return {
        "memory": memory[:MEMORY_LIMIT],
        "history": history[-8:] if recovering else [],
        "attempt_notice": initial.get("attempt_notice", "") if recovering else NEW_ATTEMPT,
        "session_source": str(session.relative_to(root)) if session.exists() else None,
        "policy": policy,
        "provenance": {
            "kind": "recovery" if recovering else "death_inheritance",
            "source": str(source.relative_to(root)),
        },
    }
