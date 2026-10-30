import json

import pytest

from gamecua.games.dont_starve.setup import ProfileLease


def test_profile_binding_restores_original_after_normal_close(tmp_path):
    target, private = tmp_path / "native", tmp_path / "private"
    target.mkdir()
    private.mkdir()
    (target / "original").write_text("preserve me")
    lease = ProfileLease(private, tmp_path / "lease.json", target)
    lease.acquire()
    (target / "only-private").write_text("isolated")
    assert (private / "only-private").read_text() == "isolated"
    lease.release()
    assert (target / "original").read_text() == "preserve me"
    assert not (target / "only-private").exists()
    assert not json.loads((tmp_path / "lease.json").read_text())["active"]


def test_interrupted_binding_can_be_reacquired_without_reset(tmp_path):
    target, private = tmp_path / "native", tmp_path / "private"
    private.mkdir()
    record = tmp_path / "lease.json"
    lease = ProfileLease(private, record, target)
    lease.acquire()
    lease.lock.close()
    replacement = ProfileLease(private, record, target)
    replacement.acquire()
    assert target.resolve() == private
    replacement.release()
    assert not target.exists()


def test_existing_profile_symlink_is_preserved(tmp_path):
    target, private, existing = tmp_path / "native", tmp_path / "private", tmp_path / "existing"
    existing.mkdir()
    private.mkdir()
    target.symlink_to(existing, target_is_directory=True)
    lease = ProfileLease(private, tmp_path / "lease.json", target)
    with pytest.raises(RuntimeError):
        lease.acquire()
    assert target.resolve() == existing
    lease.lock.close()


def test_unmatched_onboarding_screen_never_clicks_controls(tmp_path):
    import threading
    import time
    from types import SimpleNamespace

    from PIL import Image

    from gamecua.games.dont_starve.integration import Backend

    reference = tmp_path / "reference"
    reference.mkdir()
    Image.new("RGB", (1280, 720), "white").save(reference / "pause.png")
    backend = object.__new__(Backend)
    backend.snapshot = tmp_path
    backend.folder = tmp_path
    actions = []
    backend.adapter = SimpleNamespace(
        execute=lambda action, **kw: actions.append(action),
        capture=lambda: Image.new("RGB", (1280, 720), "black"),
    )
    with pytest.raises(InterruptedError):
        backend.show_controls(
            {
                "kind": "native_controls",
                "pause_frame": "pause.png",
                "pause_region": [0, 0, 100, 100],
            },
            threading.Event(),
            time.monotonic() + 0.03,
        )
    assert actions == [{"type": "press", "key": "Escape"}]


def test_container_mount_uses_the_official_client_runtime(tmp_path, monkeypatch):
    from gamecua.games.dont_starve import setup

    client = tmp_path / "client"
    (client / "steamapps").mkdir(parents=True)
    (client / "steamapps/appmanifest_219740.acf").write_text(
        '"appid" "219740" "StateFlags" "4" "installdir" "dont_starve" "buildid" "123"'
    )
    installed = client / "steamapps/common/dont_starve"
    mounted = tmp_path / "installation"
    monkeypatch.setattr(setup, "CLIENT", client)
    for installation in (installed, mounted):
        assert setup.installation_identity(installation) == {"steam_build_id": "123"}
        runtime = str(client / "ubuntu12_32/steam-runtime")
        assert runtime in setup.environment(installation)["LD_LIBRARY_PATH"]


@pytest.mark.parametrize(
    "screen,expected", [("notice", True), ("main", True), ("slot", False), ("unknown", False)]
)
def test_absent_notices_skip_only_until_the_first_required_menu(tmp_path, screen, expected):
    from PIL import Image

    from gamecua.games.dont_starve.integration import following_menu_matches

    reference = tmp_path / "reference"
    reference.mkdir()
    colors = {"notice": "red", "main": "green", "slot": "blue", "unknown": "black"}
    steps = [{"optional": True}]
    for name in ("notice", "main", "slot"):
        Image.new("RGB", (1280, 720), colors[name]).save(reference / f"{name}.png")
        steps.append(
            {"frame": f"{name}.png", "region": [0, 0, 1280, 720], "optional": name == "notice"}
        )
    frame = Image.new("RGB", (1280, 720), colors[screen])
    assert following_menu_matches(tmp_path, steps, 0, frame) is expected


def test_snapshot_identity_is_its_manifest_digest(tmp_path):
    from gamecua.catalog import digest
    from gamecua.games.dont_starve.setup import validate_snapshot
    from gamecua.storage import write_json

    plan = {"schema_version": 1, "steps": []}
    (tmp_path / "reference").mkdir()
    write_json(tmp_path / "snapshot.manifest.json", {"profile/save/survival_1": "0" * 64})
    write_json(tmp_path / "reference/plan.json", plan)
    assert validate_snapshot(tmp_path) == (digest({"profile/save/survival_1": "0" * 64}), plan)
