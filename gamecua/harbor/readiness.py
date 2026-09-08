"""Operator launch check; readiness.json is not Trial evidence and is never scored."""

import importlib
import threading
import time
from pathlib import Path

import numpy as np

from ..specs import GameSpec
from ..storage import write_json


def check(game, root, installation, snapshot):
    game = GameSpec.model_validate_json(Path(game).read_text())
    root = Path(root)
    folder = root / "launch"
    folder.mkdir(parents=True, exist_ok=False)
    support = importlib.import_module(f"gamecua.games.{game.id.replace('-', '_')}.integration")
    backend = support.Backend(root, snapshot, installation)
    stop, deadline = threading.Event(), time.monotonic() + 180
    try:
        setup = backend.prepare(folder, stop, deadline)
        frame = backend.adapter.capture()
        screenshot_deadline = min(deadline, time.monotonic() + 15)
        while float(np.asarray(frame).std()) <= 5 and time.monotonic() < screenshot_deadline:
            time.sleep(0.25)
            frame = backend.adapter.capture()
        if not setup["verified"] or frame.size != tuple(game.resolution):
            raise ValueError("Initial game state or screenshot dimensions unverified")
        if float(np.asarray(frame).std()) <= 5:
            raise ValueError("Game screenshot is black or uniform")
        backend.adapter.execute(
            {"type": "hold", "key": "Shift_L", "duration": 0.1}, stop=stop, deadline=deadline
        )
        backend.adapter.release_all()
        result = {
            "game_id": game.id,
            "verified": True,
            "screenshot_size": list(frame.size),
            "pixel_std": float(np.asarray(frame).std()),
            "input": "Native setup interaction plus ordinary Shift hold and release",
            "kind": "operator_readiness",
            "steam": "Fresh official client authentication required before this check"
            if game.id == "slay-the-spire"
            else "not required",
        }
        write_json(root / "readiness.json", result)
        return result
    finally:
        backend.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(args.game, args.output, "/installation", "/snapshot")
