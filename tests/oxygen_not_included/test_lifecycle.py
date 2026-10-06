"""Native Colony Lost recognition and unsaved-loss receipts."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from gamecua.games.oxygen_not_included.loss import colony_lost
from gamecua.games.oxygen_not_included.progress import facts

from .test_integration import backend_fixture

FIXTURES = Path(__file__).parent / "fixtures/colony_lost"
CASES = json.loads((FIXTURES / "provenance.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["path"])
def test_loss_uses_native_zero_population_and_explicit_game_defeat(case):
    with Image.open(FIXTURES / case["path"]) as image:
        assert hashlib.sha256(image.tobytes()).hexdigest() == case["rgb_sha256"]
        assert colony_lost(image) is case["colony_lost"]


@pytest.mark.parametrize("removed", ["population", "banner"])
def test_partial_loss_cues_do_not_end_an_episode(removed):
    image = Image.open(FIXTURES / "00330-before.webp")
    box = (90, 0, 135, 50) if removed == "population" else (0, 110, 240, 150)
    image.paste((0, 0, 0), box)
    assert not colony_lost(image)
    assert not colony_lost(image.resize((1920, 1080)))


def test_unsaved_loss_is_preserved_once_and_grants_no_points(tmp_path):
    backend, source = backend_fixture(tmp_path)
    unchanged = source.read_bytes()
    backend.adapter = SimpleNamespace(
        capture=lambda **kwargs: Image.open(FIXTURES / "00327-before.webp")
    )
    assert backend.poll(42) == "death"
    assert backend.poll(43) == "death"
    rows = (backend.folder / "evidence.jsonl").read_text().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["kind"] == "history" and row["elapsed"] == 42
    raw = (backend.root / row["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert facts("history", raw, backend.initial) == (set(), "death")
    assert source.read_bytes() == unchanged
