"""Synthetic startup checks enforce isolated retries and the original time boundary."""

from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from gamecua.games.peak import integration
from gamecua.games.steam import preparation
from tests.peak.test_progress import sample


@pytest.fixture
def startup(tmp_path, monkeypatch):
    """Drive PEAK preparation with a synthetic clock, launcher, observer and window."""
    clock = SimpleNamespace(now=0.0)
    options = SimpleNamespace(success_on=2, cancel_at=float("inf"))
    launches, captures = [], []
    snapshot = tmp_path / "snapshot"
    (snapshot / "compat").mkdir(parents=True)
    (snapshot / "compat/marker").write_text("synthetic clean prefix")
    client = tmp_path / "client"
    proton = client / "steamapps/common/Proton - Experimental/proton"
    proton.parent.mkdir(parents=True)
    proton.write_text("synthetic launcher")
    (proton.parent / "version").write_text("fixture")
    monkeypatch.setattr(preparation, "CLIENT", client)
    monkeypatch.setattr(integration, "native_environment", lambda *args: {})
    monkeypatch.setattr(integration.time, "monotonic", lambda: clock.now)
    monkeypatch.setenv("GAMECUA_PEAK_PROFILE_ROOT", str(tmp_path / "profiles"))

    def stage(installation, target):
        target.mkdir()
        return target

    monkeypatch.setattr(integration, "stage_game", stage)
    black = Image.new("RGB", (1280, 720))
    rendered = Image.new("RGB", (1280, 720), "white")
    ImageDraw.Draw(rendered).rectangle((0, 0, 639, 719), fill="black")

    def find():
        if backend.process is None:
            raise RuntimeError("found 0")
        return SimpleNamespace(get_full_property=lambda *args: SimpleNamespace(value=[42]))

    def capture(*, focus):
        captures.append((clock.now, focus))
        return rendered if len(launches) >= options.success_on else black

    adapter = SimpleNamespace(
        find=find, capture=capture, d=SimpleNamespace(intern_atom=lambda value: 1)
    )
    monkeypatch.setattr(integration, "Desktop", lambda **kwargs: adapter)
    root = tmp_path / "trial"
    folder = root / "episode-001"
    folder.mkdir(parents=True)
    backend = integration.Backend(root, snapshot, tmp_path / "installation")

    def stop_process():
        backend.process = None
        backend.process_id = None

    def launch(command, **kwargs):
        launches.append((backend.profile.name, clock.now, backend.binding))
        return SimpleNamespace(poll=lambda: None)

    def rows():
        row = sample(
            1,
            scene="Title",
            run_id="",
            character_present=False,
            stats_initialized=False,
            run_started=False,
        )
        row["binding"] = backend.binding
        return [row]

    monkeypatch.setattr(backend, "stop_process", stop_process)
    monkeypatch.setattr(backend, "rows", rows)
    monkeypatch.setattr(backend, "process_identity", lambda: {"pid": 42, "start_ticks": "fixture"})
    monkeypatch.setattr(integration.subprocess, "Popen", launch)

    def wait(seconds):
        clock.now += seconds
        return clock.now >= options.cancel_at

    stop = SimpleNamespace(is_set=lambda: clock.now >= options.cancel_at, wait=wait)
    return SimpleNamespace(
        backend=backend,
        folder=folder,
        stop=stop,
        clock=clock,
        options=options,
        launches=launches,
        captures=captures,
    )


def test_unrendered_title_restarts_in_an_isolated_prefix_without_another_episode(startup):
    result = startup.backend.prepare(startup.folder, startup.stop, 45)
    assert result["verified"]
    assert [row[0] for row in startup.launches] == ["episode-001", "episode-001-prepare-02"]
    assert startup.launches[0][2] != startup.launches[1][2]
    assert [row["reason"] for row in result["preparation_launches"]] == [
        "title_unrendered",
        "verified_title",
    ]
    assert startup.clock.now <= 45
    assert all(focus is False for _, focus in startup.captures)
    assert startup.captures[0][0] >= integration.TITLE_RENDER_SETTLE_SECONDS
    assert (startup.folder / "evidence/initial.json").is_file()


def test_title_retry_cannot_extend_the_original_preparation_deadline(startup):
    startup.options.success_on = 99
    with pytest.raises(InterruptedError):
        startup.backend.prepare(startup.folder, startup.stop, 20)
    assert startup.clock.now == 20
    assert len(startup.launches) == 2
    assert not (startup.folder / "initial.png").exists()


def test_cancelled_preparation_cannot_launch_a_retry(startup):
    startup.options.cancel_at = 6
    with pytest.raises(InterruptedError):
        startup.backend.prepare(startup.folder, startup.stop, 45)
    assert startup.clock.now == 6
    assert len(startup.launches) == 1


def test_preparation_launch_count_is_bounded_even_with_remaining_time(startup):
    startup.options.success_on = 99
    with pytest.raises(InterruptedError):
        startup.backend.prepare(startup.folder, startup.stop, 180)
    assert len(startup.launches) == 3
