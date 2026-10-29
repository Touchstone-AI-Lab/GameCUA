"""Synthetic Proton prefix snapshots; never benchmark results."""

from gamecua.games.untitled_goose_game.setup import (
    PROTON_METADATA,
    SAVE_DIRECTORY,
    capture_snapshot,
)


def test_snapshot_preserves_proton_metadata_and_removes_progress(tmp_path):
    compatdata = tmp_path / "compatdata"
    saves = compatdata / SAVE_DIRECTORY
    saves.mkdir(parents=True)
    (saves / "savegame0.save").write_bytes(b"existing progress")
    for name in PROTON_METADATA:
        (compatdata / name).write_text(f"proton {name}")
    snapshot = capture_snapshot(tmp_path / "installation", compatdata, tmp_path / "snapshot")
    assert not list((snapshot / SAVE_DIRECTORY).glob("savegame*.save"))
    assert {name: (snapshot / name).read_text() for name in PROTON_METADATA} == {
        name: f"proton {name}" for name in PROTON_METADATA
    }


def test_snapshot_copies_proton_file_links_that_point_outside(tmp_path):
    proton = tmp_path / "proton" / "dxgi.dll"
    proton.parent.mkdir()
    proton.write_bytes(b"proton dll")
    compatdata = tmp_path / "compatdata"
    system32 = compatdata / "pfx/drive_c/windows/system32"
    system32.mkdir(parents=True)
    (system32 / "dxgi.dll").symlink_to(proton)
    dosdevices = compatdata / "pfx/dosdevices"
    dosdevices.mkdir()
    (dosdevices / "c:").symlink_to("../drive_c")
    for name in PROTON_METADATA:
        (compatdata / name).write_text(f"proton {name}")
    snapshot = capture_snapshot(tmp_path / "installation", compatdata, tmp_path / "snapshot")
    copied = snapshot / "pfx/drive_c/windows/system32/dxgi.dll"
    assert not copied.is_symlink() and copied.read_bytes() == b"proton dll"
    assert (snapshot / "pfx/dosdevices/c:").is_symlink()
