"""Synthetic codec fixtures exercise native counter attribution under the story-v9 rubric."""

import hashlib
import json
import struct
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from gamecua.games.papers_please.haxe import read
from gamecua.games.papers_please.integration import Backend
from gamecua.games.papers_please.progress import PREDICATES, facts
from gamecua.games.papers_please.saves import discover_key, members
from gamecua.specs import Rubric

KEY = hashlib.md5(b"synthetic-test-format-key").digest()
BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"


def encrypt(text):
    raw = text.encode()
    raw += b"\0" * (-len(raw) % 4)
    values = list(struct.unpack(">" + "I" * (len(raw) // 4), raw))
    words = struct.unpack(">4I", KEY)
    count = len(values)
    total = 0
    z = values[-1]
    for _ in range(6 + 52 // count):
        total = (total + 0x9E3779B9) & 0xFFFFFFFF
        selector = (total >> 2) & 3
        for position in range(count):
            y = values[(position + 1) % count]
            mix = ((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ (
                (total ^ y) + (words[(position & 3) ^ selector] ^ z)
            )
            values[position] = (values[position] + mix) & 0xFFFFFFFF
            z = values[position]
    return struct.pack(">" + "I" * count, *values).hex()


def serialize(value):
    if value is None:
        return "n"
    if type(value) is int:
        return "i" + str(value)
    if isinstance(value, str):
        encoded = quote(value, safe="")
        return "y" + str(len(encoded)) + ":" + encoded
    if isinstance(value, list):
        return "a" + "".join(serialize(v) for v in value) + "h"
    if "__enum__" in value:
        return "w" + serialize(value["__enum__"]) + serialize(value["constructor"]) + ":0"
    prefix = "c" + serialize(value["__class__"]) if "__class__" in value else "o"
    return (
        prefix
        + "".join(serialize(k) + serialize(v) for k, v in value.items() if k != "__class__")
        + "g"
    )


def counters(processed, citations, approved=0, denied=0, stamps=0):
    return {
        "NumProcessed": processed,
        "NumCitations": citations,
        "NumApproved": approved,
        "NumDenied": denied,
        "NumStamps": stamps,
    }


def proof(processed=1, citations=0, day=1, end_id=None, ending=False, **extra):
    data = {
        "__class__": "play.stash.StashedGame",
        "stashVersion": 7,
        "gameVersion": "1.4.11.124",
        "endId": end_id,
        "day": {"__class__": "play.stash.StashedDay", "id": day, "citations": []},
        "storyStateFacts": {
            "facts": {
                "Game/Stat/" + k: {"value": {"text": str(v)}}
                for k, v in counters(processed, citations, **extra).items()
            }
        },
    }
    if ending:
        data["day"] = None
        data["screen"] = {"__enum__": "play.stash.StashedGameScreen", "constructor": "END"}
        data["storyStateFacts"]["facts"]["Game/Day"] = {"value": {"text": str(day)}}
    settings = (
        'PPSAVE1<members><entry key="easyMode" val="false"/>'
        '<entry key="languageCode" val="en"/><entry key="fullscreen" val="false"/></members>'
    )
    return json.dumps(
        {"stash": encrypt("PPSAVE1" + serialize(data)), "settings": encrypt(settings)}
    ).encode()


def day_proof(day=2, processed=5, citations=2, statistics_day=None):
    values = {"Game/Day": day, "Game/Stat/NumProcessed": processed}
    values["Game/Stat/NumCitations"] = citations
    daily = (
        "PPSAVE1<facts>"
        + "".join(f'<f p="{path}" v="{value}"/>' for path, value in values.items())
        + "</facts>"
    )
    stats = (
        "PPSAVE1<members>"
        f'<entry key="Day" val="{day if statistics_day is None else statistics_day}"/>'
        "</members>"
    )
    return json.dumps({"save": encrypt(daily), "stats": encrypt(stats)}).encode()


INITIAL = {"decoder_key": KEY.hex(), "processed": 0}


def test_story_v9_uses_only_known_predicates():
    rubric = Rubric.model_validate_json(
        (BENCHMARKS / "rubrics/papers-please/story-v9.json").read_text()
    )
    assert {m.predicate for m in rubric.milestones} == PREDICATES
    assert sum(m.points for m in rubric.milestones) == 100


def test_throughput_and_correct_inspections_count_separately():
    found, terminal = facts("history", proof(processed=10, citations=1), INITIAL)
    assert found == {"processed_5", "processed_10"}
    assert terminal is None
    found, _ = facts("history", proof(processed=12, citations=2), INITIAL)
    assert found == {"processed_5", "processed_10", "correct_10"}


def test_decision_and_stamp_counters_award_their_thresholds():
    found, _ = facts("history", proof(processed=0, approved=25, denied=15, stamps=50), INITIAL)
    assert found == {"approved_10", "approved_25", "denied_10", "denied_15"} | {
        "stamps_25",
        "stamps_50",
    }


def test_later_workday_requires_real_processed_progress():
    found, _ = facts("history", proof(processed=0, day=5), INITIAL)
    assert not found
    found, _ = facts("history", proof(processed=25, day=5), INITIAL)
    assert {"processed_20", "correct_25", "reach_day_4", "reach_day_5"} <= found
    assert "reach_day_6" not in found


def test_haxe_references_reuse_strings_and_objects():
    assert read("ay1:aR0h") == ["a", "a"]
    assert read("aoy1:ki1gr1h") == [{"k": 1}, {"k": 1}]
    assert read("anu2i3h") == [None, None, None, 3]


def test_discover_from_licensed_metadata_without_publishing_game_key():
    value = json.loads(proof())
    literal = b"synthetic-test-format-key"
    header = struct.pack("<8I", 0xFAB11BAF, 27, 32, 8, 40, len(literal), 0, 0)
    metadata = header + struct.pack("<II", len(literal), 0) + literal
    key = discover_key(metadata, value["settings"].encode())
    assert key == KEY
    assert members(value["settings"].encode(), key)["easyMode"] == "false"


def test_cursor_settle_preserves_one_action_and_rejects_invalid_before_movement(monkeypatch):
    from gamecua.desktop import X11Desktop
    from gamecua.games.papers_please.desktop import Desktop

    calls = []
    monkeypatch.setattr(
        X11Desktop, "_execute", lambda self, action, **kwargs: calls.append((action, kwargs))
    )
    desktop = object.__new__(Desktop)
    action = {"type": "click", "x": 0.5, "y": 0.6, "button": "left"}
    marker = object()
    desktop._execute(action, stop=marker, deadline=123)
    assert [item[0]["type"] for item in calls] == ["pointer", "wait", "control"]
    assert calls[-1][0] == {"type": "control", "buttons": ["left"], "duration": 0.3}
    assert all(item[1] == {"stop": marker, "deadline": 123} for item in calls)
    calls.clear()
    with pytest.raises(ValueError):
        desktop._execute(dict(action, unexpected=True))
    assert not calls


@pytest.mark.parametrize(
    "day,predicate", [(7, "reach_day_7"), (18, "reach_day_18"), (29, "reach_day_29")]
)
def test_workday_milestones_are_read_from_native_daily_saves(day, predicate):
    found, terminal = facts("save", day_proof(day=day), INITIAL)
    assert predicate in found
    assert terminal is None


def test_day_transition_without_processed_progress_cannot_earn_milestones():
    found, _ = facts("save", day_proof(day=29, processed=0, citations=0), INITIAL)
    assert not found


def backend(tmp_path, files):
    profile = tmp_path / "private-profile"
    profile.mkdir()
    for name, value in files.items():
        (profile / name).write_text(value)
    folder = tmp_path / "episode"
    (folder / "evidence").mkdir(parents=True)
    game = Backend.__new__(Backend)
    game.root, game.profile, game.folder = tmp_path, profile, folder
    game.initial = INITIAL
    game.process = SimpleNamespace(poll=lambda: None)
    game.seen = None
    return game


def test_backend_preserves_the_active_daily_save_when_no_stash_exists(tmp_path):
    payload = json.loads(day_proof())
    stale = json.loads(day_proof(day=1, statistics_day=2))
    game = backend(
        tmp_path,
        {"save_2.sav": payload["save"], "save_1.sav": stale["save"], "stats.sav": payload["stats"]},
    )
    assert game.poll(12.0) is None
    row = json.loads((game.folder / "evidence.jsonl").read_text())
    assert row["kind"] == "save"
    preserved = (tmp_path / row["path"]).read_bytes()
    assert json.loads(preserved) == {"save": payload["save"]}
    assert hashlib.sha256(preserved).hexdigest() == row["sha256"]
    assert "reach_day_2" in facts(row["kind"], preserved, INITIAL)[0]
    assert game.poll(13.0) is None
    assert len((game.folder / "evidence.jsonl").read_text().splitlines()) == 1


def test_backend_reports_the_native_terminal_of_a_new_stash(tmp_path):
    payload = json.loads(proof(processed=11, citations=5, day=2, end_id="in-debt", ending=True))
    game = backend(tmp_path, {"stash.sav": payload["stash"]})
    assert game.poll(12.0) == "death"
    row = json.loads((game.folder / "evidence.jsonl").read_text())
    assert row["kind"] == "history"
    assert json.loads((tmp_path / row["path"]).read_bytes()) == {"stash": payload["stash"]}


def test_bankruptcy_end_screen_retains_earned_progress_and_reports_death():
    found, terminal = facts(
        "history", proof(processed=11, citations=5, day=2, end_id="in-debt", ending=True), INITIAL
    )
    assert terminal == "death"
    assert found == {"processed_5", "processed_10", "reach_day_2"}


@pytest.mark.parametrize("end_id", ["escape", "ignore-ezic", "help-ezic-hold-fire"])
def test_successful_endings_are_victories(end_id):
    found, terminal = facts(
        "history", proof(processed=100, day=31, end_id=end_id, ending=True), INITIAL
    )
    assert terminal == "victory" and "story_success" in found
    assert {"reach_day_2", "reach_day_29", "processed_100"} <= found


@pytest.mark.parametrize("end_id", ["family-dead", "help-few-ezic", "killed-guard"])
def test_other_endings_retain_points_without_awarding_success(end_id):
    found, terminal = facts(
        "history", proof(processed=100, day=31, end_id=end_id, ending=True), INITIAL
    )
    assert terminal == "death" and "story_success" not in found
    assert "reach_day_29" in found


def test_an_ending_id_outside_the_ending_screen_is_not_terminal():
    assert facts("history", proof(processed=5, day=3, end_id="escape"), INITIAL)[1] is None


@pytest.mark.parametrize("ending_id,ending_day", [(None, 20), ("escape", 29), ("ignore-ezic", 31)])
def test_canonical_scorer_counts_native_progress_and_appends_scores(
    tmp_path, ending_id, ending_day
):
    from gamecua.catalog import Catalog
    from gamecua.evidence import score
    from gamecua.trials import Trial

    catalog = Catalog(BENCHMARKS)
    spec = catalog.trials["papers-please-story-v2-pointer-live-3h"]
    rubric = catalog.rubrics[spec.rubric_id]
    trial = Trial(
        tmp_path / "trial",
        spec,
        rubric,
        catalog.games[spec.game_id],
        catalog.models[spec.model_id],
        inputs=catalog.inputs[spec.inputs_id],
    )
    folder = trial.root / "episodes" / "episode-001"
    folder.mkdir(parents=True)
    (folder / "setup.json").write_text(json.dumps({"verified": True, "initial": INITIAL}))
    path = folder / "daily.native.json"
    path.write_bytes(
        day_proof(day=20, processed=100, citations=2)
        if ending_id is None
        else proof(processed=100, citations=2, day=ending_day, end_id=ending_id, ending=True)
    )
    row = {
        "kind": "save" if ending_id is None else "history",
        "elapsed": 12.0,
        "path": str(path.relative_to(trial.root)),
    }
    (folder / "evidence.jsonl").write_text(json.dumps(row) + "\n")
    trial.state["episodes"].append(
        {"id": "episode-001", "status": "completed", "reason": "deadline", "segments": []}
    )
    trial.budget.start()
    trial.finish("completed", "deadline")
    first_path, first = score(trial.root)
    first_bytes = first_path.read_bytes()
    second_path, second = score(trial.root)
    expected = {f"processed_{n}" for n in (5, 10, 15, 20, 30, 45, 60, 80, 100)}
    expected |= {f"correct_{n}" for n in (10, 25, 30, 45, 70, 95)}
    expected |= {f"reach_day_{n}" for n in (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20)}
    if ending_id:
        expected |= {"reach_day_23", "reach_day_26", "reach_day_29", "story_success"}
    milestones = {m.id: m for m in rubric.milestones if m.predicate in expected}
    assert {a["milestone_id"] for a in first["awards"]} == set(milestones)
    assert first["score"] == second["score"] == sum(m.points for m in milestones.values())
    assert first["comparison_eligible"]
    assert second_path != first_path and first_path.read_bytes() == first_bytes


@pytest.mark.parametrize("typed", [False, True])
def test_canonical_trial_uses_native_death_with_correct_lifecycle(tmp_path, typed):
    from PIL import Image

    from gamecua.catalog import Catalog
    from gamecua.evidence import score
    from gamecua.trials import Budget, Trial

    catalog = Catalog(BENCHMARKS)
    name = (
        "papers-please-jev-story-v3-pointer-live-2h"
        if typed
        else "papers-please-story-v2-pointer-live-3h"
    )
    spec = catalog.trials[name].model_copy(update={"total_seconds": 60.0})
    clock = [100.0]
    contexts = []

    class Recorder:
        def __init__(self, *args):
            pass

        def close(self):
            pass

    class Adapter:
        def capture(self):
            return Image.new("RGB", (1140, 640))

        def execute(self, *args, **kwargs):
            pass

        def release_all(self):
            pass

    class SyntheticBackend(Backend):
        def __init__(self, root):
            self.root = root
            self.adapter = Adapter()
            self.process = SimpleNamespace(poll=lambda: None)
            self.identity = {"synthetic": True}
            self.preparations = 0

        def checkpoint(self):
            return self.identity

        def prepare(self, folder, stop, deadline):
            self.preparations += 1
            if self.preparations > 1:
                clock[0] += 3
            self.folder = folder
            self.profile = tmp_path / ("profile-" + str(self.preparations))
            self.profile.mkdir()
            self.initial = INITIAL
            self.seen = None
            (self.profile / "stash.sav").write_text(json.loads(proof(processed=0))["stash"])
            (folder / "evidence").mkdir()
            return {"verified": True, "initial": INITIAL}

        def close(self, **kwargs):
            pass

    class ScriptedAgent:
        def __init__(self, *args, **kwargs):
            pass

        def decide(self, image, memory, history, stop, deadline):
            contexts.append((memory, history.copy()))
            clock[0] += 1
            if backend.preparations == 1:
                payload = json.loads(
                    proof(processed=11, citations=5, day=2, end_id="in-debt", ending=True)
                )
                (backend.profile / "stash.sav").write_text(payload["stash"])
            else:
                stop.set()
            return {
                "observation": "synthetic fixture",
                "hypothesis": "synthetic fixture",
                "memory": "synthetic same-model observation",
                "terminal_candidate": False,
                "action": {"type": "wait", "seconds": 0.1},
            }, {}

        def close(self):
            pass

    backend = SyntheticBackend((tmp_path / "trial").resolve())
    trial = Trial(
        backend.root,
        spec,
        catalog.rubrics[spec.rubric_id],
        catalog.games[spec.game_id],
        catalog.models[spec.model_id],
        backend=backend,
        agent_factory=ScriptedAgent,
        recorder=Recorder,
        inputs=catalog.inputs[spec.inputs_id],
    )
    trial.budget = Budget(trial.state, spec.total_seconds, lambda: clock[0], lambda: clock[0])
    trial.run(install_signals=False, acquire_lease=False)
    episodes = trial.state["episodes"]
    assert episodes[0]["reason"] == "death"
    assert trial.state["deadline"] == 160.0
    assert contexts[0] == ("", [])
    _, result = score(trial.root)
    assert result["score"] == 7 and result["episodes"][0]["outcome"] == "death"
    if typed:
        assert len(episodes) == backend.preparations == 1
        assert trial.state["reason"] == "death_without_memory"
        assert result["completion_status"] == "completed"
    else:
        assert len(episodes) == backend.preparations == 2
        assert contexts[1] == ("synthetic same-model observation", [])
        assert trial.state["chargeable_seconds"] == 5.0
        assert result["completion_status"] == "incomplete"
        assert not result["comparison_eligible"]
        context = json.loads(
            (
                trial.root / "episodes/episode-002/segments/segment-001/initial_agent_context.json"
            ).read_text()
        )
        assert context["provenance"]["kind"] == "death_inheritance"
        assert "reach-day" not in json.dumps(context)


class Adapter:
    def release_all(self, recovery=False):
        self.released = recovery


def test_recover_reattaches_to_the_running_game_without_repeating_evidence(tmp_path):
    import subprocess
    import sys

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True
    )
    try:
        root = tmp_path / "trial"
        folder = root / "episodes/episode-001"
        (folder / "evidence").mkdir(parents=True)
        (folder / "setup.json").write_text(json.dumps({"verified": True, "initial": INITIAL}))
        profile = tmp_path / ".profiles/trial/episode-001"
        profile.mkdir(parents=True)
        first = Backend.__new__(Backend)
        first.root, first.folder, first.profile = root, folder, profile
        first.process, first.initial, first.seen = process, INITIAL, None
        first.identity = first.process_identity()
        checkpoint = first.checkpoint()
        (profile / "stash.sav").write_text(json.loads(proof(processed=5))["stash"])
        assert first.poll(1.0) is None

        resumed = Backend.__new__(Backend)
        resumed.root, resumed.adapter = root, Adapter()
        assert resumed.recover(folder, {**checkpoint, "frame": "unused.png"})
        assert resumed.adapter.released is True
        assert resumed.poll(2.0) is None
        assert len((folder / "evidence.jsonl").read_text().splitlines()) == 1
        (profile / "stash.sav").write_text(json.loads(proof(processed=10))["stash"])
        assert resumed.poll(3.0) is None
        rows = [json.loads(r) for r in (folder / "evidence.jsonl").read_text().splitlines()]
        assert [row["elapsed"] for row in rows] == [1.0, 3.0]

        stale = {**checkpoint, "process": {**checkpoint["process"], "start_ticks": "0"}}
        assert not resumed.recover(folder, stale)
        assert resumed.recover(folder, checkpoint)
        resumed.close_process()
        assert process.wait(timeout=5) is not None
        assert not resumed.recover(folder, checkpoint)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
