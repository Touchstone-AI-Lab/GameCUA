"""Frame-guarded loading, Proton profile isolation and preserved native checkpoints."""

import json
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from gamecua.games.civilization_vi import integration
from gamecua.games.civilization_vi.runtime import proton_paths
from gamecua.storage import write_json


def frames(tmp_path):
    dialog = Image.new("RGB", (1280, 720), (130, 180, 150))
    ImageDraw.Draw(dialog).rectangle((10, 10, 30, 25), fill=(10, 10, 10))
    menu = Image.new("RGB", (1280, 720), (25, 50, 85))
    ImageDraw.Draw(menu).rectangle((60, 60, 90, 90), fill="white")
    (tmp_path / "reference").mkdir()
    dialog.save(tmp_path / "reference/dialog.png")
    menu.save(tmp_path / "reference/menu.png")
    return dialog, menu


def backend(tmp_path, capture, actions=None):
    actions = [] if actions is None else actions
    result = object.__new__(integration.Backend)
    result.snapshot = result.profile = tmp_path
    result.identity = {"pid": 1}
    result.process_identity = lambda: {"pid": 1}
    result.adapter = SimpleNamespace(
        capture=capture, execute=lambda action, **kwargs: actions.append(action)
    )
    return result


def test_native_menu_row_shift_moves_the_click_only_after_matching_text():
    reference = Image.new("RGB", (1280, 720), (25, 50, 85))
    ImageDraw.Draw(reference).rectangle((20, 165, 60, 170), fill="white")
    shifted = Image.new("RGB", reference.size, (25, 50, 85))
    ImageDraw.Draw(shifted).rectangle((20, 191, 60, 196), fill="white")
    step = {
        "region": [0, 156, 100, 174],
        "vertical_offsets": [0, 26],
        "actions": [{"type": "click", "x": 0.5, "y": 165 / 719, "button": "left"}],
    }
    matched = integration.matching_step(reference, shifted, step)
    assert matched["actions"][0]["y"] == pytest.approx(191 / 719)
    assert step["actions"][0]["y"] == 165 / 719
    assert integration.matching_step(reference, Image.new("RGB", reference.size), step) is None


@pytest.mark.parametrize("offset", [-16, 0, 16])
def test_map_label_guard_accepts_bounded_horizontal_shift(offset):
    reference = Image.new("RGB", (1280, 720), (25, 50, 85))
    ImageDraw.Draw(reference).rectangle((100, 100, 140, 120), fill=(240, 200, 30))
    shifted = Image.new("RGB", reference.size, (25, 50, 85))
    ImageDraw.Draw(shifted).rectangle((100 + offset, 100, 140 + offset, 120), fill=(240, 200, 30))
    step = {
        "region": [80, 90, 160, 130],
        "metric": "rgb",
        "horizontal_offsets": list(range(-16, 17)),
    }
    assert integration.frame_matches(reference, shifted, step)
    assert not integration.frame_matches(reference, shifted, {**step, "horizontal_offsets": [99]})


@pytest.mark.parametrize("row_offset", (0, 26))
def test_absent_optional_dialog_skips_only_on_the_following_frame(tmp_path, row_offset):
    dialog, menu = frames(tmp_path)
    step = {"frame": "dialog.png", "region": [0, 0, 100, 100], "ink": "dark"}
    following = {"frame": "menu.png", "region": [0, 0, 100, 100], "vertical_offsets": [0, 26]}
    actual = Image.new("RGB", menu.size, (25, 50, 85))
    ImageDraw.Draw(actual).rectangle((60, 60 + row_offset, 90, 90 + row_offset), fill="white")
    stop = threading.Event()
    assert (
        backend(tmp_path, lambda: actual).wait_frame(step, stop, time.monotonic() + 1, following)
        is None
    )
    with pytest.raises(InterruptedError):
        backend(tmp_path, lambda: Image.new("RGB", (1280, 720))).wait_frame(
            step, stop, time.monotonic() + 0.1, following
        )
    assert backend(tmp_path, lambda: dialog).wait_frame(step, stop, time.monotonic() + 1, following)


def test_reappearing_service_dialog_is_declined_before_loading_continues(tmp_path):
    dialog, menu = frames(tmp_path)
    images = iter([dialog] * 3 + [menu])
    actions = []
    result = backend(tmp_path, lambda: next(images), actions)
    decline = {"type": "click", "x": 520 / 1279, "y": 662 / 719, "button": "left"}
    service = {
        "frame": "dialog.png",
        "region": [0, 0, 100, 100],
        "ink": "dark",
        "actions": [decline],
    }
    step = {"frame": "menu.png", "region": [0, 0, 100, 100]}
    stop = SimpleNamespace(is_set=lambda: False, wait=lambda duration: None)
    assert result.wait_frame(step, stop, time.monotonic() + 2, service=service)
    assert [action for action in actions if action["type"] == "click"] == [decline] * 3


def test_initial_map_must_remain_visible_for_its_settle_time(tmp_path):
    reference = Image.new("RGB", (1280, 720), (25, 50, 85))
    ImageDraw.Draw(reference).rectangle((20, 20, 60, 60), fill="white")
    (tmp_path / "reference").mkdir()
    reference.save(tmp_path / "reference/map.png")
    images = iter([reference, Image.new("RGB", reference.size)] * 10)
    with pytest.raises(InterruptedError):
        backend(tmp_path, lambda: next(images)).wait_frame(
            {"frame": "map.png", "region": [0, 0, 100, 100], "metric": "rgb"},
            threading.Event(),
            time.monotonic() + 0.3,
            settle=1,
        )


def test_fixed_native_warmup_releases_keys_after_a_timeout(monkeypatch):
    result = object.__new__(integration.Backend)
    result.adapter = SimpleNamespace(focus=lambda **kwargs: None)
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(integration.subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired):
        result.warmup(threading.Event(), time.monotonic() + 1)
    assert calls[0][0][:3] == ["xdotool", "keydown", "Shift_L"]
    assert 0 < calls[0][1]["timeout"] <= 1
    assert calls[1][0] == ["xdotool", "keyup", "Return", "Shift_L"]


def test_preparation_cancelled_while_focusing_sends_no_warmup_input(monkeypatch):
    stop = threading.Event()
    result = object.__new__(integration.Backend)
    result.adapter = SimpleNamespace(focus=lambda **kwargs: stop.set())
    monkeypatch.setattr(integration.subprocess, "run", lambda *args, **kwargs: pytest.fail())
    with pytest.raises(InterruptedError):
        result.warmup(stop, time.monotonic() + 1)


def isolated(tmp_path, monkeypatch):
    client = tmp_path / "steam"
    monkeypatch.setattr(integration.steam, "CLIENT", client)
    monkeypatch.setattr(
        integration, "X11Desktop", lambda **kwargs: SimpleNamespace(release_all=lambda **_: None)
    )
    paths = proton_paths(client)
    for target in (paths["profile"], paths["saves"]):
        target.mkdir(parents=True)
        (target / "personal-artifact").write_bytes(str(target).encode())
    result = integration.Backend(tmp_path / "trial", tmp_path / "snapshot", tmp_path / "game")
    result.root.mkdir()
    result.profile = tmp_path / "isolated"
    (result.profile / "Saves").mkdir(parents=True)
    return result, paths


def test_both_proton_roots_bind_and_restore_without_losing_originals(tmp_path, monkeypatch):
    result, paths = isolated(tmp_path, monkeypatch)
    result.bind_profile()
    assert paths["profile"].resolve() == result.profile
    assert paths["saves"].resolve() == result.profile / "Saves"
    local = json.loads((result.root / "runtime.local.json").read_text())
    assert local["binding"] == result.binding
    result.restore_profile()
    for target in (paths["profile"], paths["saves"]):
        assert not target.is_symlink()
        assert (target / "personal-artifact").read_bytes() == str(target).encode()
    assert result.lease is None


def test_second_root_bind_failure_rolls_back_first_root(tmp_path, monkeypatch):
    result, paths = isolated(tmp_path, monkeypatch)
    original = Path.symlink_to

    def second_fails(path, *args, **kwargs):
        if path == paths["saves"]:
            raise OSError("synthetic second-root binding failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "symlink_to", second_fails)
    with pytest.raises(OSError, match="second-root"):
        result.bind_profile()
    for target in (paths["profile"], paths["saves"]):
        assert not target.is_symlink()
        assert (target / "personal-artifact").read_bytes() == str(target).encode()


class Reader:
    def __init__(self, state):
        self.state = state

    def read(self):
        return self.state

    def close(self):
        pass


def test_poll_preserves_each_checkpoint_with_elapsed_wall_time(tmp_path):
    result = object.__new__(integration.Backend)
    result.root = tmp_path
    result.folder = tmp_path / "episodes/episode-001"
    (result.folder / "evidence").mkdir(parents=True)
    result.identity = {"pid": 1}
    result.process_identity = lambda: {"pid": 1}
    result.initial = {"episode_id": "episode", "evaluation": "base_game_v1"}
    state = {"team_id": 0, "winning_team": -1, "alive": True}
    result.native = Reader(state)
    write_json(tmp_path / "trial.json", {"started_at": time.time() - 30})
    assert result.poll(1.0) is None
    state["winning_team"] = 1
    assert result.poll(2.0) == "death"
    rows = [
        json.loads(line) for line in (result.folder / "evidence.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 2 and all(row["kind"] == "save" and row["elapsed"] >= 30 for row in rows)
    saved = json.loads((tmp_path / rows[0]["path"]).read_text())
    assert saved == {
        "schema_version": 2,
        "episode_id": "episode",
        "evaluation": "base_game_v1",
        "native_state": {"team_id": 0, "winning_team": -1, "alive": True},
    }
    result.process_identity = lambda: {"pid": 2}
    with pytest.raises(RuntimeError, match="process changed"):
        result.poll(3.0)


def test_recovery_requires_the_same_live_process_and_native_state(tmp_path, monkeypatch):
    result, _ = isolated(tmp_path, monkeypatch)
    folder = result.root / "episodes/episode-001"
    folder.mkdir(parents=True)
    write_json(folder / "setup.json", {"initial": {"episode_id": "episode"}})
    result.identity = {"pid": 1, "start_ticks": "5"}
    result.persist_runtime()
    recovered = integration.Backend(result.root)
    monkeypatch.setattr(integration, "NativeBaseGame", lambda: Reader({"turn": 7}))
    monkeypatch.setattr(
        integration, "process_identity", lambda pid: {"pid": pid, "start_ticks": "5"}
    )
    checkpoint = {
        "process": {"pid": 1, "start_ticks": "5"},
        "native_state": {"turn": 7},
        "profile": result.profile.name,
        "frame": "before.png",
    }
    assert recovered.recover(folder, checkpoint)
    recovered.restore_profile()
    assert not recovered.recover(folder, {**checkpoint, "native_state": {"turn": 8}})
    recovered.restore_profile()
