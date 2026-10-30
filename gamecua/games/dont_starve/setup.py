"""Private native profiles prepared from a frozen snapshot with ordinary game controls."""

import configparser
import fcntl
import json
import os
import pwd
import re
import shutil
from pathlib import Path

from ...catalog import digest
from ...storage import write_json
from ..steam.preparation import CLIENT
from .saves import decode

OBSERVER_MOD = "gamecua_observer"


def native_profile():
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".klei/DoNotStarve"


def process_identity(pid):
    values = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    if values[0] == "Z":
        raise RuntimeError("Native process exited")
    return {"pid": pid, "start_ticks": values[19]}


def steam_client(installation):
    library = Path(installation).resolve().parent.parent
    return library.parent if (library / "appmanifest_219740.acf").is_file() else CLIENT


def installation_identity(installation):
    manifest = steam_client(installation) / "steamapps/appmanifest_219740.acf"
    build = re.search(r'"buildid"\s+"(\d+)"', manifest.read_text())
    return {"steam_build_id": build[1] if build else None}


class ProfileLease:
    def __init__(self, profile, record, target=None):
        self.profile, self.record = Path(profile).resolve(), Path(record)
        self.target = Path(target) if target else native_profile()
        self.lock = None

    def acquire(self):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.lock = self.target.with_name(self.target.name + ".gamecua.lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if self.record.exists() and json.loads(self.record.read_text()).get("active"):
            if self.target.is_symlink() and self.target.resolve() == self.profile:
                return
            raise RuntimeError("An interrupted profile binding requires inspection")
        if self.target.is_symlink():
            raise RuntimeError("Refusing to replace an existing native profile symlink")
        state = {
            "active": True,
            "target": str(self.target),
            "profile": str(self.profile),
            "backup": str(self.target.with_name(self.target.name + ".gamecua-backup")),
            "had_original": self.target.exists(),
        }
        write_json(self.record, state)
        if state["had_original"]:
            self.target.rename(state["backup"])
        self.target.symlink_to(self.profile, target_is_directory=True)

    def release(self):
        if self.record.exists():
            state = json.loads(self.record.read_text())
            if state.get("active"):
                if self.target.is_symlink():
                    self.target.unlink()
                if state["had_original"]:
                    Path(state["backup"]).rename(self.target)
                write_json(self.record, {**state, "active": False})
        if self.lock:
            self.lock.close()
            self.lock = None


def observer_mod(profile):
    """Name of the observer mod the profile's first save slot was prepared with."""
    index = Path(profile) / "save/saveindex"
    if index.is_file():
        mods = set(decode(index.read_bytes())["slots"][1].get("mods", {}).values())
        if len(mods) == 1:
            return mods.pop()
    return OBSERVER_MOD


def configure(profile, installation, episode_id, snapshot_hash):
    profile, installation = Path(profile).resolve(), Path(installation).resolve()
    (profile / "save").mkdir(parents=True, exist_ok=True)
    settings = configparser.ConfigParser()
    settings.optionxform = str
    settings.read(profile / "settings.ini")
    for section, values in {
        "STEAM": {"DISABLECLOUD": "true"},
        "MISC": {"ENABLECONSOLE": "false", "FIRST_TIME_INSTALL": "false"},
        "graphics": {
            "dynamic_loading_level": "0",
            "window_x": "100",
            "window_y": "100",
            "HUDSize": "10",
        },
    }.items():
        if section not in settings:
            settings[section] = {}
        settings[section].update(values)
    with (profile / "settings.ini").open("w") as file:
        settings.write(file)
    runtime = profile / "runtime"
    (runtime / "bin").mkdir(parents=True)
    shutil.copy2(installation / "bin/dontstarve_steam", runtime / "bin/dontstarve_steam")
    (runtime / "data").mkdir()
    for asset in (installation / "data").iterdir():
        (runtime / "data" / asset.name).symlink_to(asset, target_is_directory=asset.is_dir())
    (runtime / "bin/lib32").symlink_to(installation / "bin/lib32", target_is_directory=True)
    observer = observer_mod(profile)
    mod = runtime / "mods" / observer
    mod.mkdir(parents=True)
    for name in ("modinfo.lua", "modmain.lua"):
        shutil.copyfile(Path(__file__).with_name(name), mod / name)
    (runtime / "mods/modsettings.lua").write_text(f'ForceEnableMod("{observer}")\n')
    write_json(mod / "observer.json", {"episode_id": episode_id, "snapshot_sha256": snapshot_hash})


def environment(installation):
    installation = Path(installation).resolve()
    runtime = steam_client(installation) / "ubuntu12_32/steam-runtime"
    libraries = [
        installation / "bin/lib32",
        Path("/usr/lib/i386-linux-gnu"),
        Path("/lib/i386-linux-gnu"),
        runtime / "usr/lib/i386-linux-gnu",
        runtime / "lib/i386-linux-gnu",
    ]
    return {
        **os.environ,
        "SteamAppId": "219740",
        "SteamGameId": "219740",
        "LD_LIBRARY_PATH": ":".join(map(str, libraries)),
    }


def validate_snapshot(snapshot):
    snapshot = Path(snapshot).resolve()
    manifest = json.loads((snapshot / "snapshot.manifest.json").read_text())
    return digest(manifest), json.loads((snapshot / "reference/plan.json").read_text())
