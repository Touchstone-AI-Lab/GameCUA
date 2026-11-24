"""Restores the frozen custom-rally snapshot into an isolated native Linux launch profile."""

import base64
import json
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from ...catalog import digest

APP_ID = 550320
BINARY = "artofrally.x64"
PROFILE_FILES = {
    "customrally": "Funselektor Labs/art of rally/customrally",
    "SaveGame.json": "Funselektor Labs/art of rally/cloud/SaveGame.json",
    "career": "Funselektor Labs/art of rally/cloud/career",
    "prefs": "unknown/unknown/prefs",
}
RUNTIME_ENV = "ART_OF_RALLY_SNAPSHOT_RUNTIME"
PLUGIN_ENV_PREFIXES = ("GAMECUA_RALLY_", "GAMESCIENTIST_RALLY_")
IMAGE_RUNTIME_ROOT = Path("/opt/gamecua/art-of-rally/snapshot-runtime")


def plugin_environment(settings):
    """Name each plugin setting for the plugin source and for the pinned V1 plugin binary."""
    return {
        prefix + key: value for prefix in PLUGIN_ENV_PREFIXES for key, value in settings.items()
    }


def config_dir(profile):
    return Path(profile) / "home/.config/unity3d/Funselektor Labs/art of rally"


def runtime_directory(snapshot, manifest):
    explicit = os.environ.get(RUNTIME_ENV)
    if explicit:
        return Path(explicit)
    sibling = snapshot.absolute().with_name(snapshot.absolute().name + ".runtime")
    if sibling.exists():
        return sibling
    return IMAGE_RUNTIME_ROOT / digest(manifest)


def snapshot_files(snapshot):
    snapshot = Path(snapshot)
    manifest = json.loads((snapshot / "manifest.json").read_bytes())
    files = {name: snapshot / name for name in manifest if (snapshot / name).is_file()}
    if len(files) < len(manifest):
        runtime = runtime_directory(snapshot, manifest)
        files.update({name: runtime / name for name in manifest if name not in files})
    return files


def restore(snapshot, installation, profile):
    snapshot, installation, profile = map(Path, (snapshot, installation, profile))
    files = snapshot_files(snapshot)
    preparation = json.loads(files["preparation.json"].read_bytes())
    profile.mkdir(parents=True, exist_ok=False)
    root = profile / "home/.config/unity3d"
    for name, relative in PROFILE_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(files[name], path)
    prefs = root / PROFILE_FILES["prefs"]
    tree = ET.parse(prefs)
    for pref in tree.getroot():
        if pref.attrib.get("name") == "SETTINGS_APPLICATION_PATH":
            pref.text = base64.b64encode(str(config_dir(profile)).encode()).decode()
    tree.write(prefs)
    if (snapshot / "renderer-cache").is_dir():
        shutil.copytree(snapshot / "renderer-cache", profile / "home/.cache/mesa_shader_cache")
    link_steam(profile)
    game = profile / "game"
    game.mkdir()
    for name, source in files.items():
        if name.startswith("loader/"):
            target = game / name.removeprefix("loader/")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    (game / "BepInEx/plugins").mkdir()
    shutil.copyfile(
        game / "RallyNativeObserver.dll", game / "BepInEx/plugins/RallyNativeObserver.dll"
    )
    shutil.copy2(installation / BINARY, game / BINARY)
    for name in ("UnityPlayer.so", "artofrally_Data"):
        (game / name).symlink_to((installation / name).resolve())
    return preparation


def launch_environment(profile):
    profile = Path(profile).resolve()
    values = {k: v for k, v in os.environ.items() if not k.endswith("API_KEY")}
    values.update(
        HOME=str(profile / "home"),
        XDG_CONFIG_HOME=str(profile / "home/.config"),
        XDG_DATA_HOME=str(profile / "home/.local/share"),
        SteamAppId=str(APP_ID),
        SteamGameId=str(APP_ID),
        SDL_AUDIODRIVER="dummy",
    )
    return values


def link_steam(profile):
    source = Path("/state/home/.steam")
    target = Path(profile) / "home/.steam"
    target.mkdir()
    for name in ("sdk64", "steam.pid", "steam.token"):
        (target / name).symlink_to(source / name)
