"""Canonical evidence assessment and eligible-only numerical Harbor rewards."""

import json
from pathlib import Path

from ..evidence import export, score
from ..storage import write_json


def assess(root, output, portable=None):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    reward = output / "reward.txt"
    reward.unlink(missing_ok=True)
    try:
        _, assessment = score(root)
    except (OSError, ValueError, KeyError) as exc:
        result = {"comparison_eligible": False, "scoreable": False, "failure": type(exc).__name__}
        write_json(output / "assessment.json", result)
        return result
    write_json(output / "assessment.json", assessment)
    if portable and not Path(portable).exists():
        export(root, portable)
    if assessment["comparison_eligible"]:
        rubric = json.loads((root / "rubric.json").read_text())
        maximum = sum(x["points"] for x in rubric["milestones"])
        reward.write_text(str(assessment["score"] / maximum) + "\n")
    return assessment


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=Path("/work/trial"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    parser.add_argument("--portable", type=Path, default=Path("/logs/artifacts/evidence"))
    args = parser.parse_args()
    result = assess(args.run_dir, args.output, args.portable)
    raise SystemExit(0 if result.get("comparison_eligible") else 1)
