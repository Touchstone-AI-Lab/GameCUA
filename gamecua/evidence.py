"""Scores only game-written evidence rows under the Trial's rubric; each assessment is a new score file."""

import importlib
import json
import shutil
import uuid
from pathlib import Path

from .specs import Rubric, TrialRecord, TrialSpec
from .storage import local_file, write_json

COMPLETED_REASONS = (
    "deadline",
    "verified_run_completion",
    "death_without_memory",
    "episode_limit",
)
PORTABLE = {
    "episodes",
    "scores",
    "trial.spec.json",
    "trial.json",
    "rubric.json",
    "model.json",
    "game.json",
    "inputs.json",
    "events.jsonl",
    "environment.json",
    "snapshot.provenance.json",
    "system_prompt.txt",
    "interview.json",
    "summary.json",
}


PAPER_BUDGET = {False: 10800.0, True: 3600.0}


def time_allowance(root, spec, record=None):
    """Return the base budget plus any recorded provider timeout credit."""
    if getattr(spec, "provider_failure_policy", None) != "freeze_retry_timeout_credit":
        return spec.total_seconds
    try:
        record = record or TrialRecord.model_validate_json((Path(root) / "trial.json").read_text())
    except (OSError, ValueError):
        return spec.total_seconds
    ledger = record.provider_recovery
    return spec.total_seconds + (ledger.timeout_credit_seconds if ledger else 0)


def effective_deadline(record):
    state = record if isinstance(record, dict) else record.model_dump(mode="json")
    ledger = state.get("provider_recovery") or {}
    shift = ledger.get("timeout_credit_seconds", 0) + ledger.get("operator_pause_seconds", 0)
    return None if state["deadline"] is None else state["deadline"] + shift


def milestone_episode(root, episode, rows, initial, rubric, predicates, allowance, awards):
    """Award each rubric milestone once, from the first row whose facts satisfy it."""
    achieved, outcome = set(), "unknown"
    for row in rows:
        if (
            row["kind"] not in ("save", "history")
            or row.get("baseline")
            or not 0 <= row["elapsed"] <= allowance
        ):
            continue
        found, terminal = predicates.facts(
            row["kind"], local_file(root, row["path"]).read_bytes(), initial
        )
        outcome = terminal or outcome
        for milestone in rubric.milestones:
            if milestone.predicate in found and set(milestone.prerequisites) <= achieved:
                achieved.add(milestone.id)
                awards.setdefault(
                    milestone.id,
                    {
                        "milestone_id": milestone.id,
                        "points": milestone.points,
                        "episode_id": episode["id"],
                        "first_verified_seconds": row["elapsed"],
                        "evidence": row["path"],
                    },
                )
    return {
        "episode_id": episode["id"],
        "outcome": outcome,
        "milestones": sorted(achieved),
        "termination_reason": episode.get("reason"),
    }


def score(root, episode_limit=None):
    root = Path(root).resolve()
    record = TrialRecord.model_validate_json((root / "trial.json").read_text())
    spec = TrialSpec.model_validate_json((root / "trial.spec.json").read_text())
    rubric = Rubric.model_validate_json((root / "rubric.json").read_text())
    predicates = importlib.import_module(f"gamecua.games.{spec.game_id.replace('-', '_')}.progress")
    allowance = time_allowance(root, spec, record)
    endpoint = rubric.assessment == "endpoint"
    awards, episodes, failures = {}, [], []
    complete = True
    counted = record.episodes[:episode_limit] if episode_limit else record.episodes
    truncated = len(counted) < len(record.episodes)
    for episode in counted:
        folder = root / "episodes" / episode["id"]
        setup_path = folder / "setup.json"
        setup = json.loads(setup_path.read_text()) if setup_path.exists() else {}
        if not setup.get("verified"):
            failures.append({"episode_id": episode["id"], "reason": "setup_unverified"})
            episodes.append({"episode_id": episode["id"], "outcome": "setup_failure"})
            continue
        index = folder / "evidence.jsonl"
        rows = (
            [json.loads(line) for line in index.read_text().splitlines()] if index.exists() else []
        )
        if not endpoint:
            episodes.append(
                milestone_episode(
                    root, episode, rows, setup["initial"], rubric, predicates, allowance, awards
                )
            )
            continue
        review = predicates.assess_endpoint(root, folder, rows, setup["initial"], spec, rubric)
        for award in review["awards"]:
            awards[(episode["id"], award["milestone_id"])] = {**award, "episode_id": episode["id"]}
        complete = complete and review["complete"]
        failures.extend(review.get("failures", []))
        episodes.append({"episode_id": episode["id"], **review["episode"]})
    typed = json.loads((root / "model.json").read_text())["provider"] == "typesafe"
    horizon = min(spec.total_seconds, PAPER_BUDGET[typed]) + allowance - spec.total_seconds
    awards = {k: a for k, a in awards.items() if a["first_verified_seconds"] <= horizon}
    manual_stop = typed and record.reason == "stop_file"
    if record.reason not in (*COMPLETED_REASONS, None) and not (manual_stop or truncated):
        failures.append({"reason": record.reason, "scope": "trial"})
    scoreable = record.started_at is not None and any("milestones" in e for e in episodes)
    if endpoint:
        complete = complete and len(counted) == 1
        scoreable = scoreable and complete
    completed = (
        truncated
        or manual_stop
        or (record.status == "completed" and record.reason in COMPLETED_REASONS)
    )
    points = sum(a["points"] for a in awards.values())
    result = {
        "trial_id": record.id,
        "trial_status": record.status,
        "trial_reason": record.reason,
        "score": points if complete else None,
        "scoreable": scoreable,
        "completion_status": "completed" if completed else "incomplete",
        "manual_stop": manual_stop,
        "comparison_eligible": scoreable
        and completed
        and (truncated or record.eligible)
        and not failures
        and not record.protocol_failures,
        "protocol_failures": record.protocol_failures,
        "awards": list(awards.values()),
        "episodes": episodes,
        "episode_limit": episode_limit,
        "scored_horizon_seconds": horizon,
        "failures": failures,
        "rubric_id": rubric.id,
        "rubric_version": rubric.version,
        "evaluator_version": predicates.VERSION,
        "elapsed_seconds": record.elapsed_seconds,
        "chargeable_seconds": record.chargeable_seconds,
        "infrastructure_downtime_seconds": record.infrastructure_downtime_seconds,
        "effective_seconds": record.effective_seconds,
        "evidence_gaps": record.evidence_gaps,
    }
    if record.provider_recovery is not None:
        result["provider_recovery"] = record.provider_recovery.model_dump(mode="json")
        result["time_allowance_seconds"] = allowance
    if endpoint:
        result["confirmed_subtotal"] = points
        result["assessment"] = "endpoint"
    interview = root / "interview.json"
    if interview.exists():
        result["interview"] = json.loads(interview.read_text()).get("answers")
    path = root / "scores" / f"{uuid.uuid4().hex}.json"
    path.parent.mkdir(exist_ok=True)
    write_json(path, result)
    return path, result


def export(root, target):
    root, target = Path(root).resolve(), Path(target)
    shutil.copytree(
        root,
        target,
        ignore=lambda folder, names: [
            n for n in names if n.endswith(".tmp") or (Path(folder) == root and n not in PORTABLE)
        ],
    )
    return target
