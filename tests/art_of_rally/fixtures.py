"""Synthetic native observer streams and stubs; never live game evidence."""

import copy
import hashlib
import json

from gamecua.games.art_of_rally.progress import State

SOURCES = {
    "physics": "OutOfBoundsManager.FixedUpdate",
    "recovery_begin": "OutOfBoundsManager.SetResettingInProgress",
    "recovery_end": "OutOfBoundsManager.SetResettingInProgress",
    "sample": "StageTimerManager.Update",
}


class Recorder:
    def __init__(self, *args):
        pass

    def close(self):
        pass


def point(x, y=0.77, z=0):
    return {"x": float(x), "y": float(y), "z": float(z)}


def encoded(rows):
    return b"".join((json.dumps(row) + "\n").encode() for row in rows)


class Stream:
    def __init__(self, forward=True, size=100, binding="synthetic-episode-001"):
        self.size, self.forward, self.binding = size, forward, binding
        self.rows = []
        self.start(0)
        self.initial = {"binding": binding, "baseline": copy.deepcopy(self.rows[0])}

    def location(self, index):
        return point(index * 2 * (1 if self.forward else -1))

    def start(self, stage):
        geometry = json.dumps(
            {
                "points": [self.location(i) for i in range(self.size + 2)],
                "start": 0,
                "last": self.size,
                "forward": self.forward,
            }
        )
        sequence = len(self.rows) + 1
        self.rows.append(
            {
                "binding": self.binding,
                "sequence": sequence,
                "source": "OutOfBoundsManager.FixedUpdate",
                "status": 2,
                "stage_index": stage,
                "stage": f"stage-{stage}",
                "scene": str(stage),
                "forward": self.forward,
                "current": 0,
                "start": 0,
                "last": self.size,
                "count": self.size + 2,
                "resetting": False,
                "finish_gate": False,
                "stage_time": "0",
                "penalties": "0",
                "terminal_damage": "False",
                "player_retired": False,
                "error": "",
                "position": self.location(0),
                "coverage": {
                    "event": "physics",
                    "geometry": geometry,
                    "geometry_hash": hashlib.sha256(geometry.encode()).hexdigest(),
                    "gate_player": False,
                    "gate_accepted": False,
                },
            }
        )

    def emit(self, event="physics", **changes):
        row = copy.deepcopy(self.rows[-1])
        row.update(
            sequence=len(self.rows) + 1,
            status=3,
            finish_gate=False,
            stage_time=str(len(self.rows)),
            source=SOURCES[event],
        )
        row["coverage"].update(event=event, gate_player=False, gate_accepted=False, geometry="")
        row.update(changes)
        self.rows.append(row)
        return row

    def drive(self, end):
        current = self.rows[-1]["current"]
        if self.rows[-1]["status"] == 2:
            self.emit(current=current, position=self.location(current))
        sign = 1 if end > current else -1
        for index in range(current + sign, end + sign, sign):
            self.emit(current=index, position=self.location(index))

    def recover(self, destination):
        self.emit("recovery_begin", resetting=True)
        self.emit(current=destination, position=self.location(destination), resetting=True)
        self.emit("recovery_end", resetting=False)
        self.emit(current=destination, position=self.location(destination))

    def finish(self, seconds=None):
        timer = {} if seconds is None else {"stage_time": str(seconds)}
        self.emit("sample", source="StageTimerManager.OnStageOver", status=5, **timer)
        row = self.emit(
            "sample", source="TimingGate.OnTriggerEnter", status=5, finish_gate=True, **timer
        )
        row["result_time_ms"] = int(float(row["stage_time"]) * 1000)
        row["coverage"].update(gate_player=True, gate_accepted=True)

    def loading(self, stage):
        row = self.emit("sample", source="StageTimerManager.Reset", status=0, stage_time="0")
        row.update(stage_index=stage, start=0, last=0, count=0, current=0)
        row["coverage"].update(event="route_loading", geometry="", geometry_hash="")

    def die(self, signal):
        if signal == "damage":
            return self.emit(terminal_damage="True")
        if signal == "retirement":
            return self.emit(player_retired=True)
        return self.emit(
            "sample",
            source="StageTimerManager.Reset"
            if signal == "reset"
            else "StageSceneManager.SetRestartStage",
            status=1,
            stage_time="0",
        )

    def rally(self):
        for stage in range(5):
            if stage:
                self.loading(stage)
                self.start(stage)
            self.drive(self.size)
            self.finish()

    def state(self):
        state = State()
        state.append(self.rows)
        return state
