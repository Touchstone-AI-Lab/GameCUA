"""Harbor's UV-script metric excludes missing rewards instead of imputing zeros."""

import argparse
import json
from pathlib import Path


def aggregate(rewards):
    valid = [row["reward"] for row in rewards if row is not None and "reward" in row]
    result = {"eligible_count": len(valid), "excluded_count": len(rewards) - len(valid)}
    if valid:
        result["eligible_mean"] = sum(valid) / len(valid)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", type=Path, required=True)
    parser.add_argument("-o", type=Path, required=True)
    args = parser.parse_args()
    args.o.write_text(
        json.dumps(aggregate([json.loads(x) for x in args.i.read_text().splitlines()]))
    )
