"""Official Steam/Proton launch settings and PEAK title-screen profile snapshots."""

import os
import shutil
from pathlib import Path

from ...storage import write_json

APP_ID = 3527290


def stage_game(installation, target):
    """Link the game files into an episode directory with a private BepInEx copy."""
    installation, target = Path(installation).resolve(), Path(target).resolve()
    target.mkdir(parents=True, exist_ok=False)
    for source in installation.iterdir():
        if source.name == "BepInEx":
            shutil.copytree(
                source,
                target / source.name,
                ignore=shutil.ignore_patterns("LogOutput.log", "cache"),
            )
        else:
            (target / source.name).symlink_to(source, target_is_directory=source.is_dir())
    return target


def native_environment(profile, client, binding):
    """Return the Proton, WSL hardware renderer and observer environment for one launch."""
    profile = Path(profile).resolve()
    environment = dict(
        os.environ,
        SteamAppId=str(APP_ID),
        SteamGameId=str(APP_ID),
        STEAM_COMPAT_APP_ID=str(APP_ID),
        STEAM_COMPAT_CLIENT_INSTALL_PATH=str(client),
        STEAM_COMPAT_DATA_PATH=str(profile / "compat"),
        PROTON_USE_WINED3D="1",
        PROTON_LOG="0",
        WINEDEBUG="-all",
        LIBGL_ALWAYS_SOFTWARE="0",
        GALLIUM_DRIVER="d3d12",
        MESA_LOADER_DRIVER_OVERRIDE="d3d12",
        MESA_D3D12_DEFAULT_ADAPTER_NAME="NVIDIA",
        LD_LIBRARY_PATH="/usr/lib/wsl/lib",
        WINEDLLOVERRIDES="winhttp=n,b",
        GAMECUA_PEAK_BINDING=binding,
        GAMECUA_PEAK_EVIDENCE="Z:" + (profile / "native.jsonl").as_posix(),
    )
    library_dir = os.environ.get("GAMECUA_PEAK_MESA_LIBDIR")
    if library_dir:
        library_dir = Path(library_dir).expanduser().resolve()
        environment.update(
            LD_LIBRARY_PATH=f"{library_dir}:/usr/lib/wsl/lib",
            LIBGL_DRIVERS_PATH=str(library_dir / "dri"),
        )
    return environment


def capture_snapshot(profile, installation, target):
    """Copy a clean Proton prefix that starts at the title screen."""
    target = Path(target).resolve()
    target.mkdir(parents=True)
    shutil.copytree(profile, target / "compat", symlinks=True)
    write_json(
        target / "preparation.json",
        {
            "schema_version": 1,
            "experiment_kind": "fresh_title_screen",
            "initial_scene": "Title",
            "installation": str(Path(installation).resolve()),
            "native_observer": "Read-only reflection of native runtime fields at 2 Hz; no game-state writes, game-method patches, input, UI, or scoring rules",
            "map_policy": "Native daily island selection; rotation is not bypassed.",
        },
    )
    return target
