"""Offline tests for Stardew Valley snapshot capture and screen-state checks on synthetic data."""

import json

from PIL import Image

from gamecua.games.stardew_valley.integration import ENERGY_BAR, in_game, load_menu
from gamecua.games.stardew_valley.setup import capture_snapshot, save_slot
from gamecua.storage import sha256
from tests.stardew_valley.test_stardew_progress import synthetic_save


def profile(tmp_path, slots=("Farm_123456789",)):
    source = tmp_path / "StardewValley"
    for name in slots:
        slot = source / "Saves" / name
        slot.mkdir(parents=True)
        (slot / name).write_bytes(synthetic_save(day=2))
        (slot / "SaveGameInfo").write_text("<Farmer/>")
        (slot / f"{name}_old").write_bytes(synthetic_save(day=1))
    (source / "startup_preferences").write_text("<StartupPreferences/>")
    return source


def test_capture_snapshot_copies_the_save_slot(tmp_path):
    target = capture_snapshot(profile(tmp_path), tmp_path / "snapshot")
    manifest = json.loads((target / "snapshot.manifest.json").read_text())
    assert set(manifest) == {
        "Saves/Farm_123456789/Farm_123456789",
        "Saves/Farm_123456789/SaveGameInfo",
        "startup_preferences",
    }
    assert all(sha256(target / name) == checksum for name, checksum in manifest.items())
    assert save_slot(target)[1].name == "Farm_123456789"
    assert save_slot(target)[1].read_bytes() == synthetic_save(day=2)


def frame(color, bar=None):
    image = Image.new("RGB", (1280, 720), color)
    if bar:
        image.paste(Image.new("RGB", (ENERGY_BAR[2] - ENERGY_BAR[0], 160), bar), ENERGY_BAR[:2])
    return image


def test_screen_state_checks():
    assert in_game(frame((240, 180, 110), bar=(0, 255, 0)))
    assert not in_game(frame((80, 160, 230)))
    assert load_menu(frame((255, 210, 132)))
    assert not load_menu(frame((80, 160, 230)))


def test_recover_reattaches_to_the_running_game_without_repeating_evidence(tmp_path):
    import subprocess
    import sys

    from gamecua.games.stardew_valley.integration import Backend
    from gamecua.games.stardew_valley.saves import read_save

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
    )

    class Adapter:
        def release_all(self, recovery=False):
            self.released = recovery

    try:
        root = tmp_path / "trial"
        folder = root / "episodes/episode-001"
        (folder / "evidence").mkdir(parents=True)
        initial = read_save(synthetic_save(day=2))
        (folder / "setup.json").write_text(json.dumps({"verified": True, "initial": initial}))
        source = profile(tmp_path / ".profiles/trial/episode-001/home/.config")
        first = Backend.__new__(Backend)
        first.root, first.folder = root, folder.resolve()
        first.profile = (tmp_path / ".profiles/trial/episode-001").resolve()
        first.process, first.initial = process, initial
        first.seen = sha256(save_slot(source)[1])
        first.identity = first.process_identity()
        checkpoint = first.checkpoint()
        save_slot(source)[1].write_bytes(synthetic_save(day=3, hoed=1))
        assert first.poll(1.0) is None

        resumed = Backend.__new__(Backend)
        resumed.root, resumed.adapter = root, Adapter()
        assert resumed.recover(folder, {**checkpoint, "frame": "unused.png"})
        assert resumed.adapter.released is True
        assert resumed.poll(2.0) is None
        assert len((folder / "evidence.jsonl").read_text().splitlines()) == 1
        save_slot(source)[1].write_bytes(synthetic_save(day=4, hoed=1, sown=1))
        assert resumed.poll(3.0) is None
        assert len((folder / "evidence.jsonl").read_text().splitlines()) == 2
        stale = {**checkpoint, "process": {**checkpoint["process"], "start_ticks": "0"}}
        assert not resumed.recover(folder, stale)
        assert resumed.recover(folder, checkpoint)
        resumed.stop_process()
        process.wait(timeout=5)
        assert not resumed.recover(folder, checkpoint)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
