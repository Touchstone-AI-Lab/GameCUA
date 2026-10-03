"""Steam Proton paths, the Steam launch-options wrapper and game process identity."""

import os
import sys
from pathlib import Path

APP_ID = 289070
PROFILE_NAME = "Sid Meier's Civilization VI"
WINDOWS_EXECUTABLE = "Base/Binaries/Win64Steam/CivilizationVI.exe"


def proton_paths(steam_client):
    """Return the Proton prefix, native profile and save directories of this Steam client."""
    prefix = Path(steam_client).resolve() / "steamapps/compatdata" / str(APP_ID) / "pfx"
    user = prefix / "drive_c/users/steamuser"
    return {
        "prefix": prefix,
        "profile": user / "AppData/Local/Firaxis Games" / PROFILE_NAME,
        "saves": user / "Documents/My Games" / PROFILE_NAME / "Saves",
    }


def steam_ipc_command(steam_client):
    return [str(Path(steam_client).resolve() / "steam.sh"), "-applaunch", str(APP_ID)]


def profile_mounts(steam_client, inherited=""):
    """Expose bound episode profile directories inside the Steam compatibility sandbox."""
    mounts = [value for value in inherited.split(":") if value]
    paths = proton_paths(steam_client)
    for name in ("profile", "saves"):
        path = paths[name]
        if path.is_symlink() and path.is_dir():
            target = str(path.resolve())
            if target not in mounts:
                mounts.append(target)
    return ":".join(mounts)


def process_identity(pid):
    """Return the pid and kernel start time that identify one live process."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except OSError as error:
        raise RuntimeError("Civilization VI process exited") from error
    if fields[0] in ("Z", "X", "x"):
        raise RuntimeError("Civilization VI process exited")
    return {"pid": pid, "start_ticks": fields[19]}


def main(argv=None):
    """Steam launch options entry point: run the DX11 executable with fixed DXVK settings."""
    args = list(sys.argv[1:] if argv is None else argv)
    index = next(
        index
        for index, value in enumerate(args)
        if Path(value).name in ("CivilizationVI.exe", "CivilizationVI_DX12.exe")
    )
    args[index] = str(Path(args[index]).with_name("CivilizationVI.exe").resolve())
    env = dict(
        os.environ,
        DXVK_CONFIG="dxvk.numCompilerThreads = 4",
        DISABLE_VK_LAYER_VALVE_steam_overlay_1="1",
        DISABLE_VK_LAYER_VALVE_steam_fossilize_1="1",
    )
    mounts = profile_mounts(
        Path(args[0]).resolve().parents[1], os.environ.get("STEAM_COMPAT_MOUNTS", "")
    )
    if mounts:
        env["STEAM_COMPAT_MOUNTS"] = mounts
    os.execvpe(args[0], args, env)


if __name__ == "__main__":
    main()
