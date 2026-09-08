"""Environment container arguments, observer authentication and Steam preparation state."""

import asyncio
import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gamecua.environments import session
from gamecua.environments.manager import Environment, apparmor_profile
from gamecua.evidence import export
from gamecua.games.steam import preparation


def test_observer_authentication_and_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(session, "STATE", tmp_path)
    monkeypatch.setattr(session, "WORK", tmp_path)
    (tmp_path / "access-token").write_text("private-access")

    async def check():
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", session.handle)
        async with TestClient(TestServer(app)) as client:
            assert (await client.get("/status")).status == 403
            assert (await client.post("/auth", data="wrong")).status == 403
            assert (await client.post("/auth", data="private-access")).status == 200
            response = await client.get("/status")
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert (await response.json())["read_only"]
            assert (await client.get("/desktop/../../etc/passwd")).status == 404

    monkeypatch.setenv("DISPLAY", ":99")
    asyncio.run(check())


def test_private_environment_state_never_exported(tmp_path):
    for name in ("environment.json", "environment.local.json", "access-token", "steam.json"):
        (tmp_path / name).write_text("{}")
    export(tmp_path, tmp_path.parent / "exported")
    assert [p.name for p in (tmp_path.parent / "exported").iterdir()] == ["environment.json"]


def test_qr_disappearance_and_stale_profile_do_not_mean_login(monkeypatch, tmp_path):
    client = tmp_path / "client"
    (client / "config").mkdir(parents=True)
    (client / "logs").mkdir()
    (client / "config/loginusers.vdf").write_text('"AccountName" "private" "MostRecent" "1"')
    (client / "logs/connection_log.txt").write_text("[Logged On, 1, 1]")
    monkeypatch.setattr(preparation, "CLIENT", client)
    assert not preparation.logged_in(10**12)
    assert preparation.logged_in(0)
    assert not preparation.logged_in(0, (client / "logs/connection_log.txt").stat().st_size)
    (client / "logs/connection_log.txt").write_text("QR disappeared")
    assert not preparation.logged_in(0)


def test_qr_uri_is_constrained():
    assert preparation.QR.fullmatch("https://s.team/q/123456/abcdef")
    assert not preparation.QR.fullmatch("https://evil.test/qr")
    assert not preparation.QR.fullmatch("https://s.team/q/abc\npassword")


def test_observer_links_steps_to_original_records(monkeypatch, tmp_path):
    root = tmp_path / "trial"
    folder = root / "episodes/episode/segments/segment"
    folder.mkdir(parents=True)
    (root / "trial.json").write_text(json.dumps({"id": "trial-id"}))
    (folder / "000001.json").write_text(json.dumps({"step": 1, "execution_status": "completed"}))
    monkeypatch.setattr(session, "WORK", tmp_path)
    rows = session.events()
    assert rows[0]["steps"][0]["path"] == "trial/episodes/episode/segments/segment/000001.json"
    assert rows[0]["steps"][0]["record"]["execution_status"] == "completed"


def test_browser_script_preserves_javascript_newlines_and_absolute_websocket_path():
    assert "'\\n'" in session.PAGE
    assert "'\n'" not in session.PAGE
    assert "path=%2Fwebsocket" in session.PAGE


def test_qr_cleanup_removes_partial_challenges(monkeypatch, tmp_path):
    monkeypatch.setattr(preparation, "STATE", tmp_path)
    for name in ("steam-qr.png", "steam-qr.next.png"):
        (tmp_path / name).touch()
    preparation.clear()
    assert not list(tmp_path.glob("steam-qr*.png"))


def test_new_client_login_matches_native_connection_to_persisted_account(monkeypatch, tmp_path):
    client = tmp_path / "client"
    (client / "config").mkdir(parents=True)
    (client / "logs").mkdir()
    (client / "config/config.vdf").write_text('"Accounts" { "SteamID" "76561197960265851" }')
    (client / "logs/connection_log.txt").write_text(
        "[Logged On, 4, 7] [U:1:123] LogOnResponse() : processing complete"
    )
    monkeypatch.setattr(preparation, "CLIENT", client)
    assert preparation.logged_in(0)
    (client / "config/config.vdf").write_text('"Accounts" { "SteamID" "76561197960265852" }')
    assert not preparation.logged_in(0)


def test_native_game_log_projection_preserves_gameplay_but_excludes_steam_state():
    from gamecua.games.slay_the_spire.setup import public_log

    raw = (
        b"INFO steam.SteamIntegration> ACCOUNT ID: 123\n"
        b"SteamAPI_Init(): loaded private runtime\n"
        b"SteamInternal_SetMinidumpSteamID: Caching Steam ID: 76561197960265852 [API loaded no]\n"
        b"INFO core.CardCrawlGame> DistributorPlatform=steam\n"
        b"INFO dungeons.AbstractDungeon> MONSTER: Cultist\n"
    )
    assert public_log(raw) == b"INFO dungeons.AbstractDungeon> MONSTER: Cultist\n"


@pytest.mark.parametrize("app_id", [646570, 219740])
def test_steam_preparation_reports_skipped_launch_without_starting_game(
    monkeypatch, tmp_path, app_id
):
    installation = {"directory": "/private/game", "build_id": "123", "app_id": app_id}
    monkeypatch.setattr(preparation, "STATE", tmp_path)
    monkeypatch.setattr(preparation, "installed_app", lambda _: installation)

    def reject_launch(*args, **kwargs):
        raise AssertionError("Installed games must not be launched during preparation")

    monkeypatch.setattr(preparation.subprocess, "Popen", reject_launch)
    preparation.await_game(app_id, preparation.time.monotonic() + 10)
    status = json.loads((tmp_path / "steam.json").read_text())
    assert status["status"] == "ready"
    assert status["app_id"] == app_id
    assert status["launch_verification"] == "skipped"


def nvidia_run_arguments(monkeypatch, tmp_path, runtimes):
    from gamecua.environments import manager

    calls = []

    def fake_docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "run":
            raise RuntimeError("stop after container arguments")
        return "image-id"

    monkeypatch.setattr(manager, "docker", fake_docker)
    with pytest.raises(RuntimeError, match="stop after"):
        Environment(tmp_path / "gpu").create(None, None, renderer="nvidia", gpu="5")
    return " ".join(next(c for c in calls if c[0] == "run"))


def test_nvidia_renderer_requests_one_graphics_gpu(monkeypatch, tmp_path):
    run = nvidia_run_arguments(monkeypatch, tmp_path, {"runc": {}, "nvidia": {}})
    assert "--runtime nvidia" in run
    assert "NVIDIA_VISIBLE_DEVICES=5" in run
    assert "NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compat32" in run
    assert "nvidia.com/gpu" not in run
    assert "GAMECUA_RENDER_DEVICE=nvidia5" in run
    assert "LIBGL_ALWAYS_SOFTWARE=0" in run


def test_container_runs_as_the_host_user(monkeypatch, tmp_path):
    import os

    run = nvidia_run_arguments(monkeypatch, tmp_path, {"runc": {}, "nvidia": {}})
    assert f"--user {os.getuid()}:{os.getgid()}" in run


def test_session_names_an_unknown_host_uid_with_the_state_home(tmp_path):
    import os

    passwd, group = tmp_path / "passwd", tmp_path / "group"
    passwd.write_text("root:x:0:0:root:/root:/bin/bash\n")
    group.write_text("root:x:0:\n")
    session.ensure_account(passwd, group)
    session.ensure_account(passwd, group)
    uid, gid = os.getuid(), os.getgid()
    assert passwd.read_text().count(f":{uid}:{gid}::/state/home:") == (uid != 0) * 1
    assert group.read_text().count(f"x:{gid}:") == 1


def test_nvidia_renderer_uses_cdi_without_a_registered_runtime(monkeypatch, tmp_path):
    run = nvidia_run_arguments(monkeypatch, tmp_path, {"runc": {}})
    assert "--device nvidia.com/gpu=5" in run
    assert "--runtime" not in run
    assert "NVIDIA_VISIBLE_DEVICES" not in run
    assert "GAMECUA_RENDER_DEVICE=nvidia5" in run
    assert "LIBGL_ALWAYS_SOFTWARE=0" in run


def wsl_run_arguments(monkeypatch, tmp_path):
    from gamecua.environments import manager

    calls = []

    def fake_docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "run":
            raise RuntimeError("stop after container arguments")
        return "image-id"

    monkeypatch.setattr(manager, "docker", fake_docker)
    with pytest.raises(RuntimeError, match="stop after"):
        Environment(tmp_path / "wsl").create(None, None, renderer="wsl-d3d12", gpu="NVIDIA")
    return " ".join(next(c for c in calls if c[0] == "run"))


def test_wsl_d3d12_renderer_mounts_driver_and_names_adapter(monkeypatch, tmp_path):
    run = wsl_run_arguments(monkeypatch, tmp_path)
    assert "--device /dev/dxg" in run
    assert "type=bind,src=/usr/lib/wsl,dst=/usr/lib/wsl,readonly" in run
    assert "LD_LIBRARY_PATH=/usr/lib/wsl/lib" in run
    assert "GALLIUM_DRIVER" not in run
    assert "MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA" in run
    assert "GAMECUA_GRAPHICS_PRESET=wsl-d3d12" in run
    assert "GAMECUA_RENDER_DEVICE=NVIDIA" in run
    assert "LIBGL_ALWAYS_SOFTWARE=0" in run
    assert "--runtime" not in run
    assert "nvidia.com/gpu" not in run


def test_readiness_probe_requires_requested_hardware_renderer():
    assert session.probe_command(None, "software") == ["glxinfo", "-B"]
    assert session.probe_command("NVIDIA", "wsl-d3d12") == [
        "env",
        "GALLIUM_DRIVER=d3d12",
        "glxinfo",
        "-B",
    ]
    assert session.probe_command("nvidia0", "nvidia")[:4] == [
        "/opt/VirtualGL/bin/vglrun",
        "-d",
        "egl0",
        "-c",
    ]
    nvidia = "OpenGL renderer string: D3D12 (NVIDIA GeForce RTX 5050 Laptop GPU)"
    intel = "OpenGL renderer string: D3D12 (Intel(R) Arc(TM) 130T GPU (16GB))"
    software = "OpenGL renderer string: llvmpipe (LLVM 20.1.8, 256 bits)"
    assert session.probe_accepts(software, None, "software")
    assert session.probe_accepts(nvidia, "NVIDIA", "wsl-d3d12")
    assert session.probe_accepts(nvidia, "nvidia", "wsl-d3d12")
    assert not session.probe_accepts(intel, "NVIDIA", "wsl-d3d12")
    assert not session.probe_accepts(software, "NVIDIA", "wsl-d3d12")
    assert not session.probe_accepts("", "NVIDIA", "wsl-d3d12")
    assert not session.probe_accepts(software, "nvidia0", "nvidia")


def test_steam_environment_reuse_mounts_the_prepared_home(monkeypatch, tmp_path):
    from gamecua.environments import manager

    source = tmp_path / "source"
    home = source / "private/home"
    home.mkdir(parents=True)
    (source / "environment.local.json").write_text(json.dumps({"steam_home": str(home)}))
    calls = []

    def fake_docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "run":
            raise RuntimeError("stop after container arguments")
        return "image-id"

    monkeypatch.setattr(manager, "docker", fake_docker)
    monkeypatch.setattr(manager, "apparmor_profile", lambda: "unconfined")
    with pytest.raises(RuntimeError, match="stop after"):
        Environment(tmp_path / "evaluation").create(None, None, steam_environment=source)
    run = " ".join(next(c for c in calls if c[0] == "run"))
    assert f"type=bind,src={home.resolve()},dst=/state/home" in run
    assert "apparmor=unconfined" in run


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("kernel\0", "kernel"),
        ("docker-default (enforce)\n", "docker-default"),
        ("unconfined", "unconfined"),
    ],
)
def test_apparmor_profile_ignores_null_padding_and_mode(tmp_path, raw, expected):
    current = tmp_path / "current"
    current.write_text(raw)
    assert apparmor_profile(current) == expected


def test_environment_mounts_unique_valid_dbus_machine_id(monkeypatch, tmp_path):
    from gamecua.environments import manager

    calls = []

    def docker(*args):
        calls.append(args)
        if args[:2] == ("image", "inspect"):
            return "sha256:test"
        if args[0] == "run":
            mount = next(
                value
                for value in args
                if value.startswith("type=bind,src=") and value.endswith(",dst=/state")
            )
            state = Path(mount.split("src=", 1)[1].split(",dst=", 1)[0])
            (state / "ready.json").write_text("{}")
        return "container-test"

    monkeypatch.setattr(manager, "docker", docker)
    monkeypatch.setattr(manager, "inspect_host", lambda: {})
    monkeypatch.setattr(Environment, "status", lambda self: {})
    identities = []
    for name in ("first", "second"):
        environment = Environment(tmp_path / name)
        environment.create(None, None, mode="development")
        machine_id = environment.root / "private/machine-id"
        value = machine_id.read_text().strip()
        assert len(value) == 32 and int(value, 16) >= 0
        identities.append(value)
        assert any(
            f"type=bind,src={machine_id},dst=/etc/machine-id,readonly" in call for call in calls
        )
    assert len(set(identities)) == 2
