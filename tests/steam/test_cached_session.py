"""Finding the running official Steam client and resuming its logged-on session."""

import json

import pytest

from gamecua.games.steam import preparation


def client(tmp_path, monkeypatch):
    root = tmp_path / "client"
    executable = root / "ubuntu12_32/steam"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic official-client fixture")
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(preparation, "CLIENT", root)
    monkeypatch.setattr(preparation, "STATE", state)
    return root, state, executable


def process(proc, executable, pid, ticks="456", state="S"):
    folder = proc / str(pid)
    folder.mkdir(parents=True)
    (folder / "exe").symlink_to(executable)
    (folder / "stat").write_text(f"{pid} (steam) " + " ".join([state, "0", *["0"] * 17, ticks]))
    return folder


def steamrt(root):
    executable = root / "steamrt64/steam"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"synthetic steamrt64 client")
    return executable


def test_old_layout_decides_before_the_new_one(tmp_path, monkeypatch):
    root, _, old = client(tmp_path, monkeypatch)
    new = steamrt(root)
    proc = tmp_path / "proc"
    process(proc, new, 200, ticks="900")
    assert preparation.client_identity(proc) == {"pid": 200, "start_ticks": "900"}
    process(proc, old, 100)
    assert preparation.client_identity(proc) == {"pid": 100, "start_ticks": "456"}


def test_newest_live_client_of_this_user_is_found(tmp_path, monkeypatch):
    root, _, _ = client(tmp_path, monkeypatch)
    new = steamrt(root)
    wrapper = root / "runtime-wrapper"
    wrapper.write_bytes(b"synthetic runtime wrapper")
    proc = tmp_path / "proc"
    process(proc, new, 200, ticks="100")
    process(proc, wrapper, 201, ticks="200")
    process(proc, new, 202, ticks="300")
    process(proc, new, 203, ticks="400", state="Z")
    assert preparation.client_identity(proc)["pid"] == 202
    monkeypatch.setattr(preparation.os, "getuid", lambda: proc.stat().st_uid + 1)
    assert preparation.client_identity(proc) is None


def logged_on(tmp_path, monkeypatch):
    root, state, _ = client(tmp_path, monkeypatch)
    (root / "logs").mkdir()
    (root / "logs/connection_log.txt").write_text("[Logged On, synthetic session]\n")
    monkeypatch.setattr(preparation, "client_identity", lambda: {"pid": 123})
    return root


def test_live_session_can_resume_without_a_new_login(tmp_path, monkeypatch):
    logged_on(tmp_path, monkeypatch)
    assert preparation.verify_cached_session() == {"pid": 123}


@pytest.mark.parametrize("change", ["stopped", "logged_off"])
def test_stopped_or_logged_off_client_cannot_resume(tmp_path, monkeypatch, change):
    root = logged_on(tmp_path, monkeypatch)
    if change == "stopped":
        monkeypatch.setattr(preparation, "client_identity", lambda: None)
    else:
        with (root / "logs/connection_log.txt").open("a") as file:
            file.write("[Logged Off, synthetic session]\n")
    with pytest.raises(RuntimeError):
        preparation.verify_cached_session()


def test_cached_client_start_turns_offline_mode_off(tmp_path, monkeypatch):
    root, state, _ = client(tmp_path, monkeypatch)
    (root / "config").mkdir()
    (root / "config/loginusers.vdf").write_text('"WantsOfflineMode" "1"')
    monkeypatch.setattr(preparation, "logged_in", lambda *args: True)
    monkeypatch.setattr(preparation.subprocess, "Popen", lambda *args, **kwargs: None)
    preparation.start_cached_client()
    assert json.loads((state / "steam.json").read_text())["status"] == "authenticated"
    assert '"WantsOfflineMode" "0"' in (root / "config/loginusers.vdf").read_text()
