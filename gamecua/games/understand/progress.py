"""Route panel awards and native ending detection from preserved Understand saves."""

import json
import subprocess
from collections import defaultdict

from ...evidence import time_allowance
from ...storage import local_file
from .native import GROUP_PANELS, NativePanels

VERSION = "understand-native-panels-4"
SPINE = ("1-1", "1-2", "1-3", "1-4", "2-1", "2-2", "EX-10", "END")
POINTS = {
    f"panel-{group}-{panel}": (group, panel)
    for group, count in GROUP_PANELS.items()
    for panel in range(1, count + 1)
}
PREDICATES = set(POINTS)


def slot(raw, initial):
    return json.loads(raw)[initial["active_slot"]] or [[], None, None, {}]


def facts(kind, raw, initial):
    if kind != "save":
        return set(), None
    return set(), "victory" if set(SPINE) <= set(slot(raw, initial)[0]) else None


def load_history(root, rows, initial, spec):
    allowance = time_allowance(root, spec)
    snapshots = []
    for row in rows:
        if row["kind"] != "save" or row.get("baseline") or not 0 <= row["elapsed"] <= allowance:
            continue
        data = slot(local_file(root, row["path"]).read_bytes(), initial)
        snapshots.append((row, set(data[0]), data[3] if isinstance(data[3], dict) else {}))
    return snapshots


def evaluate_history(snapshots, checker_factory=None):
    proofs = {group: {} for group in GROUP_PANELS}
    queue = defaultdict(list)
    for index, (row, cleared, lines) in enumerate(snapshots):
        for group, count in GROUP_PANELS.items():
            if group in cleared:
                for panel in range(1, count + 1):
                    proofs[group].setdefault(panel, {"row": row, "method": "native-group-reveal"})
            elif any(lines.get(group) or ()):
                queue[group].append({"id": str(index), "lines": {group: lines[group]}})
    failures, runtime = [], {}
    try:
        if queue:
            checker = (checker_factory or NativePanels)()
            for group, states in queue.items():
                for result in checker.evaluate(group, states):
                    row = snapshots[int(result["id"])][0]
                    for panel, passed in enumerate(result["passed"], 1):
                        old = proofs[group].get(panel)
                        if passed and (old is None or row["elapsed"] < old["row"]["elapsed"]):
                            proofs[group][panel] = {"row": row, "method": "native-submitted-path"}
            runtime = checker.metadata
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        failures.append({"reason": "native_panel_assessment_unavailable", "detail": str(exc)[:600]})
    awards = [
        {
            "milestone_id": milestone,
            "points": 1,
            "first_verified_seconds": proof["row"]["elapsed"],
            "evidence": proof["row"]["path"],
            "evidence_sha256": proof["row"]["sha256"],
            "proof_method": proof["method"],
        }
        for milestone, (group, panel) in POINTS.items()
        if (proof := proofs[group].get(panel))
    ]
    final_clear, cleared = set(), set()
    for _, current, _ in snapshots:
        if new_groups := current - cleared:
            final_clear = new_groups
        cleared = current
    victory = set(SPINE) <= cleared
    return {
        "complete": not failures,
        "awards": awards,
        "failures": failures,
        "episode": {
            "outcome": "victory" if victory else "unknown",
            "milestones": [award["milestone_id"] for award in awards],
            "points_at_2h": sum(award["first_verified_seconds"] <= 7200 for award in awards),
            "group_completion_counts": {g: len(p) for g, p in proofs.items()},
            "highest_confirmed_completed_chapter": max(
                (int(group.split("-")[0]) for group in cleared if group[0].isdigit()), default=0
            ),
            "most_recent_confirmed_completed_groups": sorted(final_clear),
            "ending_verified": victory,
            "native_runtime": runtime,
            "measurement": "One point per unique native panel proved within the first episode's time allowance.",
        },
    }


def assess_endpoint(root, folder, rows, initial, spec, rubric):
    snapshots = load_history(root, rows, initial, spec)
    if not snapshots:
        return {
            "complete": False,
            "awards": [],
            "failures": [{"reason": "missing_native_history"}],
            "episode": {"outcome": "unknown", "milestones": []},
        }
    return evaluate_history(snapshots)
