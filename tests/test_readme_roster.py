"""Every README roster row names a configured game and an existing guide."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_roster_rows_match_game_configurations():
    titles = {
        json.loads(path.read_text())["title"].lower()
        for path in (ROOT / "benchmarks/games").glob("*/game.json")
    }
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in (ROOT / "README.md").read_text().splitlines()
        if line.startswith("| ") and "(gamecua/games/" in line
    ]
    assert len(rows) == len(titles)
    for name, _, _, guide in rows:
        assert any(name.lower() in title for title in titles), name
        assert (ROOT / re.search(r"\((.+)\)", guide).group(1)).is_file(), guide
