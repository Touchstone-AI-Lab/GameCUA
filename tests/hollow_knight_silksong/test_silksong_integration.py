"""Silksong predicates, profile isolation, evidence polling and pause settling on synthetic saves."""

import base64
import itertools
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from PIL import Image, ImageDraw

from gamecua.catalog import Catalog
from gamecua.games.hollow_knight_silksong import integration, progress, setup
from gamecua.games.hollow_knight_silksong.saves import HEADER, KEY
from gamecua.specs import InputProfile, Rubric
from gamecua.typed import merge

PLAYER = {
    **{field: False for field in progress.FLAGS.values()},
    **{field: False for field in progress.MARKS.values()},
    "hasNeedleThrow": False,
    "CompletedEndings": 0,
    "scenesVisited": ["Tut_01", "Tut_03"],
    "health": 5,
    "respawnType": 0,
    "geo": 0,
    "HeroCorpseMoneyPool": 0,
    "ShellShards": 0,
    "EnemyJournalKillData": {"list": []},
    "Collectables": {"savedData": []},
    "Tools": {"savedData": []},
    "QuestCompletionData": {"savedData": []},
}
NEW_SCENES = [f"Scene_{n:02d}" for n in range(20)]
BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def encode(player=None, **changes):
    document = {"playerData": {**PLAYER, **(player or {}), **changes}, "sceneData": {}}
    plain = json.dumps(document).encode()
    plain += bytes([16 - len(plain) % 16]) * (16 - len(plain) % 16)
    encryptor = Cipher(algorithms.AES(KEY), modes.ECB()).encryptor()
    payload = base64.b64encode(encryptor.update(plain) + encryptor.finalize())
    size, prefix = len(payload), bytearray()
    while True:
        byte, size = size & 0x7F, size >> 7
        prefix.append(byte | (0x80 if size else 0))
        if not size:
            return HEADER + bytes(prefix) + payload + b"\x0b"


def profile(root, directory="default", **changes):
    saves = root / setup.SAVES / directory
    saves.mkdir(parents=True)
    (saves / "user1.dat").write_bytes(encode(**changes))
    (saves / "shared.dat").write_bytes(b"shared")
    (root / setup.PREFS).parent.mkdir(parents=True, exist_ok=True)
    (root / setup.PREFS).write_text("<prefs/>")
    return saves


def test_facts_award_only_newly_recorded_progress():
    initial = progress.summary(encode())
    everything = {field: True for field in progress.FLAGS.values()}
    found, terminal = progress.facts(
        "save", encode(scenesVisited=PLAYER["scenesVisited"] + NEW_SCENES, **everything), initial
    )
    assert found == set(progress.FLAGS) | {f"new_scenes_{n}" for n in progress.NEW_SCENES}
    assert terminal is None
    assert progress.facts("save", encode(), initial) == (set(), None)
    assert progress.facts("save", encode(defeatedBellBeast=True), initial)[0] == {
        "bell_beast_defeated"
    }
    already = progress.summary(encode(visitedMosstown=True))
    assert progress.facts("save", encode(visitedMosstown=True), already)[0] == set()


def test_a_recorded_ending_is_the_verified_completion():
    initial = progress.summary(encode())
    for ending in (1, 2, 4, 8):
        assert progress.facts("save", encode(CompletedEndings=ending), initial) == (
            set(),
            "victory",
        )
    already = progress.summary(encode(CompletedEndings=1))
    assert progress.facts("save", encode(CompletedEndings=1), already) == (set(), None)
    assert progress.facts("save", encode(CompletedEndings=3), already)[1] == "victory"


def journal(*kills):
    return {"list": [{"Name": f"Enemy {n}", "Record": {"Kills": k}} for n, k in enumerate(kills)]}


def test_tallies_count_kills_collections_characters_and_rest():
    initial = progress.summary(encode())
    found, terminal = progress.facts(
        "save",
        encode(
            EnemyJournalKillData=journal(30, 20, 0),
            ShellShards=60,
            geo=5,
            HeroCorpseMoneyPool=15,
            Collectables={"savedData": [{"Name": "Rosary_Set_Frayed", "Data": {"Amount": 1}}]},
            Tools={
                "savedData": [
                    {"Name": "Bone Necklace", "Data": {"IsUnlocked": True}},
                    {"Name": "Hidden", "Data": {"IsUnlocked": False}},
                ]
            },
            QuestCompletionData={
                "savedData": [
                    {"Name": "Citadel Seeker", "Data": {"IsAccepted": True}},
                    {"Name": "Seen only", "Data": {"IsAccepted": False}},
                ]
            },
            metSherma=True,
            metMapper=True,
            MetBoneBottomShopKeep=True,
            respawnType=1,
            visitedMossCave=True,
            greatBoneGateOpened=True,
        ),
        initial,
    )
    assert terminal is None
    assert found == {
        "moss_cave_visited",
        "bone_gate_opened",
        "bench_rested",
        "enemy_kinds_1",
        "enemy_kinds_2",
        "enemy_kills_5",
        "enemy_kills_10",
        "enemy_kills_25",
        "enemy_kills_50",
        "shell_shards_10",
        "shell_shards_25",
        "shell_shards_50",
        "rosaries_1",
        "rosaries_20",
        "items_1",
        "tools_1",
        "wishes_1",
        "npcs_1",
        "npcs_3",
    }


def test_abilities_count_from_the_tool_or_the_ability_flag():
    initial = progress.summary(encode())

    def tools(unlocked):
        return {"savedData": [{"Name": "Silk Spear", "Data": {"IsUnlocked": unlocked}}]}

    assert progress.facts("save", encode(Tools=tools(True)), initial)[0] == {
        "silkspear_gained",
        "tools_1",
    }
    assert progress.facts("save", encode(Tools=tools(False)), initial)[0] == set()
    assert progress.facts("save", encode(hasNeedleThrow=True), initial)[0] == {"silkspear_gained"}
    assert progress.facts("save", encode(hasDash=True), initial)[0] == {"swift_step_gained"}


def test_a_save_at_zero_health_is_a_native_death():
    initial = progress.summary(encode())
    assert progress.facts("save", encode(health=0), initial) == (set(), "death")
    assert progress.facts("save", encode(health=1), initial) == (set(), None)
    assert progress.facts("save", encode(health=0, CompletedEndings=1), initial)[1] == "victory"


def test_points_v1_has_more_than_fifty_known_points_worth_one_hundred():
    rubric = Rubric.model_validate_json(
        (BENCHMARKS / "rubrics/hollow-knight-silksong/points-v1.json").read_text()
    )
    predicates = [m.predicate for m in rubric.milestones]
    assert len(rubric.milestones) == 52 and set(predicates) == progress.PREDICATES
    assert sum(m.points for m in rubric.milestones) == 100
    assert {m.points for m in rubric.milestones} == {1, 2}
    assert not any(m.prerequisites for m in rubric.milestones)


def test_every_trial_uses_points_v1_with_its_budget():
    catalog = Catalog(BENCHMARKS)
    trials = [t for t in catalog.trials.values() if t.game_id == "hollow-knight-silksong"]
    assert len(trials) == 12
    for trial in trials:
        assert trial.rubric_id == "hollow-knight-silksong-points-v1"
        jev = trial.model_id == "jev-1-14"
        assert trial.total_seconds == (3600 if jev else 10800)


def test_every_jev_answer_holds_a_direction_for_one_step():
    profile = InputProfile.model_validate_json(
        (BENCHMARKS / "inputs/hollow-knight-silksong/keys-v1.json").read_text()
    )
    arrows = {"Up", "Down", "Left", "Right"}
    for combination in itertools.product(*(group.buttons for group in profile.groups.values())):
        answers = {name: {"choice": choice} for name, choice in zip(profile.groups, combination)}
        action = merge(profile, answers)
        assert action["type"] == "control" and action["duration"] == profile.step_seconds
        assert arrows & set(action["keys"])


def test_declared_pause_settle_matches_the_integration():
    game = json.loads((BENCHMARKS / "games/hollow-knight-silksong/game.json").read_text())
    assert game["timing"] == "realtime"
    assert game["pause"] == {
        "method": "process",
        "settle_seconds": integration.THAW_SETTLE_SECONDS,
    }
    assert game["introduction"] and game["controls"]


def test_new_scene_milestones_count_only_scenes_absent_from_setup():
    initial = progress.summary(encode())
    visited = PLAYER["scenesVisited"]
    for count in (1, 2, 6, 9, 10, 19, 20):
        found, _ = progress.facts(
            "save", encode(scenesVisited=visited + NEW_SCENES[:count]), initial
        )
        assert found == {f"new_scenes_{n}" for n in progress.NEW_SCENES if n <= count}
    repeated = encode(scenesVisited=visited + visited + NEW_SCENES[:1])
    assert progress.facts("save", repeated, initial)[0] == {"new_scenes_1"}


def test_save_directory_finds_the_account_directory(tmp_path):
    profile(tmp_path, "123")
    assert setup.save_directory(tmp_path).name == "123"


def test_snapshot_capture_copies_the_prepared_profile(tmp_path):
    profile(tmp_path / "source")
    target = setup.capture_snapshot(tmp_path / "source", tmp_path / "game", tmp_path / "snapshot")
    assert sorted(p.name for p in target.iterdir()) == [
        "prefs",
        "shared.dat",
        "snapshot.manifest.json",
        "user1.dat",
    ]
    assert progress.summary((target / "user1.dat").read_bytes()) == progress.summary(encode())
    assert (target / "prefs").read_text() == "<prefs/>"


def hud_frame(disc=(85, 45, 55), bolt=(240, 240, 240), background=(0, 0, 0)):
    frame = Image.new("RGB", (1280, 720), background)
    draw = ImageDraw.Draw(frame)
    draw.ellipse((58, 47, 105, 88), fill=disc)
    draw.rectangle((78, 64, 86, 68), fill=bolt)
    return frame


def test_hud_visible_requires_the_silk_spool():
    assert integration.hud_visible(hud_frame())
    assert not integration.hud_visible(Image.new("RGB", (1280, 720)))
    assert not integration.hud_visible(Image.new("RGB", (1280, 720), (255, 255, 255)))
    assert not integration.hud_visible(hud_frame(disc=(40, 40, 40)))
    assert not integration.hud_visible(hud_frame(bolt=(85, 45, 55)))
    assert not integration.hud_visible(hud_frame(bolt=(85, 45, 55), background=(255, 255, 255)))


def test_process_environment_selects_d3d12_and_isolates_xdg(tmp_path):
    environment = integration.native_environment(tmp_path)
    assert environment["GALLIUM_DRIVER"] == "d3d12"
    assert environment["XDG_CONFIG_HOME"] == str(tmp_path / "config")
    assert environment["SteamAppId"] == str(setup.APP_ID)
    assert "-force-clamped" in setup.ARGUMENTS and "-force-glcore45" in setup.ARGUMENTS


def bare_backend(tmp_path, snapshot=None):
    backend = object.__new__(integration.Backend)
    backend.root = tmp_path / "trial"
    backend.folder = backend.root / "episodes/1"
    (backend.folder / "evidence").mkdir(parents=True)
    backend.profile = tmp_path / "profile"
    backend.profile.mkdir()
    backend.snapshot = snapshot
    backend.process = SimpleNamespace(poll=lambda: None)
    return backend


def test_profile_installs_snapshot_under_account_directory(tmp_path):
    profile(tmp_path / "source")
    snapshot = setup.capture_snapshot(tmp_path / "source", None, tmp_path / "snapshot")
    backend = bare_backend(tmp_path, snapshot)
    backend.install_profile("424242")
    assert backend.save == backend.profile / "config" / setup.SAVES / "424242/user1.dat"
    assert backend.save.read_bytes() == (snapshot / "user1.dat").read_bytes()
    assert (backend.profile / "config" / setup.PREFS).read_text() == "<prefs/>"


def test_poll_preserves_only_new_decodable_saves(tmp_path):
    backend = bare_backend(tmp_path)
    backend.save = tmp_path / "user1.dat"
    backend.save.write_bytes(encode())
    backend.initial = progress.summary(encode())
    backend.seen = integration.hashlib.sha256(encode()).hexdigest()
    assert backend.poll(1.0) is None
    assert not (backend.folder / "evidence.jsonl").exists()
    backend.save.write_bytes(b"partial")
    assert backend.poll(2.0) is None
    assert not (backend.folder / "evidence.jsonl").exists()
    backend.save.write_bytes(encode(defeatedMossMother=True))
    assert backend.poll(3.0) is None
    rows = [
        json.loads(line) for line in (backend.folder / "evidence.jsonl").read_text().splitlines()
    ]
    assert [row["elapsed"] for row in rows] == [3.0] and rows[0]["kind"] == "save"
    evidence = Path(backend.root / rows[0]["path"]).read_bytes()
    assert progress.facts("save", evidence, backend.initial)[0] == {"moss_mother_defeated"}
    assert backend.poll(4.0) is None
    assert len((backend.folder / "evidence.jsonl").read_text().splitlines()) == 1
    backend.save.write_bytes(encode(defeatedMossMother=True, health=0))
    assert backend.poll(5.0) == "death"


def test_preparation_wait_honours_cancellation():
    backend = object.__new__(integration.Backend)
    stop = threading.Event()
    stop.set()
    with pytest.raises(InterruptedError):
        backend.wait(5, stop, float("inf"))


def test_thaw_lets_the_resumed_game_settle_before_input(monkeypatch):
    calls = []

    class Pause:
        def thaw(self):
            calls.append("thaw")

    backend = object.__new__(integration.Backend)
    monkeypatch.setattr(integration.time, "sleep", lambda seconds: calls.append(seconds))
    backend.thaw()
    assert calls == []
    backend.pause_handle = Pause()
    backend.thaw()
    assert calls == ["thaw", integration.THAW_SETTLE_SECONDS]
    assert 0.02 <= integration.THAW_SETTLE_SECONDS <= 0.1


def test_official_installation_and_steam_client(tmp_path, monkeypatch):
    from gamecua.games.steam import preparation

    monkeypatch.setattr(
        preparation,
        "installed_app",
        lambda app: {"directory": str(tmp_path), "build_id": "1", "app_id": app},
    )
    assert integration.official_installation() == tmp_path
    started = []
    monkeypatch.setattr(preparation, "start_cached_client", lambda: started.append(True))
    monkeypatch.setattr(preparation, "client_identity", lambda: {"pid": 1})
    integration.ensure_steam_client()
    assert started == []
    monkeypatch.setattr(preparation, "client_identity", lambda: None)
    integration.ensure_steam_client()
    assert started == [True]


def test_recover_reattaches_to_the_running_game_without_repeating_evidence(tmp_path):
    import subprocess
    import sys

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
        initial = progress.summary(encode())
        (folder / "setup.json").write_text(json.dumps({"verified": True, "initial": initial}))
        saves = profile((tmp_path / ".profiles/trial/episode-001/config"), "424242")
        first = object.__new__(integration.Backend)
        first.root, first.folder, first.save = root, folder, saves / "user1.dat"
        first.process, first.initial = process, initial
        first.seen = integration.hashlib.sha256(encode()).hexdigest()
        first.identity = first.process_identity()
        checkpoint = first.checkpoint()
        first.save.write_bytes(encode(defeatedMossMother=True))
        assert first.poll(1.0) is None

        resumed = object.__new__(integration.Backend)
        resumed.root, resumed.adapter = root, Adapter()
        assert resumed.recover(folder, {**checkpoint, "frame": "unused.png"})
        assert resumed.save == first.save and resumed.adapter.released is True
        assert resumed.poll(2.0) is None
        assert len((folder / "evidence.jsonl").read_text().splitlines()) == 1
        first.save.write_bytes(encode(defeatedMossMother=True, health=0))
        assert resumed.poll(3.0) == "death"
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
