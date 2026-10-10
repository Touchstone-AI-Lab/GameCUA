"""Native route-checkpoint evidence, its live chunk writer and the V9 endpoint scorer."""

import json
import os
from pathlib import Path

from ...evidence import time_allowance
from .route import SELECTION, Coverage, selection

VERSION = "art-of-rally-stage-evidence-9"
EVALUATOR = "art-of-rally-checkpoints-1"
FORMAT = "art-of-rally-native-chunk-1"
PREDICATES = {f"s{stage}-route-{point:02d}" for stage in range(1, 6) for point in range(1, 20)} | {
    f"s{stage}-finish" for stage in range(1, 6)
}
RESTARTS = {"StageTimerManager.Reset", "StageSceneManager.SetRestartStage"}
TIMER_CAP = 3599


class Attempt:
    def __init__(self, row):
        self.anchor = row
        self.route = Coverage(row)
        self.recovering = self.finished = self.result_seen = False
        self.finish = None

    def advance(self, row):
        capture = row["coverage"]
        event = capture["event"]
        if event in ("recovery_begin", "recovery_end"):
            self.recovering = event == "recovery_begin"
            self.route.suspend()
        elif event == "recovery_cancel":
            self.route.suspend()
        if event == "physics" and row["status"] == 3 and not self.recovering and not self.finished:
            self.route.advance(row)
        elif event == "physics" and row["status"] in (2, 4) and not self.recovering:
            self.route.pause(row)
        elif row["status"] not in (2, 3, 4):
            self.route.suspend()
        if row["source"] == "StageTimerManager.OnStageOver":
            self.result_seen = row["status"] == 5 and 0 < float(row["stage_time"]) <= TIMER_CAP
        if (
            row["finish_gate"]
            and not self.finished
            and row["source"] == "TimingGate.OnTriggerEnter"
            and self.result_seen
            and not self.recovering
            and capture.get("gate_player") is True
            and capture.get("gate_accepted") is True
            and row.get("player_retired") is False
            and type(row.get("result_time_ms")) is int
            and 0 < row["result_time_ms"] <= TIMER_CAP * 1000
        ):
            self.finished = True
            self.finish = row


class State:
    def __init__(self):
        self.attempts, self.current = [], None
        self.index = self.count = 0
        self.terminal = None

    def append(self, rows):
        for row in rows:
            if self.terminal:
                break
            restart = (
                row["source"] in RESTARTS
                and row["coverage"]["event"] != "route_loading"
                and row["stage_index"] == self.index
            )
            if self.count and (
                row["terminal_damage"] == "True" or row["player_retired"] or restart
            ):
                self.current = None
                self.terminal = "death"
            else:
                self.step(row)
                if len({a.anchor["stage_index"] for a in self.attempts if a.finished}) == 5:
                    self.terminal = "victory"
            self.count += 1

    def step(self, row):
        if row["stage_index"] != self.index:
            self.index, self.current = row["stage_index"], None
        restart = row["source"] in RESTARTS
        if self.current is not None:
            self.current.advance(row)
            if restart:
                self.current = None
        if (
            self.current is None
            and not restart
            and row["status"] == 2
            and float(row["stage_time"]) == 0
        ):
            self.current = Attempt(row)
            self.attempts.append(self.current)


class Writer:
    def __init__(self, root, folder, initial):
        self.root, self.folder = Path(root), Path(folder)
        self.binding = initial["binding"]
        self.state = State()
        self.state.append([initial["baseline"]])
        self.number = 0

    def append(self, rows, elapsed):
        if not rows:
            return
        self.state.append(rows)
        self.number += 1
        path = self.folder / "evidence" / f"chunk-{self.number:08d}.native.json"
        chunk = {
            "schema_version": 3,
            "format": FORMAT,
            "binding": self.binding,
            "ordinal": self.number,
            "first_sequence": rows[0]["sequence"],
            "last_sequence": rows[-1]["sequence"],
            "samples": rows,
        }
        path.write_text(json.dumps(chunk, separators=(",", ":"), ensure_ascii=False))
        entry = {
            "kind": "native_chunk",
            "path": str(path.relative_to(self.root)),
            "elapsed": elapsed,
            "ordinal": self.number,
        }
        with (self.folder / "evidence.jsonl").open("a") as index:
            index.write(json.dumps(entry, separators=(",", ":")) + "\n")
            index.flush()
            os.fsync(index.fileno())


def assess_endpoint(root, folder, rows, initial, spec, rubric):
    allowance = time_allowance(root, spec)
    state = State()
    state.append([initial["baseline"]])
    number, verified_elapsed, endpoint = 0, None, None
    awards, routes = {}, {}
    for entry in rows:
        if entry.get("kind") != "native_chunk":
            continue
        elapsed = entry["elapsed"]
        if elapsed > allowance:
            break
        chunk = json.loads((Path(root) / entry["path"]).read_bytes())
        state.append(chunk["samples"])
        for attempt in state.attempts:
            stage = attempt.anchor["stage_index"] + 1
            checkpoints = selection(attempt.anchor)
            route_hash = attempt.anchor["coverage"]["geometry_hash"]
            routes[stage] = {
                "stage": stage,
                "scene": attempt.anchor["scene"],
                "forward": attempt.anchor["forward"],
                "geometry_hash": route_hash,
                "segments": list(checkpoints),
                "selection": SELECTION,
            }
            found = {
                f"s{stage}-route-{point:02d}": {
                    "segment": segment,
                    "native_sequences": attempt.route.covered[segment],
                    "target_fraction": point / 20,
                }
                for point, segment in enumerate(checkpoints, 1)
                if segment in attempt.route.covered
            }
            if attempt.finished:
                found[f"s{stage}-finish"] = {
                    "native_sequences": [attempt.finish["sequence"]],
                    "result_ms": attempt.finish["result_time_ms"],
                }
            for key, details in found.items():
                awards.setdefault(
                    key,
                    {
                        "milestone_id": key,
                        "points": 1,
                        "first_verified_seconds": elapsed,
                        "evidence": entry["path"],
                        "geometry_hash": route_hash,
                        "stage": stage,
                        **details,
                    },
                )
        verified_elapsed, endpoint = elapsed, entry["path"]
        number += 1
        if state.terminal:
            break
    complete = number > 0
    return {
        "complete": complete,
        "awards": list(awards.values()),
        "failures": [] if complete else [{"reason": "missing_native_checkpoint_chunks"}],
        "episode": {
            "outcome": state.terminal or "unknown",
            "milestones": sorted(awards),
            "endpoint_evidence": endpoint,
            "checkpoint_evaluator": EVALUATOR,
            "routes": [routes[stage] for stage in sorted(routes)],
            "native_chunks_replayed": number,
            "native_records_replayed": state.count,
            "last_verified_poll_seconds": verified_elapsed,
        },
    }
